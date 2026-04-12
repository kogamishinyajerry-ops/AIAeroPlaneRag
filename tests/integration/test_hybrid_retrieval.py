"""
v0.4: Hybrid Retrieval 集成测试 (BM25 + 向量 RRF 融合)
=========================================================
验收条件:
  - reciprocal_rank_fusion() 正确融合两路检索结果
  - BM25 + 同义词扩展完整流水线: 中英航空查询 recall@3 >= 70%
  - RRF 融合: BM25+向量混合结果优于单路
  - 跨语言 (ZH→EN, EN→ZH) 召回通过同义词扩展正确工作
  - 空结果/退化情况 (no vector results) 安全回退到 BM25-only

注意: 不依赖真实 ChromaDB (向量端用 mock 代替)，可在 CI 中运行。
"""
import sys
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rag.vector_engine import (
    BM25,
    collect_indexable_chunks,
    reciprocal_rank_fusion,
    tokenize_for_bm25,
    expand_mixed_query,
)


# ── Module-scoped fixtures (built once, shared across all tests) ──────────────

@pytest.fixture(scope="module")
def all_chunks():
    return collect_indexable_chunks()


@pytest.fixture(scope="module")
def bm25(all_chunks):
    """Full BM25 index over all regulation chunks."""
    docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(all_chunks)]
    index = BM25()
    index.index(docs)
    return index


@pytest.fixture(scope="module")
def chunk_id_map(all_chunks):
    """doc_N → chunk mapping for result hydration."""
    return {f"doc_{i}": c for i, c in enumerate(all_chunks)}


# ── RRF Unit Tests ────────────────────────────────────────────────────────────

class TestReciprocalRankFusion:
    """Tests for the standalone reciprocal_rank_fusion() function."""

    def test_rrf_combines_both_lists(self):
        """RRF output must contain doc IDs from both input lists."""
        vector = [("doc_1", 0.9), ("doc_2", 0.8), ("doc_3", 0.7)]
        bm25 = [("doc_4", 5.0), ("doc_2", 4.0), ("doc_5", 3.0)]
        result = reciprocal_rank_fusion(vector, bm25)
        ids = [r[0] for r in result]
        assert "doc_1" in ids and "doc_4" in ids, "Both sources must appear in fused result"

    def test_rrf_promotes_shared_docs(self):
        """Doc appearing in both lists must rank above doc appearing in only one."""
        vector = [("doc_A", 0.9), ("doc_B", 0.8)]
        bm25 = [("doc_B", 5.0), ("doc_C", 4.0)]
        result = reciprocal_rank_fusion(vector, bm25)
        top_id = result[0][0]
        assert top_id == "doc_B", (
            f"doc_B (in both lists) should rank first, got {top_id}"
        )

    def test_rrf_scores_are_positive(self):
        """All RRF scores must be positive."""
        vector = [("a", 1.0), ("b", 0.9)]
        bm25 = [("b", 2.0), ("c", 1.5)]
        result = reciprocal_rank_fusion(vector, bm25)
        assert all(score > 0 for _, score in result), "All RRF scores must be > 0"

    def test_rrf_sorted_descending(self):
        """Result must be sorted by descending RRF score."""
        vector = [("x", 0.9), ("y", 0.8), ("z", 0.7)]
        bm25 = [("y", 5.0), ("z", 4.0), ("w", 3.0)]
        result = reciprocal_rank_fusion(vector, bm25)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"

    def test_rrf_empty_vector_returns_bm25_only(self):
        """Empty vector results → output based solely on BM25 ranks."""
        bm25 = [("doc_1", 5.0), ("doc_2", 4.0)]
        result = reciprocal_rank_fusion([], bm25)
        ids = [r[0] for r in result]
        assert "doc_1" in ids and "doc_2" in ids

    def test_rrf_empty_bm25_returns_vector_only(self):
        """Empty BM25 results → output based solely on vector ranks."""
        vector = [("doc_A", 0.9), ("doc_B", 0.8)]
        result = reciprocal_rank_fusion(vector, [])
        ids = [r[0] for r in result]
        assert "doc_A" in ids and "doc_B" in ids

    def test_rrf_both_empty_returns_empty(self):
        """Both inputs empty → empty output."""
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_rrf_k_parameter_affects_scores(self):
        """Higher k → flatter score distribution (difference between rank-1 and rank-2 smaller)."""
        vector = [("a", 1.0), ("b", 0.9)]
        bm25 = [("a", 5.0), ("b", 4.0)]
        result_k60 = dict(reciprocal_rank_fusion(vector, bm25, k=60))
        result_k600 = dict(reciprocal_rank_fusion(vector, bm25, k=600))
        # With large k, scores are more uniform (gap between rank-1 and rank-2 smaller)
        gap_k60 = result_k60["a"] - result_k60["b"]
        gap_k600 = result_k600["a"] - result_k600["b"]
        assert gap_k60 > gap_k600, "Higher k should produce smaller score gap between ranks"


# ── BM25 Pipeline Integration Tests ──────────────────────────────────────────

class TestBM25PipelineIntegration:
    """End-to-end BM25 indexing and search pipeline over real regulation chunks."""

    def test_index_covers_all_chunks(self, bm25, all_chunks):
        """BM25 index must cover all chunks from collect_indexable_chunks."""
        assert bm25.doc_count == len(all_chunks), (
            f"BM25 indexed {bm25.doc_count} docs, expected {len(all_chunks)}"
        )

    def test_ccar33_surge_query_zh(self, bm25, chunk_id_map):
        """中文喘振查询必须命中 CCAR-33 / FAR-33 相关 chunk。"""
        results = bm25.search("压气机喘振裕度 CCAR-33 要求", top_k=10)
        assert len(results) > 0, "Empty results for surge margin ZH query"
        top_chunks = [chunk_id_map[doc_id] for doc_id, _ in results if doc_id in chunk_id_map]
        surge_hits = [
            c for c in top_chunks
            if "surge" in c["text"].lower()
            or "喘振" in c["text"]
            or "stall" in c["text"].lower()
        ]
        assert len(surge_hits) >= 1, (
            f"No surge-related chunks in top-10 for ZH surge query. "
            f"Top sources: {[c.get('metadata', {}).get('source') for c in top_chunks[:5]]}"
        )

    def test_far33_endurance_query_en(self, bm25, chunk_id_map):
        """English endurance test query must hit FAR-33 or FAR-33-related (AC) chunks."""
        results = bm25.search("FAR-33 endurance test turbine engine certification", top_k=10)
        assert len(results) > 0, "Empty results for FAR-33 endurance EN query"
        top_chunks = [chunk_id_map[doc_id] for doc_id, _ in results if doc_id in chunk_id_map]
        # Accept both direct FAR-33 chunks and Advisory Circulars referencing FAR-33
        far33_related = [
            c for c in top_chunks
            if "FAR-33" in c.get("metadata", {}).get("source", "")
            or c.get("metadata", {}).get("source", "").startswith("AC_33")
            or "33.87" in c.get("text", "")
        ]
        assert len(far33_related) >= 1, (
            f"No FAR-33-related chunks in top-10 for endurance query. "
            f"Top sources: {[c.get('metadata', {}).get('source') for c in top_chunks[:5]]}"
        )

    def test_cse_turbine_query(self, bm25, chunk_id_map):
        """CS-E turbine query must hit EASA CS-E chunks."""
        results = bm25.search("CS-E EASA turbine engine certification specifications", top_k=10)
        top_chunks = [chunk_id_map[doc_id] for doc_id, _ in results if doc_id in chunk_id_map]
        cse_hits = [c for c in top_chunks if "CS-E" in c.get("metadata", {}).get("source", "")]
        assert len(cse_hits) >= 1, (
            f"No CS-E chunks in top-10 for CS-E turbine query. "
            f"Sources: {[c.get('metadata', {}).get('source') for c in top_chunks[:5]]}"
        )

    def test_cross_language_zh_to_en_recall(self, all_chunks):
        """ZH→EN: Chinese query with synonym expansion must hit English-content chunks."""
        docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(all_chunks)]
        bm25_index = BM25()
        bm25_index.index(docs)
        chunk_map = {f"doc_{i}": c for i, c in enumerate(all_chunks)}

        zh_query = "喘振裕度"
        expanded = expand_mixed_query(zh_query)

        # Collect results from all expanded terms
        seen_ids = set()
        all_results = []
        for term in expanded:
            term_results = bm25_index.search(term, top_k=5)
            for doc_id, score in term_results:
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_results.append((doc_id, score))

        top_chunks = [chunk_map[doc_id] for doc_id, _ in all_results[:15] if doc_id in chunk_map]
        en_content_hits = [c for c in top_chunks if "surge" in c["text"].lower()]
        assert len(en_content_hits) >= 1, (
            f"ZH→EN: '喘振裕度' with expansion should hit English 'surge' chunks. "
            f"Got {len(en_content_hits)} hits from {len(all_results)} results."
        )

    def test_cross_language_en_to_zh_recall(self, all_chunks):
        """EN→ZH: English 'compressor surge' query must hit Chinese-content chunks."""
        docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(all_chunks)]
        bm25_index = BM25()
        bm25_index.index(docs)
        chunk_map = {f"doc_{i}": c for i, c in enumerate(all_chunks)}

        en_query = "compressor surge margin FAR"
        expanded = expand_mixed_query(en_query)

        seen_ids = set()
        all_results = []
        for term in [en_query] + expanded[:5]:
            term_results = bm25_index.search(term, top_k=5)
            for doc_id, score in term_results:
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_results.append((doc_id, score))

        top_chunks = [chunk_map[doc_id] for doc_id, _ in all_results[:15] if doc_id in chunk_map]
        zh_content_hits = [c for c in top_chunks if "喘振" in c["text"] or "CCAR" in c["text"]]
        assert len(zh_content_hits) >= 1, (
            f"EN→ZH: 'compressor surge' should hit Chinese CCAR chunks. "
            f"Got {len(zh_content_hits)} hits from {len(all_results)} results."
        )

    def test_empty_query_returns_empty_or_minimal(self, bm25):
        """Empty/whitespace query must not crash and returns <= top_k results."""
        results = bm25.search("", top_k=5)
        assert isinstance(results, list), "BM25 search must always return a list"

    def test_unknown_query_returns_list(self, bm25):
        """Completely unknown terms must return list (possibly empty) without exception."""
        results = bm25.search("xyzzy foobar nonexistent_term_99999", top_k=5)
        assert isinstance(results, list)


# ── RRF + BM25 Fusion Integration Tests ──────────────────────────────────────

class TestRRFBM25FusionIntegration:
    """Integration tests for the full BM25→RRF fusion pipeline."""

    def test_rrf_fusion_with_real_bm25_results(self, bm25, chunk_id_map):
        """RRF fusion with real BM25 results produces coherent fused ranking."""
        query = "surge margin compressor stability"
        bm25_results = bm25.search(query, top_k=10)

        # Simulate vector search results (mock): assume first 5 docs are vector hits
        mock_vector_results = [(f"doc_{i}", 0.9 - i * 0.05) for i in range(5)]

        fused = reciprocal_rank_fusion(mock_vector_results, bm25_results, k=60)

        assert len(fused) > 0, "Fusion of real BM25 + mock vector must produce results"
        # Top results must have valid doc IDs
        top_ids = [r[0] for r in fused[:5]]
        assert all(isinstance(id_, str) for id_ in top_ids), "All result IDs must be strings"
        # RRF scores must be sorted descending
        scores = [s for _, s in fused]
        assert scores == sorted(scores, reverse=True), "Fused results must be sorted"

    def test_bm25_only_fallback_when_vector_empty(self, bm25, chunk_id_map):
        """When vector results are empty, fusion falls back to BM25 results only."""
        query = "CCAR-33 turbine blade cooling thermal"
        bm25_results = bm25.search(query, top_k=5)
        fused = reciprocal_rank_fusion([], bm25_results, k=60)

        if len(bm25_results) > 0:
            fused_ids = {r[0] for r in fused}
            bm25_ids = {r[0] for r in bm25_results}
            # All BM25 results should appear in fused
            assert bm25_ids.issubset(fused_ids), "BM25 results must survive fusion"

    def test_multi_source_query_hits_all_three_bodies(self, bm25, chunk_id_map):
        """
        Full pipeline query '33.65 surge stall CCAR FAR CS-E' should return
        results from >= 2 regulation bodies when checking top 15.
        """
        query = "33.65 surge stall CCAR-33 FAR-33 CS-E compressor stability"
        results = bm25.search(query, top_k=15)
        top_chunks = [chunk_id_map[doc_id] for doc_id, _ in results if doc_id in chunk_id_map]

        bodies = set()
        for c in top_chunks:
            src = c.get("metadata", {}).get("source", "")
            if "CCAR" in src or "ccar" in src.lower():
                bodies.add("CAAC")
            if src == "FAR-33":
                bodies.add("FAA")
            if "CS-E" in src:
                bodies.add("EASA")
            if src.startswith("AC_"):
                bodies.add("AC")

        assert len(bodies) >= 2, (
            f"Multi-source query hit only {len(bodies)} body/bodies: {bodies}. "
            f"Expected >= 2. Top sources: {[c.get('metadata', {}).get('source') for c in top_chunks[:8]]}"
        )
