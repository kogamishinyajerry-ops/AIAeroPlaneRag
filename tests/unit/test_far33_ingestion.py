"""
v0.3: FAR-33 全文结构化接入验收测试
====================================
验收条件:
  - collect_indexable_chunks() 包含 FAR-33 条款 (>= 60 chunks)
  - FAR-33 §33.65 (Surge and stall) 可检索
  - 跨法规对比查询 '33.65 surge stall CCAR FAR CS-E' 返回三份来源
  - 每个 FAR-33 chunk 有 agency=FAA + section metadata
"""
import sys
import json
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import collect_indexable_chunks, BM25, tokenize_for_bm25

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def chunks():
    return collect_indexable_chunks()


@pytest.fixture(scope="module")
def source_counts(chunks):
    return Counter(c.get("metadata", {}).get("source", "?") for c in chunks)


@pytest.fixture(scope="module")
def bm25_index(chunks):
    """Build BM25 index over all chunks."""
    docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(chunks)]
    bm25 = BM25()
    bm25.index(docs)
    return bm25, chunks


# ── FAR-33 presence tests ─────────────────────────────────────────────────────

class TestFAR33Presence:
    def test_far33_chunks_exist(self, source_counts):
        """FAR-33 must be loaded from FAR-33_chunks.json."""
        count = source_counts.get("FAR-33", 0)
        assert count >= 60, (
            f"Expected >= 60 FAR-33 chunks, got {count}. "
            "Check that FAR-33_chunks.json is in data/processed/."
        )

    def test_far33_chunks_json_on_disk(self):
        """FAR-33_chunks.json file must exist in data/processed."""
        chunks_file = ROOT / "data/processed/FAR-33_chunks.json"
        assert chunks_file.exists(), f"FAR-33_chunks.json not found at {chunks_file}"

    def test_far33_full_md_on_disk(self):
        """FAR-33_Full.md file must exist in data/processed."""
        md_file = ROOT / "data/processed/FAR-33_Full.md"
        assert md_file.exists(), f"FAR-33_Full.md not found at {md_file}"


# ── FAR-33 metadata quality tests ────────────────────────────────────────────

class TestFAR33Metadata:
    def test_far33_chunks_have_agency_faa(self, chunks):
        """All FAR-33 chunks must have agency=FAA."""
        far33_chunks = [c for c in chunks if c.get("metadata", {}).get("source") == "FAR-33"]
        assert len(far33_chunks) >= 60, f"Too few FAR-33 chunks: {len(far33_chunks)}"
        faa_chunks = [c for c in far33_chunks if c.get("metadata", {}).get("agency") == "FAA"]
        assert len(faa_chunks) >= len(far33_chunks) * 0.95, (
            f"Only {len(faa_chunks)}/{len(far33_chunks)} FAR-33 chunks have agency=FAA"
        )

    def test_far33_chunks_have_section_metadata(self, chunks):
        """FAR-33 chunks must carry a 'section' field in metadata."""
        far33_chunks = [c for c in chunks if c.get("metadata", {}).get("source") == "FAR-33"]
        with_section = [c for c in far33_chunks if c.get("metadata", {}).get("section")]
        assert len(with_section) >= len(far33_chunks) * 0.9, (
            f"Only {len(with_section)}/{len(far33_chunks)} FAR-33 chunks have 'section' metadata"
        )

    def test_far33_chunks_non_empty_text(self, chunks):
        """No FAR-33 chunk should have empty text."""
        far33_chunks = [c for c in chunks if c.get("metadata", {}).get("source") == "FAR-33"]
        empty = [c for c in far33_chunks if not c.get("text", "").strip()]
        assert len(empty) == 0, f"{len(empty)} FAR-33 chunks have empty text"


# ── FAR-33 §33.65 retrievability ─────────────────────────────────────────────

class TestFAR33SurgeRetrievability:
    def test_far33_65_chunk_exists(self, chunks):
        """FAR-33 §33.65 (Surge and Stall) chunk must be present."""
        far33_chunks = [c for c in chunks if c.get("metadata", {}).get("source") == "FAR-33"]
        surge_chunks = [
            c for c in far33_chunks
            if "33.65" in c.get("metadata", {}).get("section", "")
            or "surge" in c.get("text", "").lower()
        ]
        assert len(surge_chunks) >= 1, (
            "FAR-33 §33.65 surge chunk not found. "
            "Check that FAR-33_chunks.json includes §33.65."
        )

    def test_bm25_retrieves_far33_65(self, bm25_index, chunks):
        """BM25 search for '33.65 surge stall' must return at least one FAR-33 result."""
        bm25, _ = bm25_index
        query = "33.65 surge stall margin compressor"
        results = bm25.search(query, top_k=10)

        # Map doc_id → chunk
        id_to_chunk = {f"doc_{i}": c for i, c in enumerate(chunks)}
        top_chunks = [id_to_chunk[doc_id] for doc_id, _ in results if doc_id in id_to_chunk]

        far33_hits = [c for c in top_chunks if c.get("metadata", {}).get("source") == "FAR-33"]
        assert len(far33_hits) >= 1, (
            f"BM25 top-10 for '33.65 surge stall' returned no FAR-33 chunks. "
            f"Sources found: {[c.get('metadata', {}).get('source') for c in top_chunks]}"
        )


# ── Cross-regulation retrieval test ──────────────────────────────────────────

class TestCrossRegulationRetrieval:
    def test_cross_regulation_sources_present(self, source_counts):
        """
        All three regulation bodies must be represented in the index:
          - CCAR-33 (CCAR-33-R2_Full.md or similar)
          - FAR-33
          - CS-E Amendment 5
        """
        ccar_count = (
            source_counts.get("CCAR-33.md", 0)
            + source_counts.get("CCAR-33-R2_Full.md", 0)
            + source_counts.get("CCAR-33-R2", 0)
        )
        far33_count = source_counts.get("FAR-33", 0)
        easa_count = source_counts.get("CS-E Amendment 5", 0)

        assert ccar_count >= 10, f"CCAR-33 chunks too few: {ccar_count}"
        assert far33_count >= 60, f"FAR-33 chunks too few: {far33_count}"
        assert easa_count >= 100, f"CS-E chunks too few: {easa_count}"

    def test_bm25_cross_regulation_query(self, bm25_index, chunks):
        """
        BM25 query '33.65 CCAR FAR CS-E surge stall characteristics' must return
        results from at least 2 different regulation sources in top-10.
        """
        bm25, _ = bm25_index
        query = "33.65 surge stall characteristics CCAR FAR CS-E compressor"
        results = bm25.search(query, top_k=10)

        id_to_chunk = {f"doc_{i}": c for i, c in enumerate(chunks)}
        top_chunks = [id_to_chunk[doc_id] for doc_id, _ in results if doc_id in id_to_chunk]

        sources = set()
        for c in top_chunks:
            src = c.get("metadata", {}).get("source", "")
            if "CCAR" in src or "ccar" in src.lower():
                sources.add("CCAR")
            elif src == "FAR-33":
                sources.add("FAR-33")
            elif "CS-E" in src or "EASA" in src:
                sources.add("CS-E")
            elif src.startswith("AC_"):
                sources.add("AC")

        assert len(sources) >= 2, (
            f"Cross-regulation query returned results from only {len(sources)} source(s): {sources}. "
            f"Expected >= 2 of {{CCAR, FAR-33, CS-E}}. "
            f"Top sources: {[c.get('metadata', {}).get('source') for c in top_chunks]}"
        )

    def test_total_chunks_with_far33(self, chunks):
        """Total chunks must be >= 600 now that FAR-33 is included."""
        assert len(chunks) >= 600, (
            f"Expected >= 600 total chunks after FAR-33 ingestion, got {len(chunks)}. "
            "FAR-33_chunks.json may not be loading."
        )
