"""
v0.3: Guardrail JSON 解析鲁棒性单元测试
========================================
验收目标: JSON 解析失败率 < 5% — 即以下所有解析策略均能正确处理 LLM 输出变体。
不依赖外部 LLM，仅测试 _extract_json_str / _strip_json_noise / _regex_field_extract / _parse_guardrail_output。
"""
import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.guardrail import FactCheckingGuardrail


@pytest.fixture(scope="module")
def g():
    """Guardrail instance without LLM (no API key needed)."""
    return FactCheckingGuardrail()


DUMMY_DRAFT = "压气机喘振裕度不得小于12%。"
DUMMY_CTXS = [{"text": "根据CCAR-33.65，喘振裕度要求。", "metadata": {"source": "CCAR-33", "section": "33.65"}}]


# ══════════════════════════════════════════════════════════════════════════
# 1. _extract_json_str — JSON 提取策略
# ══════════════════════════════════════════════════════════════════════════

class TestExtractJsonStr:
    def test_clean_json(self, g):
        raw = '{"status":"PASS","reasoning":"ok","safe_answer":"fine"}'
        result = g._extract_json_str(raw)
        assert "{" in result and "PASS" in result

    def test_markdown_json_fence(self, g):
        raw = 'Sure!\n```json\n{"status":"PASS","reasoning":"好的","safe_answer":"结论"}\n```'
        result = g._extract_json_str(raw)
        parsed = json.loads(result)
        assert parsed["status"] == "PASS"

    def test_markdown_json_fence_uppercase(self, g):
        raw = '```JSON\n{"status":"PARTIAL","reasoning":"部分","safe_answer":"见上"}\n```'
        result = g._extract_json_str(raw)
        parsed = json.loads(result)
        assert parsed["status"] == "PARTIAL"

    def test_markdown_fence_no_language(self, g):
        raw = '```\n{"status":"FAIL","reasoning":"不符","safe_answer":"原文"}\n```'
        result = g._extract_json_str(raw)
        parsed = json.loads(result)
        assert parsed["status"] == "FAIL"

    def test_json_with_preamble_text(self, g):
        raw = 'After reviewing the answer:\n{"status":"PARTIAL","reasoning":"部分覆盖","safe_answer":"X"}'
        result = g._extract_json_str(raw)
        parsed = json.loads(result)
        assert parsed["status"] == "PARTIAL"

    def test_json_with_postamble_text(self, g):
        raw = '{"status":"PASS","reasoning":"合格","safe_answer":"Y"}\n\n请注意...'
        result = g._extract_json_str(raw)
        parsed = json.loads(result)
        assert parsed["status"] == "PASS"

    def test_nested_json_braces(self, g):
        raw = '{"status":"PASS","reasoning":"包含 {嵌套括号} 的说明","safe_answer":"Z"}'
        result = g._extract_json_str(raw)
        # 应能正确找到外层完整 JSON
        parsed = json.loads(result)
        assert parsed["status"] == "PASS"


# ══════════════════════════════════════════════════════════════════════════
# 2. _strip_json_noise — 噪声清洗
# ══════════════════════════════════════════════════════════════════════════

class TestStripJsonNoise:
    def test_trailing_comma_in_object(self, g):
        raw = '{"status":"PASS","reasoning":"ok",}'
        cleaned = g._strip_json_noise(raw)
        parsed = json.loads(cleaned)
        assert parsed["status"] == "PASS"

    def test_trailing_comma_in_array(self, g):
        raw = '["a","b",]'
        cleaned = g._strip_json_noise(raw)
        parsed = json.loads(cleaned)
        assert parsed == ["a", "b"]

    def test_no_noise_unchanged(self, g):
        raw = '{"status":"FAIL"}'
        assert g._strip_json_noise(raw) == raw


# ══════════════════════════════════════════════════════════════════════════
# 3. _regex_field_extract — 正则兜底提取
# ══════════════════════════════════════════════════════════════════════════

class TestRegexFieldExtract:
    def test_yaml_style_output(self, g):
        raw = 'status: PASS\nreasoning: 答案与证据一致\nsafe_answer: 压气机喘振裕度满足要求'
        result = g._regex_field_extract(raw)
        assert result.get("status") == "PASS"
        assert "一致" in result.get("reasoning", "")

    def test_colon_space_format(self, g):
        raw = '"status": "PARTIAL"\n"reasoning": "部分支持"\n"safe_answer": "见检索结果"'
        result = g._regex_field_extract(raw)
        assert result.get("status") == "PARTIAL"

    def test_case_insensitive_status(self, g):
        raw = 'status: pass\nreasoning: great'
        result = g._regex_field_extract(raw)
        assert result.get("status") == "PASS"

    def test_fail_status(self, g):
        raw = 'STATUS: FAIL\nREASONING: 无对应条款'
        result = g._regex_field_extract(raw)
        assert result.get("status") == "FAIL"


# ══════════════════════════════════════════════════════════════════════════
# 4. _parse_guardrail_output — 端到端解析路径
# ══════════════════════════════════════════════════════════════════════════

class TestParseGuardrailOutput:
    def test_clean_json_pass(self, g):
        raw = '{"status":"PASS","reasoning":"全部支持","safe_answer":"裕度足够"}'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "PASS"

    def test_markdown_wrapped_json(self, g):
        raw = '```json\n{"status":"PARTIAL","reasoning":"部分","safe_answer":"见下"}\n```'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "PARTIAL"

    def test_trailing_comma_json(self, g):
        raw = '{"status":"FAIL","reasoning":"无据","safe_answer":"无法确认",}'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "FAIL"

    def test_preamble_json(self, g):
        raw = 'I evaluated the answer. Result: {"status":"PASS","reasoning":"ok","safe_answer":"fine"}'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "PASS"

    def test_regex_fallback_when_json_fails(self, g):
        raw = 'status: PARTIAL\nreasoning: 部分覆盖关键要求\nsafe_answer: 建议参考原文'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        # Should succeed via regex fallback
        assert result["status"] == "PARTIAL"

    def test_lowercase_status_normalization(self, g):
        raw = '{"status":"pass","reasoning":"合格","safe_answer":"Y"}'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "PASS"

    def test_status_partial_pass_normalization(self, g):
        raw = '{"status":"partial_pass","reasoning":"大部分支持","safe_answer":"Z"}'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "PARTIAL"

    def test_completely_unparseable_returns_unverified(self, g):
        raw = 'This is completely free form text with no JSON or field markers whatsoever.'
        result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "UNVERIFIED"
        assert "safe_answer" in result

    def test_empty_string_returns_unverified(self, g):
        result = g._parse_guardrail_output("", DUMMY_DRAFT, DUMMY_CTXS)
        assert result["status"] == "UNVERIFIED"

    def test_result_always_has_required_keys(self, g):
        for raw in [
            '{"status":"PASS","reasoning":"ok","safe_answer":"answer"}',
            '```json\n{"status":"FAIL"}\n```',
            'garbage text',
            '',
        ]:
            result = g._parse_guardrail_output(raw, DUMMY_DRAFT, DUMMY_CTXS)
            assert "status" in result
            assert "reasoning" in result
            assert "safe_answer" in result


# ══════════════════════════════════════════════════════════════════════════
# 5. _normalize_status — 状态归一化
# ══════════════════════════════════════════════════════════════════════════

class TestNormalizeStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("pass", "PASS"),
        ("PASS", "PASS"),
        ("passed", "PASS"),
        ("fail", "FAIL"),
        ("FAIL", "FAIL"),
        ("failed", "FAIL"),
        ("false", "FAIL"),
        ("partial", "PARTIAL"),
        ("PARTIAL", "PARTIAL"),
        ("partial_pass", "PARTIAL"),
        ("partially", "PARTIAL"),
        ("pass.", "PASS"),
        ("PASS!", "PASS"),
        ("pass  ", "PASS"),
    ])
    def test_normalization(self, raw, expected):
        assert FactCheckingGuardrail._normalize_status(raw) == expected


# ══════════════════════════════════════════════════════════════════════════
# 6. Local verifier (no LLM path)
# ══════════════════════════════════════════════════════════════════════════

class TestLocalVerify:
    def test_high_overlap_returns_pass(self, g):
        answer = "CCAR-33条款要求压气机的喘振裕度在所有飞行包线内满足规定要求"
        contexts = [{"text": "CCAR-33条款规定压气机喘振裕度要求", "metadata": {}}]
        result = g._local_verify(answer, contexts)
        assert result["status"] in ("PASS", "PARTIAL")

    def test_low_overlap_returns_unverified(self, g):
        answer = "The answer is completely unrelated to aviation"
        contexts = [{"text": "CCAR-33条款规定压气机喘振裕度", "metadata": {}}]
        result = g._local_verify(answer, contexts)
        assert result["status"] in ("UNVERIFIED", "PARTIAL")

    def test_empty_answer_returns_unverified(self, g):
        result = g._local_verify("", [{"text": "some context", "metadata": {}}])
        assert result["status"] == "UNVERIFIED"
