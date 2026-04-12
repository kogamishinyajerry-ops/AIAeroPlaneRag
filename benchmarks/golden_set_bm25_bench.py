"""
Golden Set BM25 Recall Benchmark
==================================
对 evaluation/golden_set_sample.json 中 30 道题进行 BM25-only 召回评估。
不需要 LLM，可在 CI 中独立运行。

评估指标:
  - recall@3: top-3 结果中是否至少一个包含 expected_keywords
  - recall@5: top-5 结果中是否至少一个包含 expected_keywords
  - source_recall: top-3 中是否包含对应 regulation 来源

通过门槛:
  - recall@3 >= 70%
  - recall@5 >= 80%

用法:
  python3 benchmarks/golden_set_bm25_bench.py
  python3 benchmarks/golden_set_bm25_bench.py --top-k 5 --threshold 0.7
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))        # for `from src.settings import ...`
sys.path.insert(0, str(ROOT / "src"))  # for direct `from rag.vector_engine import ...`

from rag.vector_engine import BM25, collect_indexable_chunks, expand_mixed_query

GOLDEN_SET_PATH = ROOT / "evaluation" / "golden_set_sample.json"

# Regulation → expected source substring mapping
# Keys are case-insensitive matched; None means "always pass" (general definitional queries)
REGULATION_SOURCE_MAP: dict[str, list[str] | None] = {
    "CCAR-33": ["CCAR-33", "ccar"],
    "FAR-33": ["FAR-33", "AC_33"],   # AC Advisory Circulars are valid FAR-33 guidance
    "CS-E": ["CS-E", "EASA", "easa"],
    "cross": ["CCAR-33", "FAR-33", "CS-E", "AC_33", "ccar", "EASA"],
    "general": None,   # definitional queries — AviationDefinitions is a valid source
}

# Normalise regulation string before lookup (golden set uses lowercase for some)
def _norm_regulation(regulation: str) -> str:
    return regulation.strip().lower() if regulation.lower() in ("cross", "general") else regulation


def load_golden_set(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _keyword_hit(chunk_text: str, keywords: list[str]) -> bool:
    """Return True if ANY keyword from the list appears in chunk text (case-insensitive)."""
    text_lower = chunk_text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _source_hit(chunk: dict, regulation: str) -> bool:
    """Return True if chunk source matches the expected regulation."""
    reg_key = _norm_regulation(regulation)
    patterns = REGULATION_SOURCE_MAP.get(reg_key, REGULATION_SOURCE_MAP.get(regulation))
    if patterns is None:
        return True   # general category — any source is acceptable
    if patterns is REGULATION_SOURCE_MAP.get(regulation) and patterns is None:
        return True
    if not patterns:
        patterns = [regulation]
    source = chunk.get("metadata", {}).get("source", "")
    return any(p.lower() in source.lower() for p in patterns)


def evaluate_question(
    question: dict,
    bm25_index: BM25,
    chunks: list[dict],
    chunk_map: dict[str, dict],
    top_k: int = 5,
) -> dict[str, Any]:
    """Evaluate a single golden set question against the BM25 index."""
    query = question["query"]
    keywords = question.get("expected_keywords", [])
    regulation = question.get("regulation", "")

    # Expand query for cross-language support
    expanded = expand_mixed_query(query)

    # RRF (Reciprocal Rank Fusion) merge of results across all expanded terms.
    # Mirrors production retrieval behaviour (Hybrid Retrieval uses RRF fusion).
    # The original full-context query receives 3× weight to prevent cross-language
    # synonym expansions from overwhelming the primary language match signal.
    K_RRF = 60
    rrf_scores: dict[str, float] = {}
    all_terms = [query] + [t for t in expanded[:8] if len(t.strip()) >= 3]
    for term_idx, term in enumerate(all_terms):
        weight = 3.0 if term_idx == 0 else 1.0  # original query has higher authority
        ranked = bm25_index.search(term, top_k=top_k * 3)
        for rank, (doc_id, _bm25_score) in enumerate(ranked):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + weight / (K_RRF + rank + 1)

    # Sort by RRF score (highest first)
    sorted_ids = sorted(rrf_scores, key=lambda d: rrf_scores[d], reverse=True)
    top_chunks = [chunk_map[doc_id] for doc_id in sorted_ids[:top_k] if doc_id in chunk_map]
    top3_chunks = top_chunks[:3]

    # Compute hits
    kw_hit_3 = any(_keyword_hit(c["text"], keywords) for c in top3_chunks) if keywords else True
    kw_hit_topk = any(_keyword_hit(c["text"], keywords) for c in top_chunks) if keywords else True
    src_hit_3 = any(_source_hit(c, regulation) for c in top3_chunks)

    return {
        "id": question["id"],
        "query": query[:60],
        "regulation": regulation,
        "language": question.get("language", "en"),
        "keyword_recall@3": kw_hit_3,
        f"keyword_recall@{top_k}": kw_hit_topk,
        "source_recall@3": src_hit_3,
        "top3_sources": [c.get("metadata", {}).get("source", "?") for c in top3_chunks],
    }


def run_benchmark(top_k: int = 5, threshold_recall3: float = 0.70,
                  threshold_recall5: float = 0.80) -> dict[str, Any]:
    print("=" * 60)
    print("AeroPower-RAG Golden Set BM25 Recall Benchmark")
    print("=" * 60)

    # Build BM25 index
    print("\n[1/3] Loading chunks and building BM25 index...")
    t0 = time.time()
    chunks = collect_indexable_chunks()
    docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(chunks)]
    bm25_index = BM25()
    bm25_index.index(docs)
    chunk_map = {f"doc_{i}": c for i, c in enumerate(chunks)}
    build_time = time.time() - t0
    print(f"    {len(chunks)} chunks indexed in {build_time:.2f}s")

    # Load golden set
    print("\n[2/3] Loading golden set...")
    golden_set = load_golden_set(GOLDEN_SET_PATH)
    print(f"    {len(golden_set)} questions loaded")

    # Evaluate each question
    print(f"\n[3/3] Evaluating recall@3 and recall@{top_k}...")
    results = []
    for q in golden_set:
        result = evaluate_question(q, bm25_index, chunks, chunk_map, top_k=top_k)
        results.append(result)
        status = "✅" if result["keyword_recall@3"] else "❌"
        print(f"  {status} [{result['regulation']}][{result['language']}] {result['query']}")
        if not result["keyword_recall@3"]:
            print(f"      top3: {result['top3_sources']}")

    # Aggregate metrics
    n = len(results)
    kw_recall3 = sum(1 for r in results if r["keyword_recall@3"]) / n
    kw_recall_topk = sum(1 for r in results if r[f"keyword_recall@{top_k}"]) / n
    src_recall3 = sum(1 for r in results if r["source_recall@3"]) / n

    # Per-regulation breakdown
    by_reg: dict[str, list] = {}
    for r in results:
        by_reg.setdefault(r["regulation"], []).append(r)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Total questions:       {n}")
    print(f"  Keyword recall@3:      {kw_recall3:.1%}  (threshold: {threshold_recall3:.1%})")
    print(f"  Keyword recall@{top_k}:      {kw_recall_topk:.1%}  (threshold: {threshold_recall5:.1%})")
    print(f"  Source  recall@3:      {src_recall3:.1%}")
    print()

    print("Per-regulation breakdown:")
    for reg, reg_results in sorted(by_reg.items()):
        reg_n = len(reg_results)
        reg_kw3 = sum(1 for r in reg_results if r["keyword_recall@3"]) / reg_n
        print(f"  {reg:12s}  recall@3={reg_kw3:.1%}  ({reg_n} questions)")

    # Pass/fail determination
    pass_recall3 = kw_recall3 >= threshold_recall3
    pass_recall_topk = kw_recall_topk >= threshold_recall5

    print()
    print("GATE CHECK:")
    gate3 = "✅ PASS" if pass_recall3 else "❌ FAIL"
    gate_topk = "✅ PASS" if pass_recall_topk else "❌ FAIL"
    print(f"  recall@3  >= {threshold_recall3:.0%}: {gate3}")
    print(f"  recall@{top_k}  >= {threshold_recall5:.0%}: {gate_topk}")

    overall_pass = pass_recall3 and pass_recall_topk
    print(f"\n  OVERALL: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    print("=" * 60)

    summary = {
        "total": n,
        "keyword_recall_at_3": round(kw_recall3, 4),
        f"keyword_recall_at_{top_k}": round(kw_recall_topk, 4),
        "source_recall_at_3": round(src_recall3, 4),
        "build_time_seconds": round(build_time, 2),
        "pass": overall_pass,
        "gate": {
            "recall_at_3": {"value": round(kw_recall3, 4), "threshold": threshold_recall3, "pass": pass_recall3},
            f"recall_at_{top_k}": {"value": round(kw_recall_topk, 4), "threshold": threshold_recall5, "pass": pass_recall_topk},
        },
        "per_regulation": {
            reg: {
                "n": len(rr),
                "recall_at_3": round(sum(1 for r in rr if r["keyword_recall@3"]) / len(rr), 4)
            }
            for reg, rr in by_reg.items()
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden Set BM25 Recall Benchmark")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K cutoff for recall (default: 5)")
    parser.add_argument("--threshold-recall3", type=float, default=0.70, help="recall@3 pass threshold (default: 0.70)")
    parser.add_argument("--threshold-recall5", type=float, default=0.80, help="recall@top_k pass threshold (default: 0.80)")
    parser.add_argument("--output", type=str, default=None, help="JSON output path for benchmark summary")
    args = parser.parse_args()

    summary = run_benchmark(
        top_k=args.top_k,
        threshold_recall3=args.threshold_recall3,
        threshold_recall5=args.threshold_recall5,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSummary written to: {out_path}")

    sys.exit(0 if summary["pass"] else 1)


if __name__ == "__main__":
    main()
