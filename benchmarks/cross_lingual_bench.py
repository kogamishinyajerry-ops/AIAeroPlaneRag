"""
BM25 中→英跨语言召回基准测试
=================================
验收标准: 25 道中文查询，recall@3 >= 0.6（即 >= 15/25 道题在 top-3 中命中英文相关文档）

测试方法:
  1. 构建包含英文段落的 BM25 索引（模拟 FAR-33 英文条款库）
  2. 用中文查询经同义词扩展后在英文语料库中检索
  3. 判断 top-3 是否包含预期相关文档

运行:
    python benchmarks/cross_lingual_bench.py

退出码:
    0 — 通过 (recall@3 >= 0.6)
    1 — 未通过
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rag.vector_engine import BM25, tokenize_for_bm25, SYNONYM_DICT  # type: ignore

THRESHOLD = 0.60
REPORT_PATH = Path(__file__).parent / "cross_lingual_recall_report.json"


# ── 英文语料库（模拟 FAR-33 / CS-E 条款，25 主题，每主题 1 条文档）──────────────
ENGLISH_CORPUS = [
    {"id": "far-surge", "text": "The compressor must maintain adequate surge margin throughout the approved operating envelope to prevent compressor stall and damage.", "metadata": {"source": "FAR-33.65", "topic": "surge_margin"}},
    {"id": "far-turbine-blade", "text": "Turbine blade containment and retention must be demonstrated by test. Turbine blades must withstand centrifugal loads.", "metadata": {"source": "FAR-33.27", "topic": "turbine_blade"}},
    {"id": "far-fuel", "text": "The fuel system must supply fuel to the engine at adequate flow rate and pressure for satisfactory operation.", "metadata": {"source": "FAR-33.29", "topic": "fuel_system"}},
    {"id": "far-temperature", "text": "The engine must operate satisfactorily through the full range of outside air temperature from -54°C to +49°C.", "metadata": {"source": "FAR-33.47", "topic": "temperature"}},
    {"id": "far-overspeed", "text": "The engine rotor must withstand overspeed conditions for the specified duration without failure.", "metadata": {"source": "FAR-33.27", "topic": "overspeed"}},
    {"id": "far-thrust", "text": "The takeoff thrust or power rating must be demonstrated under sea level standard atmospheric conditions.", "metadata": {"source": "FAR-33.7", "topic": "thrust"}},
    {"id": "far-lubrication", "text": "The lubrication system must supply adequate oil to all parts requiring lubrication under all normal operating conditions.", "metadata": {"source": "FAR-33.71", "topic": "lubrication"}},
    {"id": "far-vibration", "text": "The engine must not exhibit vibration levels exceeding acceptable limits throughout the approved operating envelope.", "metadata": {"source": "FAR-33.33", "topic": "vibration"}},
    {"id": "far-fatigue", "text": "Compliance with fatigue requirements must be shown by testing or analysis for all rotating components.", "metadata": {"source": "FAR-33.70", "topic": "fatigue"}},
    {"id": "far-ignition", "text": "The ignition system must be capable of starting the engine under all specified conditions including altitude relight.", "metadata": {"source": "FAR-33.69", "topic": "ignition"}},
    {"id": "far-containment", "text": "The engine must be designed to contain any blade fragment that results from a blade failure without penetrating the engine case.", "metadata": {"source": "FAR-33.94", "topic": "containment"}},
    {"id": "far-power-loss", "text": "The engine must be designed to minimize the hazardous effects of power loss and any uncontained failure.", "metadata": {"source": "FAR-33.75", "topic": "power_loss"}},
    {"id": "far-material", "text": "All materials used must meet the strength and durability requirements under the specified environmental conditions.", "metadata": {"source": "FAR-33.15", "topic": "material"}},
    {"id": "far-stress", "text": "Stress analysis must demonstrate that all structural components have adequate strength under ultimate load conditions.", "metadata": {"source": "FAR-33.19", "topic": "stress"}},
    {"id": "far-endurance", "text": "Engine endurance tests must demonstrate reliable operation throughout the service life.", "metadata": {"source": "FAR-33.87", "topic": "endurance"}},
    {"id": "far-altitude", "text": "The engine must operate satisfactorily at all altitudes within the approved flight envelope.", "metadata": {"source": "FAR-33.47", "topic": "altitude"}},
    {"id": "far-pressure", "text": "The engine must demonstrate adequate performance under all operating pressure conditions.", "metadata": {"source": "FAR-33.29", "topic": "pressure"}},
    {"id": "far-rotor", "text": "Rotor integrity must be demonstrated by proof test and analysis to prevent catastrophic failures.", "metadata": {"source": "FAR-33.27", "topic": "rotor"}},
    {"id": "far-cooling", "text": "The cooling system must maintain turbine blade temperatures within acceptable limits during all operating conditions.", "metadata": {"source": "FAR-33.47", "topic": "cooling"}},
    {"id": "far-maintenance", "text": "The engine must be designed to facilitate inspection, maintenance, and overhaul in service.", "metadata": {"source": "FAR-33.4", "topic": "maintenance"}},
    {"id": "far-noise", "text": "Engine noise certification must comply with applicable noise standards.", "metadata": {"source": "FAR-36", "topic": "noise"}},
    {"id": "far-emissions", "text": "Engine exhaust emissions must comply with the applicable emission standards for hydrocarbons, CO, and NOx.", "metadata": {"source": "FAR-34", "topic": "emissions"}},
    {"id": "far-icing", "text": "The engine must demonstrate satisfactory operation in icing conditions throughout the specified icing envelope.", "metadata": {"source": "FAR-33.68", "topic": "icing"}},
    {"id": "far-reverser", "text": "Thrust reverser systems must be designed to prevent uncommanded deployment during flight.", "metadata": {"source": "FAR-33.97", "topic": "reverser"}},
    {"id": "far-bird-ingestion", "text": "The engine must demonstrate the ability to ingest birds without causing unacceptable hazard to the aircraft.", "metadata": {"source": "FAR-33.76", "topic": "bird_ingestion"}},
]

# ── 25 道中文查询（每道题映射到预期英文文档 id）────────────────────────────────
ZH_QUERIES = [
    {"id": "q01", "query": "压气机喘振裕度的适航要求是什么", "expected_doc_ids": ["far-surge"]},
    {"id": "q02", "query": "涡轮叶片的包容性如何验证", "expected_doc_ids": ["far-containment", "far-turbine-blade"]},
    {"id": "q03", "query": "燃油系统的供油流量和压力要求", "expected_doc_ids": ["far-fuel", "far-pressure"]},
    {"id": "q04", "query": "发动机工作温度范围限制", "expected_doc_ids": ["far-temperature"]},
    {"id": "q05", "query": "转子超速保护要求", "expected_doc_ids": ["far-overspeed", "far-rotor"]},
    {"id": "q06", "query": "发动机推力性能认证方法", "expected_doc_ids": ["far-thrust"]},
    {"id": "q07", "query": "润滑系统供油可靠性", "expected_doc_ids": ["far-lubrication"]},
    {"id": "q08", "query": "发动机振动限制标准", "expected_doc_ids": ["far-vibration"]},
    {"id": "q09", "query": "旋转部件疲劳寿命验证方法", "expected_doc_ids": ["far-fatigue"]},
    {"id": "q10", "query": "点火系统高空重新起动能力", "expected_doc_ids": ["far-ignition"]},
    {"id": "q11", "query": "叶片碎片包容性设计", "expected_doc_ids": ["far-containment", "far-turbine-blade"]},
    {"id": "q12", "query": "功率损失失效的危害控制", "expected_doc_ids": ["far-power-loss"]},
    {"id": "q13", "query": "发动机材料强度和耐久性要求", "expected_doc_ids": ["far-material"]},
    {"id": "q14", "query": "结构件应力分析极限载荷", "expected_doc_ids": ["far-stress"]},
    {"id": "q15", "query": "发动机耐久性持久试验要求", "expected_doc_ids": ["far-endurance"]},
    {"id": "q16", "query": "高空工作飞行包线限制", "expected_doc_ids": ["far-altitude"]},
    {"id": "q17", "query": "工作压力条件性能验证", "expected_doc_ids": ["far-pressure", "far-fuel"]},
    {"id": "q18", "query": "轮盘完整性防灾难性失效", "expected_doc_ids": ["far-rotor"]},
    {"id": "q19", "query": "涡轮叶片冷却温度控制", "expected_doc_ids": ["far-cooling", "far-temperature"]},
    {"id": "q20", "query": "发动机维修性和可检查性设计", "expected_doc_ids": ["far-maintenance"]},
    {"id": "q21", "query": "发动机噪音适航符合性", "expected_doc_ids": ["far-noise"]},
    {"id": "q22", "query": "发动机排放物 NOx 和 CO 标准", "expected_doc_ids": ["far-emissions"]},
    {"id": "q23", "query": "结冰条件下发动机工作验证", "expected_doc_ids": ["far-icing"]},
    {"id": "q24", "query": "反推力装置飞行中意外展开防护", "expected_doc_ids": ["far-reverser"]},
    {"id": "q25", "query": "发动机吸鸟试验不可接受危害", "expected_doc_ids": ["far-bird-ingestion"]},
]


def _expand_zh_query(query: str) -> List[str]:
    """
    通过滑动窗口子串匹配 SYNONYM_DICT，提取中文查询中的词汇并扩展为英文同义词。
    这是正确的做法：extract_phrase_candidates 把整个 CJK 块当一个词，无法命中字典，
    因此我们用 2-6 字的滑动窗口来扫描匹配键。
    """
    terms: set = set()
    # 1. 滑动窗口：对所有长度 2-7 的子串查 SYNONYM_DICT
    for start in range(len(query)):
        for end in range(start + 2, min(start + 8, len(query) + 1)):
            substr = query[start:end]
            if substr in SYNONYM_DICT:
                terms.add(substr)
                for syn in SYNONYM_DICT[substr]:
                    terms.add(syn.lower())
                    # 二级扩展
                    for syn2 in SYNONYM_DICT.get(syn.lower(), []):
                        terms.add(syn2.lower())
    # 2. 英文词直接保留（混合查询）
    import re as _re
    for en in _re.findall(r'[a-zA-Z][a-zA-Z0-9\-]*', query):
        terms.add(en.lower())
        for syn in SYNONYM_DICT.get(en.lower(), []):
            terms.add(syn.lower())
    return list(terms)


def _build_expanded_query(query: str) -> str:
    """将中文查询及其同义词扩展拼成 BM25 可检索的文本。"""
    expanded_terms = _expand_zh_query(query)
    all_terms = set(t.lower() for t in expanded_terms if t.strip())
    return " ".join(all_terms)


def recall_at_k(retrieved_ids: List[str], expected_ids: List[str], k: int) -> float:
    top_k = set(retrieved_ids[:k])
    relevant = set(expected_ids)
    hits = top_k & relevant
    return 1.0 if hits else 0.0


def run_benchmark(top_k: int = 3) -> Tuple[float, List[Dict]]:
    bm25 = BM25()
    bm25.index(ENGLISH_CORPUS)

    results = []
    hits = 0

    for q in ZH_QUERIES:
        expanded_query = _build_expanded_query(q["query"])
        scored = bm25.search(expanded_query, top_k=top_k)
        retrieved_ids = [doc_id for doc_id, _ in scored]
        r = recall_at_k(retrieved_ids, q["expected_doc_ids"], top_k)
        hits += int(r > 0)
        results.append({
            "id": q["id"],
            "query": q["query"],
            "expected": q["expected_doc_ids"],
            "retrieved_top3": retrieved_ids[:top_k],
            "hit": bool(r > 0),
            "expanded_query_tokens": expanded_query[:120],
        })

    recall = hits / len(ZH_QUERIES)
    return recall, results


def main() -> int:
    recall, results = run_benchmark(top_k=3)
    passed = recall >= THRESHOLD
    n = len(ZH_QUERIES)
    hits = sum(1 for r in results if r["hit"])

    # ── 打印报告 ──────────────────────────────────────────────────────────
    print("=" * 65)
    print("BM25 中→英跨语言召回基准测试 (recall@3)")
    print("=" * 65)
    print(f"总题数   : {n}")
    print(f"命中数   : {hits}")
    print(f"Recall@3 : {recall:.1%}  (门槛 {THRESHOLD:.0%})")
    print(f"结论     : {'✅ PASS' if passed else '❌ FAIL'}")

    failures = [r for r in results if not r["hit"]]
    if failures:
        print(f"\n── Miss 样本 ({len(failures)} 条) ─────────────────────────────────")
        for f in failures:
            print(f"  [{f['id']}] {f['query']}")
            print(f"        expected={f['expected']}")
            print(f"        retrieved={f['retrieved_top3']}")
    print("=" * 65)

    # ── 保存 JSON 报告 ────────────────────────────────────────────────────
    report = {
        "benchmark": "cross_lingual_recall",
        "metric": "recall@3",
        "threshold": THRESHOLD,
        "total": n,
        "hits": hits,
        "recall_at_3": round(recall, 4),
        "passed": passed,
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n📄 报告已保存: {REPORT_PATH}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
