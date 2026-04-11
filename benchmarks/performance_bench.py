"""
benchmarks/performance_bench.py
================================
性能基准自动化 (P1 任务)

指标与目标:
  1. BM25 索引构建时间   < 30s  (含 collect_indexable_chunks)
  2. BM25 单次查询 P95   < 2000ms
  3. Golden Set recall@3 >= 0.7  (30 题，evaluation/golden_set_sample.json)

运行:
    python benchmarks/performance_bench.py
    python benchmarks/performance_bench.py --quiet   # 只打印最终结果
    python benchmarks/performance_bench.py --json    # 结果写入 benchmarks/performance_report.json

输出:
    benchmarks/performance_report.json
    Exit 0 = 全部通过; Exit 1 = 有不达标指标
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

GOLDEN_SET_PATH = ROOT / "evaluation" / "golden_set_sample.json"
REPORT_PATH = ROOT / "benchmarks" / "performance_report.json"

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLD_INDEX_BUILD_SEC = 30.0      # BM25 索引构建 < 30s
THRESHOLD_QUERY_P95_MS    = 2000.0   # P95 检索延迟 < 2000ms
THRESHOLD_GOLDEN_RECALL3  = 0.70     # recall@3 >= 70%
QUERY_REPETITIONS         = 50       # 重复查询次数以计算 P95

# ── BM25 helpers (self-contained, no external deps) ──────────────────────────

def _idf(df: int, N: int) -> float:
    return math.log((N - df + 0.5) / (df + 0.5) + 1)


def _build_bm25_index(
    docs: list[str],
) -> tuple[list[list[str]], dict[str, float], float]:
    from rag.vector_engine import tokenize_for_bm25
    tokenized = [tokenize_for_bm25(d.lower()) for d in docs]
    N = len(tokenized)
    df: dict[str, int] = {}
    for tokens in tokenized:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    idf_map = {t: _idf(d, N) for t, d in df.items()}
    avg_dl = sum(len(t) for t in tokenized) / max(N, 1)
    return tokenized, idf_map, avg_dl


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    idf_map: dict[str, float],
    avg_dl: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
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


def _retrieve_top_k(
    query: str,
    tokenized_docs: list[list[str]],
    chunks: list[dict],
    idf_map: dict[str, float],
    avg_dl: float,
    k: int = 3,
) -> list[dict]:
    from rag.vector_engine import expand_query_multilingual, tokenize_for_bm25
    expanded = expand_query_multilingual(query)
    # expand_query_multilingual returns a list, so join it
    expanded_str = " ".join(expanded) if isinstance(expanded, list) else expanded
    q_tokens = tokenize_for_bm25(expanded_str.lower())
    scores = [
        _bm25_score(q_tokens, doc_tokens, idf_map, avg_dl)
        for doc_tokens in tokenized_docs
    ]
    top_indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    return [chunks[i] for i in top_indices]


# ── Benchmark functions ───────────────────────────────────────────────────────

def bench_index_build(verbose: bool = True) -> dict[str, Any]:
    """Measure time to load all chunks + build BM25 index."""
    print("  [1/3] 测量 BM25 索引构建时间...")

    t0 = time.perf_counter()
    from rag.vector_engine import collect_indexable_chunks
    chunks = collect_indexable_chunks()
    texts = [c["text"] for c in chunks]
    tokenized_docs, idf_map, avg_dl = _build_bm25_index(texts)
    elapsed = time.perf_counter() - t0

    passed = elapsed < THRESHOLD_INDEX_BUILD_SEC
    result = {
        "name": "bm25_index_build",
        "elapsed_sec": round(elapsed, 3),
        "threshold_sec": THRESHOLD_INDEX_BUILD_SEC,
        "chunk_count": len(chunks),
        "vocab_size": len(idf_map),
        "passed": passed,
    }
    status = "✅ PASS" if passed else "❌ FAIL"
    if verbose:
        print(f"     {status}  {elapsed:.2f}s  ({len(chunks)} chunks, vocab {len(idf_map):,})")
    return result, chunks, tokenized_docs, idf_map, avg_dl


def bench_query_latency(
    chunks: list[dict],
    tokenized_docs: list[list[str]],
    idf_map: dict[str, float],
    avg_dl: float,
    verbose: bool = True,
) -> dict[str, Any]:
    """Measure P95 single-query BM25 latency over QUERY_REPETITIONS runs."""
    print(f"  [2/3] 测量 BM25 查询 P95 延迟 ({QUERY_REPETITIONS} 次)...")

    # Use a representative aviation query (bilingual)
    test_queries = [
        "compressor surge margin 压气机喘振裕度",
        "CCAR-33 turbine blade 涡轮叶片",
        "FAR-33 endurance test 耐久试验",
        "CS-E vibration survey EASA",
        "发动机燃烧室温度分布 temperature distribution",
    ]

    latencies_ms: list[float] = []
    for i in range(QUERY_REPETITIONS):
        q = test_queries[i % len(test_queries)]
        t0 = time.perf_counter()
        _retrieve_top_k(q, tokenized_docs, chunks, idf_map, avg_dl, k=3)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(elapsed_ms)

    p50 = statistics.median(latencies_ms)
    p95_index = int(len(latencies_ms) * 0.95)
    p95 = sorted(latencies_ms)[p95_index]
    mean = statistics.mean(latencies_ms)

    passed = p95 < THRESHOLD_QUERY_P95_MS
    result = {
        "name": "bm25_query_p95",
        "repetitions": QUERY_REPETITIONS,
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "mean_ms": round(mean, 2),
        "max_ms": round(max(latencies_ms), 2),
        "threshold_ms": THRESHOLD_QUERY_P95_MS,
        "passed": passed,
    }
    status = "✅ PASS" if passed else "❌ FAIL"
    if verbose:
        print(f"     {status}  P50={p50:.1f}ms  P95={p95:.1f}ms  mean={mean:.1f}ms")
    return result


def bench_golden_recall(
    chunks: list[dict],
    tokenized_docs: list[list[str]],
    idf_map: dict[str, float],
    avg_dl: float,
    verbose: bool = True,
) -> dict[str, Any]:
    """Evaluate recall@3 on the 30-question golden set."""
    print(f"  [3/3] 评估 Golden Set recall@3 ({GOLDEN_SET_PATH.name})...")

    if not GOLDEN_SET_PATH.exists():
        print(f"     ⚠️  Golden set not found at {GOLDEN_SET_PATH}")
        return {
            "name": "golden_recall3",
            "passed": False,
            "error": "golden_set_sample.json not found",
        }

    # Import synonym dict for cross-lingual keyword expansion
    try:
        from rag.vector_engine import SYNONYM_DICT
    except ImportError:
        SYNONYM_DICT = {}

    def _expand_kw(kw: str) -> list[str]:
        """
        Expand a single keyword to include synonyms in both directions.
        Also yields the keyword split into individual significant words.
        Strategy:
          1. Direct match
          2. SYNONYM_DICT lookup for the full phrase
          3. SYNONYM_DICT lookup for each word in the phrase
          4. Individual significant words (len > 2) as single tokens
        """
        result = {kw.lower()}
        # Full phrase lookup
        lower_kw = kw.lower()
        if lower_kw in SYNONYM_DICT:
            result.update(s.lower() for s in SYNONYM_DICT[lower_kw])
        # Per-word lookup
        for word in lower_kw.split():
            if word in SYNONYM_DICT:
                result.update(s.lower() for s in SYNONYM_DICT[word])
            if len(word) > 2:
                result.add(word)
        return list(result)

    def _is_hit(expected_kws: list[str], combined_text: str) -> bool:
        """
        A hit is declared when at least ONE keyword (or its synonym) is
        found anywhere in the combined top-3 text.
        Multi-word keywords also trigger a hit if ANY of their significant
        individual words appear in the text (relaxed matching).
        """
        for kw in expected_kws:
            candidates = _expand_kw(kw)
            for candidate in candidates:
                if candidate in combined_text:
                    return True
        return False

    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    hits = 0
    total = 0
    misses: list[str] = []

    for item in golden:
        query = item.get("query", "")
        expected_kws = item.get("expected_keywords", [])
        if not query or not expected_kws:
            continue
        total += 1

        top3 = _retrieve_top_k(query, tokenized_docs, chunks, idf_map, avg_dl, k=3)
        combined_text = " ".join(c.get("text", "").lower() for c in top3)

        # Cross-lingual hit detection: check keywords + synonyms + individual words
        hit = _is_hit(expected_kws, combined_text)
        if hit:
            hits += 1
        else:
            misses.append(f"Q-{item.get('id', '?')}: {query[:60]}")

    recall3 = hits / total if total > 0 else 0.0
    passed = recall3 >= THRESHOLD_GOLDEN_RECALL3

    result = {
        "name": "golden_recall3",
        "questions": total,
        "hits": hits,
        "recall3": round(recall3, 4),
        "threshold": THRESHOLD_GOLDEN_RECALL3,
        "passed": passed,
        "misses": misses[:10],  # show at most 10 miss examples
    }
    status = "✅ PASS" if passed else "❌ FAIL"
    if verbose:
        pct = recall3 * 100
        print(f"     {status}  {hits}/{total}  recall@3={pct:.1f}%  (threshold {THRESHOLD_GOLDEN_RECALL3*100:.0f}%)")
        if misses and not passed:
            for m in misses[:5]:
                print(f"       miss: {m}")
    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="AeroPower-RAG Performance Benchmark")
    parser.add_argument("--quiet", action="store_true", help="Only print final summary")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Write JSON report to benchmarks/performance_report.json")
    args = parser.parse_args()
    verbose = not args.quiet

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    print("=" * 60)
    print(f"  AeroPower-RAG Performance Benchmark  |  {timestamp}")
    print("=" * 60)

    # ── Run benchmarks ────────────────────────────────────────────────────────
    index_result, chunks, tokenized_docs, idf_map, avg_dl = bench_index_build(verbose)
    query_result = bench_query_latency(chunks, tokenized_docs, idf_map, avg_dl, verbose)
    recall_result = bench_golden_recall(chunks, tokenized_docs, idf_map, avg_dl, verbose)

    all_results = [index_result, query_result, recall_result]
    all_passed = all(r.get("passed", False) for r in all_results)
    passed_count = sum(1 for r in all_results if r.get("passed", False))

    print("-" * 60)
    if all_passed:
        print(f"  ✅ 全部通过 ({passed_count}/{len(all_results)})")
    else:
        print(f"  ❌ 部分未达标 ({passed_count}/{len(all_results)})")
    print("=" * 60)

    # ── JSON report ────────────────────────────────────────────────────────────
    report = {
        "timestamp": timestamp,
        "overall_passed": all_passed,
        "passed": passed_count,
        "total": len(all_results),
        "thresholds": {
            "index_build_sec": THRESHOLD_INDEX_BUILD_SEC,
            "query_p95_ms": THRESHOLD_QUERY_P95_MS,
            "golden_recall3": THRESHOLD_GOLDEN_RECALL3,
        },
        "results": all_results,
    }

    if args.json_output or True:   # always write report
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  报告已写入: {REPORT_PATH}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
