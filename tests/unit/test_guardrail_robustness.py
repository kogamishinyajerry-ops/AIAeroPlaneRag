"""
Guardrail JSON 解析鲁棒性基准 — 100 样本
==========================================
Acceptance: 失败率 < 5%（即 ≥ 96/100 样本被正确解析，返回 PASS/PARTIAL/FAIL，
            而非因 JSON 解析故障导致的 UNVERIFIED）。
"""
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.rag.guardrail import FactCheckingGuardrail

CONTEXTS = [
    {
        "text": "压气机必须保持足够的喘振裕度。",
        "metadata": {"source": "CCAR-33", "chapter": "33.65", "section": "a"},
    }
]

VALID_STATUSES = {"PASS", "PARTIAL", "FAIL"}

# ── 辅助：判断一次解析是否"成功" ──────────────────────────────────────────────
def is_parse_success(result: dict) -> bool:
    """
    成功定义: status ∈ {PASS, PARTIAL, FAIL}
    UNVERIFIED 表示解析失败（JSON解析报错或无法提取）。
    注意: NOT_FOUND 是因为 contexts 为空，不属于解析失败，这里不测试该路径。
    """
    return result.get("status") in VALID_STATUSES


# ── 100 样本（模拟 GLM 各种真实返回） ─────────────────────────────────────────
def make_samples():
    samples = []

    # 1) 标准 JSON — 60 条
    for status in ["PASS", "PARTIAL", "FAIL"] * 20:
        samples.append(
            json.dumps({
                "status": status,
                "reasoning": f"这是 {status} 的标准原因。",
                "safe_answer": "基于检索上下文的答案。",
            }, ensure_ascii=False)
        )

    # 2) Markdown 代码块包裹 — 10 条
    for status in ["PASS", "PARTIAL", "FAIL", "PASS", "PARTIAL",
                   "FAIL", "PASS", "PARTIAL", "FAIL", "PASS"]:
        samples.append(
            f"```json\n"
            + json.dumps({"status": status, "reasoning": "推理。", "safe_answer": "答案。"}, ensure_ascii=False)
            + "\n```"
        )

    # 3) 前后有额外文字 — 8 条
    for status in ["PASS", "FAIL", "PARTIAL", "PASS", "FAIL", "PARTIAL", "PASS", "FAIL"]:
        obj = json.dumps({"status": status, "reasoning": "R", "safe_answer": "A"}, ensure_ascii=False)
        samples.append(f"以下是我的评估结果：\n{obj}\n请参考以上内容。")

    # 4) status 小写 / 尾部有句号 / 带空格 — 8 条
    for raw_status in ["pass", "fail", "partial", "PASS.", "FAIL.", "PARTIAL.",
                       " PASS ", "PARTIAL\n"]:
        samples.append(
            json.dumps({"status": raw_status, "reasoning": "R", "safe_answer": "A"},
                       ensure_ascii=False)
        )

    # 5) 嵌套有特殊字符的 safe_answer — 5 条
    for _ in range(5):
        samples.append(
            json.dumps({
                "status": "PASS",
                "reasoning": '答案包含引号 "CCAR-33.65"',
                "safe_answer": '根据 FAR-33 § 33.65(a)，\n压气机必须保持喘振裕度。',
            }, ensure_ascii=False)
        )

    # 6) safe_answer 超长 — 3 条
    for status in ["PASS", "PARTIAL", "FAIL"]:
        samples.append(
            json.dumps({
                "status": status,
                "reasoning": "长推理" * 200,
                "safe_answer": "长答案" * 200,
            }, ensure_ascii=False)
        )

    # 7) 只有两个字段（缺 safe_answer）— 3 条
    for status in ["PASS", "PARTIAL", "FAIL"]:
        samples.append(
            json.dumps({"status": status, "reasoning": "推理"}, ensure_ascii=False)
        )

    # 8) 截断 JSON（真实网络中偶发）— 3 条  → 期望 UNVERIFIED（允许失败）
    TRUNCATED = [
        '{"status": "PASS", "reasoning": "推理',          # 未闭合字符串
        '{"status": "PARTIAL", "reason',                   # 截断 key
        '{"status":',                                       # 极端截断
    ]
    samples += TRUNCATED  # 这 3 条允许解析失败

    return samples


SAMPLES = make_samples()
# 标记哪些样本允许失败（截断 JSON）
ALLOWED_FAIL_INDICES = {len(SAMPLES) - 3, len(SAMPLES) - 2, len(SAMPLES) - 1}

assert len(SAMPLES) == 100, f"样本数应为 100，实际 {len(SAMPLES)}"


class TestGuardrailParseRobustness:
    """100 样本鲁棒性基准。"""

    @pytest.fixture(scope="class")
    def guardrail(self):
        g = FactCheckingGuardrail()
        g.client = None
        return g

    @pytest.mark.parametrize("idx,raw_text", list(enumerate(SAMPLES)))
    def test_sample(self, guardrail, idx, raw_text):
        """每条样本必须返回合法 dict，且不抛异常。"""
        result = guardrail._parse_guardrail_output(raw_text, "draft", CONTEXTS)
        assert isinstance(result, dict), "返回值必须是 dict"
        assert "status" in result, "必须含 status 字段"
        assert "safe_answer" in result, "必须含 safe_answer 字段"
        # 截断 JSON 允许 UNVERIFIED；其余必须是 PASS/PARTIAL/FAIL
        if idx not in ALLOWED_FAIL_INDICES:
            assert result["status"] in VALID_STATUSES, (
                f"样本 {idx} 解析失败 (UNVERIFIED)。\n"
                f"  输入: {raw_text[:120]}\n"
                f"  输出: {result}"
            )

    def test_failure_rate_under_5_percent(self, guardrail):
        """
        聚合断言：非截断样本中失败率必须 < 5%。
        """
        required_samples = [s for i, s in enumerate(SAMPLES) if i not in ALLOWED_FAIL_INDICES]
        failures = []
        for i, raw in enumerate(required_samples):
            result = guardrail._parse_guardrail_output(raw, "draft", CONTEXTS)
            if result.get("status") not in VALID_STATUSES:
                failures.append((i, raw[:80], result["status"]))

        total = len(required_samples)
        fail_count = len(failures)
        rate = fail_count / total
        assert rate < 0.05, (
            f"失败率 {rate:.1%} ({fail_count}/{total}) 超过 5% 阈值。\n"
            f"失败样本:\n"
            + "\n".join(f"  [{i}] {txt!r} → {st}" for i, txt, st in failures)
        )
