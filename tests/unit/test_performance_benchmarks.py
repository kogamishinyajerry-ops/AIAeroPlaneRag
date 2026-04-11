"""
tests/unit/test_performance_benchmarks.py
==========================================
性能基准 pytest 集成测试 (P1 任务)

将 benchmarks/performance_bench.py 的三项指标包装成 pytest 用例，
可在 CI 的 unit-tests job 中直接运行（不需要启动后端服务）。

验收阈值 (与 performance_bench.py 保持同步):
  - BM25 索引构建   < 30s
  - BM25 单次查询   P95 < 2000ms
  - Golden Set      recall@3 >= 70%
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

GOLDEN_SET_PATH = ROOT / "evaluation" / "golden_set_sample.json"

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLD_INDEX_BUILD_SEC = 30.0
THRESHOLD_QUERY_P95_MS    = 2000.0
THRESHOLD_GOLDEN_RECALL3  = 0.70
QUERY_REPETITIONS         = 30   # reduced for unit test speed

# ── Shared fixtures (module-scoped to build index once per test run) ──────────

@pytest.fixture(scope="module")
def bm25_index():
    """Build the BM25 index once for all tests in this module."""
    from rag.vector_engine import collect_indexable_chunks, tokenize_for_bm25

    def idf(df, N): return math.log((N - df + 0.5) / (df + 0.5) + 1)

    chunks = collect_indexable_chunks()
    texts = [c["text"] for c in chunks]
    tokenized = [tokenize_for_bm25(d.lower()) for d in texts]
    N = len(tokenized)
    df: dict[str, int] = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    idf_map = {t: idf(d, N) for t, d in df.items()}
    avg_dl = sum(len(t) for t in tokenized) / max(N, 1)
    return chunks, tokenized, idf_map, avg_dl


def _score(q_toks, doc_toks, idf_map, avg_dl, k1=1.5, b=0.75):
    dl = len(doc_toks)
    freq: dict[str, int] = {}
    for t in doc_toks:
        freq[t] = freq.get(t, 0) + 1
    s = 0.0
    for t in q_toks:
        if t not in idf_map:
            continue
        f = freq.get(t, 0)
        s += idf_map[t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
    return s


def _retrieve(query, chunks, tokenized, idf_map, avg_dl, k=3):
    from rag.vector_engine import expand_query_multilingual, tokenize_for_bm25
    expanded = expand_query_multilingual(query)
    exp_str = " ".join(expanded) if isinstance(expanded, list) else expanded
    q_toks = tokenize_for_bm25(exp_str.lower())
    scores = [_score(q_toks, dt, idf_map, avg_dl) for dt in tokenized]
    top_idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    return [chunks[i] for i in top_idx]


def _is_hit(expected_kws, combined_text, synonym_dict):
    """Cross-lingual hit detection: keyword + synonyms + individual word fallback."""
    for kw in expected_kws:
        candidates = {kw.lower()}
        lower_kw = kw.lower()
        if lower_kw in synonym_dict:
            candidates.update(s.lower() for s in synonym_dict[lower_kw])
        for word in lower_kw.split():
            if word in synonym_dict:
                candidates.update(s.lower() for s in synonym_dict[word])
            if len(word) > 2:
                candidates.add(word)
        if any(c in combined_text for c in candidates):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════
# 1. BM25 索引构建时间
# ══════════════════════════════════════════════════════════════════════════

def test_bm25_index_build_time():
    """BM25 index build (including collect_indexable_chunks) must complete < 30s."""
    from rag.vector_engine import collect_indexable_chunks, tokenize_for_bm25

    def idf(df, N): return math.log((N - df + 0.5) / (df + 0.5) + 1)

    t0 = time.perf_counter()
    chunks = collect_indexable_chunks()
    texts = [c["text"] for c in chunks]
    tokenized = [tokenize_for_bm25(d.lower()) for d in texts]
    N = len(tokenized)
    df: dict[str, int] = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    idf_map = {t: idf(d, N) for t, d in df.items()}
    elapsed = time.perf_counter() - t0

    assert len(chunks) >= 500, f"Expected >= 500 chunks, got {len(chunks)}"
    assert elapsed < THRESHOLD_INDEX_BUILD_SEC, (
        f"BM25 index build took {elapsed:.1f}s, threshold is {THRESHOLD_INDEX_BUILD_SEC}s"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2. BM25 单次查询 P95 延迟
# ══════════════════════════════════════════════════════════════════════════

def test_bm25_query_p95_latency(bm25_index):
    """BM25 single query P95 latency must be < 2000ms."""
    chunks, tokenized, idf_map, avg_dl = bm25_index

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
        _retrieve(q, chunks, tokenized, idf_map, avg_dl, k=3)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

    p95_idx = int(len(latencies_ms) * 0.95)
    p95 = sorted(latencies_ms)[p95_idx]
    p50 = statistics.median(latencies_ms)

    assert p95 < THRESHOLD_QUERY_P95_MS, (
        f"BM25 query P95={p95:.1f}ms exceeds {THRESHOLD_QUERY_P95_MS}ms threshold. "
        f"P50={p50:.1f}ms"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3. Golden Set recall@3
# ══════════════════════════════════════════════════════════════════════════

def test_golden_set_recall3(bm25_index):
    """Golden set recall@3 must be >= 70% using cross-lingual keyword matching."""
    chunks, tokenized, idf_map, avg_dl = bm25_index

    assert GOLDEN_SET_PATH.exists(), f"Golden set not found: {GOLDEN_SET_PATH}"
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))

    try:
        from rag.vector_engine import SYNONYM_DICT
    except ImportError:
        SYNONYM_DICT = {}

    hits = 0
    total = 0
    misses: list[str] = []

    for item in golden:
        query = item.get("query", "")
        expected_kws = item.get("expected_keywords", [])
        if not query or not expected_kws:
            continue
        total += 1

        top3 = _retrieve(query, chunks, tokenized, idf_map, avg_dl, k=3)
        combined_text = " ".join(c.get("text", "").lower() for c in top3)

        if _is_hit(expected_kws, combined_text, SYNONYM_DICT):
            hits += 1
        else:
            misses.append(f"Q-{item.get('id', '?')}: {query[:70]}")

    recall3 = hits / total if total else 0.0
    miss_sample = "\n  ".join(misses[:5])

    assert recall3 >= THRESHOLD_GOLDEN_RECALL3, (
        f"Golden set recall@3={recall3:.1%} ({hits}/{total}) is below {THRESHOLD_GOLDEN_RECALL3:.0%} threshold.\n"
        f"Sample misses:\n  {miss_sample}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 4. 黄金集基本结构验证
# ══════════════════════════════════════════════════════════════════════════

def test_golden_set_size():
    """Golden set must have >= 20 questions (P1 task requirement)."""
    assert GOLDEN_SET_PATH.exists(), f"Golden set not found: {GOLDEN_SET_PATH}"
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    assert len(golden) >= 20, f"Golden set has {len(golden)} questions, need >= 20"


def test_golden_set_multilingual():
    """Golden set must cover both Chinese and English queries."""
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    langs = {item.get("language") for item in golden}
    assert "zh" in langs, "Golden set missing Chinese queries"
    assert "en" in langs, "Golden set missing English queries"


def test_golden_set_multi_regulation():
    """Golden set must cover CCAR-33, FAR-33, CS-E, and cross-regulation."""
    golden = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    regs = {item.get("regulation") for item in golden}
    assert "CCAR-33" in regs, "Missing CCAR-33 questions"
    assert "FAR-33" in regs, "Missing FAR-33 questions"
    assert "CS-E" in regs, "Missing CS-E questions"
    assert "cross" in regs, "Missing cross-regulation questions"
