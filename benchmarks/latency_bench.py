"""
检索延迟性能基准
================
验收标准: P95 首次检索延迟 < 2000ms

运行:
    python benchmarks/latency_bench.py

退出码:
    0 — 通过 (P95 < 2000ms)
    1 — 未通过
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rag.vector_engine import BM25  # type: ignore

P95_THRESHOLD_MS = 2000
REPORT_PATH = Path(__file__).parent / "latency_bench_report.json"
WARMUP_RUNS = 2
MEASURE_RUNS = 20

BENCHMARK_QUERIES = [
    "压气机喘振裕度要求",
    "涡轮叶片材料标准",
    "FAR-33与CCAR-33的差异",
    "发动机最低怠速推力",
    "压气机效率测试方法",
    "航空发动机适航取证阶段",
    "燃气涡轮发动机结构组成",
    "FADEC全权数字式发动机控制",
    "CCAR-33-R4与FAR-25发动机安装接口",
    "涡轮进口温度限制",
    "surge margin compressor stall prevention",
    "turbine blade containment certification",
    "engine endurance test requirements FAR 33.87",
    "overspeed rotor integrity proof test",
    "ignition system altitude relight",
]


def build_corpus(count: int = 1000) -> List[Dict]:
    topics = ["压气机喘振裕度", "涡轮叶片材料", "燃油系统认证", "发动机温度范围",
              "疲劳寿命验证", "振动试验标准", "排放污染物限制", "噪声审定程序",
              "维修检查周期", "适航取证流程"]
    return [
        {"id": f"chunk-{i:05d}",
         "text": f"第{i}条关于{topics[i % len(topics)]}的要求：必须满足所有适用的安全标准和适航规定。",
         "metadata": {"source": f"REG-{i % 10}", "section": f"§{i}"}}
        for i in range(count)
    ]


def measure_latencies(index: BM25, queries: List[str], runs: int = 1) -> List[float]:
    latencies = []
    for _ in range(runs):
        for q in queries:
            start = time.perf_counter()
            index.search(q, top_k=3)
            latencies.append((time.perf_counter() - start) * 1000)
    return latencies


def percentile(data: List[float], p: float) -> float:
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def main() -> int:
    # ── Build index ───────────────────────────────────────────────────────
    corpus = build_corpus(1000)
    index = BM25()
    t0 = time.perf_counter()
    index.index(corpus)
    index_ms = (time.perf_counter() - t0) * 1000

    # ── Warmup ────────────────────────────────────────────────────────────
    measure_latencies(index, BENCHMARK_QUERIES, WARMUP_RUNS)

    # ── Measure ───────────────────────────────────────────────────────────
    latencies = measure_latencies(index, BENCHMARK_QUERIES, MEASURE_RUNS)

    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    mean = statistics.mean(latencies)
    passed = p95 < P95_THRESHOLD_MS

    # ── Print report ──────────────────────────────────────────────────────
    print("=" * 60)
    print("检索延迟性能基准 (BM25, 1000 docs, 15 queries)")
    print("=" * 60)
    print(f"索引构建耗时  : {index_ms:.1f}ms")
    print(f"测量轮次      : {MEASURE_RUNS} × {len(BENCHMARK_QUERIES)} queries")
    print(f"总样本数      : {len(latencies)}")
    print(f"mean          : {mean:.2f}ms")
    print(f"P50           : {p50:.2f}ms")
    print(f"P95           : {p95:.2f}ms  (门槛 {P95_THRESHOLD_MS}ms)")
    print(f"P99           : {p99:.2f}ms")
    print(f"结论          : {'✅ PASS' if passed else '❌ FAIL'}")
    print("=" * 60)

    # ── Save JSON report ──────────────────────────────────────────────────
    report = {
        "benchmark": "latency_p95",
        "threshold_ms": P95_THRESHOLD_MS,
        "corpus_size": len(corpus),
        "query_count": len(BENCHMARK_QUERIES),
        "measure_runs": MEASURE_RUNS,
        "index_build_ms": round(index_ms, 2),
        "mean_ms": round(mean, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "passed": passed,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n📄 报告已保存: {REPORT_PATH}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
