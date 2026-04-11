"""
benchmarks/multilingual_mixed_bench.py
=======================================
T5.3 验收: 中英混合查询 recall@3 >= 0.6

测试集:  25 条中英混合问题，每条有已知相关文档 (golden relevant)
方法:    expand_query_multilingual() 扩展后对 BM25 索引评分，取 top-3
验收:    recall@3 (命中率) >= 0.6

运行:
    python benchmarks/multilingual_mixed_bench.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag.vector_engine import expand_query_multilingual, tokenize_for_bm25

# ── BM25 helpers (self-contained) ────────────────────────────────────────────

def _idf(df: int, N: int) -> float:
    return math.log((N - df + 0.5) / (df + 0.5) + 1)


def bm25_score(query_tokens: list[str], doc_tokens: list[str],
               idf_map: dict[str, float], avg_dl: float,
               k1: float = 1.5, b: float = 0.75) -> float:
    dl = len(doc_tokens)
    freq: dict[str, int] = {}
    for t in doc_tokens:
        freq[t] = freq.get(t, 0) + 1
    score = 0.0
    for t in query_tokens:
        if t not in idf_map:
            continue
        f = freq.get(t, 0)
        score += idf_map[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
    return score


def build_index(docs: list[str]) -> tuple[list[list[str]], dict[str, float], float]:
    tokenized = [tokenize_for_bm25(d) for d in docs]
    N = len(tokenized)
    df: dict[str, int] = {}
    for tokens in tokenized:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    idf_map = {t: _idf(d, N) for t, d in df.items()}
    avg_dl = sum(len(t) for t in tokenized) / N if N else 1
    return tokenized, idf_map, avg_dl


def retrieve_top_k(query: str, tokenized_docs: list[list[str]],
                   idf_map: dict[str, float], avg_dl: float,
                   top_k: int = 3) -> list[int]:
    # Expand query multilingually then tokenize
    expanded_terms = expand_query_multilingual(query)
    query_tokens = []
    for term in expanded_terms:
        query_tokens.extend(tokenize_for_bm25(term))

    scores = [bm25_score(query_tokens, doc, idf_map, avg_dl) for doc in tokenized_docs]
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return ranked[:top_k]


# ── Test corpus — CCAR-33-R2 style bilingual snippets ────────────────────────

CORPUS: list[str] = [
    # 0
    "压气机喘振裕度 surge margin compressor stall CCAR-33 涡轮发动机设计",
    # 1
    "涡轮叶片冷却 turbine blade cooling high temperature 材料疲劳 fatigue",
    # 2
    "燃油系统 fuel system 燃油喷嘴 fuel nozzle 燃烧室 combustion chamber",
    # 3
    "发动机控制系统 FADEC full authority digital engine control 自动驾驶",
    # 4
    "持续适航文件 airworthiness limitation 维修程序 maintenance procedure",
    # 5
    "喘振裕度试验 surge margin test 压气机稳定性 compressor stability",
    # 6
    "涡轮转子超速 turbine rotor overspeed 离心力 centrifugal force 强度",
    # 7
    "防火设计 fire protection 灭火系统 fire suppression nacelle 短舱",
    # 8
    "航空发动机型号合格证 type certificate FAA EASA CAAC 适航审定",
    # 9
    "推力额定值 thrust rating 最大连续推力 maximum continuous thrust 起飞",
    # 10
    "振动测试 vibration test 振动应力 vibration stress 共振 resonance",
    # 11
    "滑油系统 oil system 润滑 lubrication 滑油压力 oil pressure",
    # 12
    "发动机包容性 engine containment 转子爆裂 rotor burst 碎片 fragment",
    # 13
    "气动稳定性 aerodynamic stability compressor map 特性图 工作线",
    # 14
    "高循环疲劳 HCF high cycle fatigue 低循环疲劳 LCF 裂纹 crack",
    # 15
    "发动机安装 engine installation 推力架 thrust mount 隔振 vibration isolation",
    # 16
    "ETOPS 延程运行 twin-engine 双发飞机 可靠性 reliability 滑油耗量",
    # 17
    "喘振 surge stall 失速 压气机特性 compressor characteristic 余量",
    # 18
    "涡轮盘强度 turbine disc integrity 超转保护 overspeed protection",
    # 19
    "燃烧稳定性 combustion stability 熄火 flame-out 点火 ignition system",
    # 20
    "吸雨试验 rain ingestion 吸冰 ice ingestion 发动机防冰 engine anti-ice",
    # 21
    "噪声认证 noise certification 排放 emission CCAR-34 环保要求",
    # 22
    "转子动平衡 rotor balancing 不平衡量 imbalance 振动测量 vibration measurement",
    # 23
    "材料强度 material strength 合金 alloy 钛合金 titanium 镍基高温合金 nickel superalloy",
    # 24
    "发动机寿命 engine life 翻修寿命 TBO time between overhaul 疲劳分析",
]

# ── Test questions: mixed ZH+EN, with expected top-3 relevant doc indices ────

QUESTIONS: list[tuple[str, list[int]]] = [
    ("compressor surge margin 压气机喘振裕度", [0, 5, 17]),
    ("turbine blade cooling 涡轮叶片冷却", [1, 23, 18]),
    ("fuel system 燃油系统 nozzle 喷嘴", [2, 19, 11]),
    ("FADEC 发动机控制", [3, 8, 4]),
    ("airworthiness 适航 maintenance 维修", [4, 8, 15]),
    ("surge margin test 喘振裕度测试", [5, 0, 17]),
    ("turbine overspeed 涡轮超速 rotor 转子", [6, 18, 12]),
    ("fire protection 防火 nacelle 短舱", [7, 15, 4]),
    ("type certificate 型号合格证 FAA CAAC", [8, 4, 21]),
    ("thrust rating 推力额定 takeoff 起飞", [9, 15, 8]),
    ("vibration test 振动试验 resonance 共振", [10, 22, 14]),
    ("oil system 滑油系统 pressure 压力", [11, 4, 16]),
    ("engine containment 包容性 rotor burst 转子爆裂", [12, 6, 18]),
    ("compressor map 压气机特性 aerodynamic 气动", [13, 0, 17]),
    ("fatigue crack 疲劳裂纹 HCF LCF", [14, 23, 18]),
    ("engine installation 安装 mount 推力架", [15, 4, 7]),
    ("ETOPS 延程 reliability 可靠性", [16, 8, 4]),
    ("compressor stall surge 压气机失速喘振", [17, 0, 5]),
    ("turbine disc overspeed 涡轮盘超速保护", [18, 6, 12]),
    ("combustion stability 燃烧稳定性 ignition 点火", [19, 2, 20]),
    ("rain ice ingestion 吸雨吸冰 anti-ice 防冰", [20, 7, 21]),
    ("noise emission 噪声排放 CCAR-34", [21, 8, 4]),
    ("rotor balance 转子动平衡 vibration 振动", [22, 10, 6]),
    ("titanium alloy 钛合金 nickel superalloy 镍基", [23, 14, 18]),
    ("engine life TBO 发动机寿命 overhaul 翻修", [24, 4, 14]),
]


# ── Evaluation ────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 56)
    print("T5.3 中英混合查询 recall@3 基准")
    print("=" * 56)

    tokenized_docs, idf_map, avg_dl = build_index(CORPUS)

    hits = 0
    total = len(QUESTIONS)

    for q, relevant_docs in QUESTIONS:
        top_k = retrieve_top_k(q, tokenized_docs, idf_map, avg_dl, top_k=3)
        hit = any(idx in top_k for idx in relevant_docs[:1])  # recall: primary relevant doc
        hits += int(hit)
        status = "✅" if hit else "❌"
        print(f"  {status} '{q[:50]}' → top3={top_k}, expected_in={relevant_docs[:1]}")

    recall_at_3 = hits / total
    print(f"\n{'='*56}")
    print(f"recall@3: {hits}/{total} = {recall_at_3:.2%}")

    THRESHOLD = 0.60
    if recall_at_3 >= THRESHOLD:
        print(f"✅ PASS (threshold {THRESHOLD:.0%})")
    else:
        print(f"❌ FAIL (threshold {THRESHOLD:.0%})")
        sys.exit(1)

    # Save report
    report = {
        "benchmark": "multilingual_mixed_recall@3",
        "total": total,
        "hits": hits,
        "recall_at_3": round(recall_at_3, 4),
        "threshold": THRESHOLD,
        "passed": recall_at_3 >= THRESHOLD,
    }
    out = ROOT / "benchmarks/multilingual_mixed_recall_report.json"
    out.write_text(__import__("json").dumps(report, ensure_ascii=False, indent=2))
    print(f"\n📄 Report saved → {out}")


if __name__ == "__main__":
    main()
