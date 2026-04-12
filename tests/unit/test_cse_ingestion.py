"""
v0.4: CS-E EASA chunks 接入验收测试
=====================================
验收条件:
  - collect_indexable_chunks() 包含 CS-E 条款 (>= 200 chunks)
  - CS-E 权威机构标注正确 (authority=EASA, jurisdiction=EU)
  - CS-E 涡轮相关条款可被 BM25 检索 (surge, turbine)
  - 跨法规查询同时命中 CS-E + FAR-33 + CCAR
  - CS-E chunks 有 section/chapter 元数据
  - chunks_full.json 文件存在且结构完整
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import collect_indexable_chunks, BM25, tokenize_for_bm25

ROOT = Path(__file__).parent.parent.parent
CSE_CHUNKS_PATH = ROOT / "data/processed/easa_cse/chunks_full.json"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def raw_cse_chunks():
    """Load CS-E chunks directly from JSON (no vector engine)."""
    assert CSE_CHUNKS_PATH.exists(), f"chunks_full.json not found: {CSE_CHUNKS_PATH}"
    with open(CSE_CHUNKS_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_chunks():
    """All chunks from collect_indexable_chunks (includes CCAR + FAR-33 + CS-E + AC)."""
    return collect_indexable_chunks()


@pytest.fixture(scope="module")
def source_counts(all_chunks):
    return Counter(c.get("metadata", {}).get("source", "?") for c in all_chunks)


@pytest.fixture(scope="module")
def cse_chunks(all_chunks):
    """Only CS-E chunks from the full index."""
    return [c for c in all_chunks if "CS-E" in c.get("metadata", {}).get("source", "")]


@pytest.fixture(scope="module")
def bm25_index(all_chunks):
    """Build BM25 index over all chunks (module-scoped = built once)."""
    docs = [{"id": f"doc_{i}", "text": c["text"]} for i, c in enumerate(all_chunks)]
    bm25 = BM25()
    bm25.index(docs)
    return bm25, all_chunks


# ── File presence tests ───────────────────────────────────────────────────────

class TestCSEFilePresence:
    def test_chunks_full_json_exists(self):
        """data/processed/easa_cse/chunks_full.json must exist on disk."""
        assert CSE_CHUNKS_PATH.exists(), f"Missing: {CSE_CHUNKS_PATH}"

    def test_chunks_json_exists(self):
        """data/processed/easa_cse/chunks.json (condensed) must also exist."""
        condensed = ROOT / "data/processed/easa_cse/chunks.json"
        assert condensed.exists(), f"Missing condensed chunks: {condensed}"

    def test_cse_structure_json_exists(self):
        """CS-E_structure.json for PageIndex must exist."""
        struct = ROOT / "data/processed/CS-E_structure.json"
        assert struct.exists(), f"Missing CS-E structure: {struct}"


# ── Raw file quality tests ────────────────────────────────────────────────────

class TestCSERawChunks:
    def test_minimum_chunk_count(self, raw_cse_chunks):
        """chunks_full.json must contain >= 200 CS-E chunks."""
        assert len(raw_cse_chunks) >= 200, (
            f"Expected >= 200 CS-E chunks, got {len(raw_cse_chunks)}"
        )

    def test_all_chunks_have_text(self, raw_cse_chunks):
        """Every chunk must have a non-empty 'text' field."""
        empty = [c for c in raw_cse_chunks if not c.get("text", "").strip()]
        assert len(empty) == 0, f"{len(empty)} CS-E chunks have empty text"

    def test_all_chunks_have_metadata(self, raw_cse_chunks):
        """Every chunk must have a 'metadata' dict."""
        missing = [c for c in raw_cse_chunks if not isinstance(c.get("metadata"), dict)]
        assert len(missing) == 0, f"{len(missing)} CS-E chunks missing metadata"

    def test_authority_is_easa(self, raw_cse_chunks):
        """All CS-E chunks must have metadata.authority = 'EASA'."""
        wrong = [c for c in raw_cse_chunks
                 if c.get("metadata", {}).get("authority") != "EASA"]
        assert len(wrong) == 0, (
            f"{len(wrong)}/{len(raw_cse_chunks)} CS-E chunks have wrong authority. "
            f"Sample: {[c.get('metadata', {}).get('authority') for c in wrong[:3]]}"
        )

    def test_jurisdiction_is_eu(self, raw_cse_chunks):
        """All CS-E chunks must have metadata.jurisdiction = 'EU'."""
        wrong = [c for c in raw_cse_chunks
                 if c.get("metadata", {}).get("jurisdiction") != "EU"]
        assert len(wrong) == 0, (
            f"{len(wrong)}/{len(raw_cse_chunks)} CS-E chunks have wrong jurisdiction"
        )

    def test_source_field_contains_cse(self, raw_cse_chunks):
        """metadata.source must contain 'CS-E' for all chunks."""
        wrong = [c for c in raw_cse_chunks
                 if "CS-E" not in c.get("metadata", {}).get("source", "")]
        assert len(wrong) == 0, (
            f"{len(wrong)} CS-E chunks have unexpected source: "
            f"{set(c.get('metadata', {}).get('source') for c in wrong)}"
        )

    def test_all_chunks_have_section(self, raw_cse_chunks):
        """All chunks must have a non-empty section in metadata."""
        missing = [c for c in raw_cse_chunks
                   if not c.get("metadata", {}).get("section", "").strip()]
        assert len(missing) == 0, (
            f"{len(missing)}/{len(raw_cse_chunks)} CS-E chunks missing 'section' metadata"
        )


# ── Ingestion into collect_indexable_chunks ───────────────────────────────────

class TestCSEIngestion:
    def test_cse_present_in_index(self, cse_chunks):
        """collect_indexable_chunks() must return >= 200 CS-E chunks."""
        assert len(cse_chunks) >= 200, (
            f"Only {len(cse_chunks)} CS-E chunks in index. "
            f"Check collect_indexable_chunks() step 3 (EASA CS-E)."
        )

    def test_total_chunks_covers_all_sources(self, all_chunks):
        """Total chunk count must be >= 600 (CCAR + FAR-33 + CS-E + AC sources)."""
        assert len(all_chunks) >= 600, (
            f"Expected >= 600 total chunks, got {len(all_chunks)}. "
            f"CS-E may not be loading correctly."
        )

    def test_all_three_jurisdictions_present(self, source_counts):
        """CCAR (CAAC), FAR-33 (FAA), CS-E (EASA) must all be present in index."""
        ccar = sum(v for k, v in source_counts.items() if "CCAR" in k or "ccar" in k.lower())
        far33 = source_counts.get("FAR-33", 0)
        cse = sum(v for k, v in source_counts.items() if "CS-E" in k)
        assert ccar >= 10, f"CCAR-33 too few in index: {ccar}"
        assert far33 >= 60, f"FAR-33 too few in index: {far33}"
        assert cse >= 200, f"CS-E too few in index: {cse}"


# ── BM25 Retrievability tests ─────────────────────────────────────────────────

class TestCSEBM25Retrieval:
    def test_bm25_retrieves_cse_for_turbine_query(self, bm25_index, all_chunks):
        """BM25 search for 'turbine CS-E engine certification' must hit CS-E chunks."""
        bm25, _ = bm25_index
        results = bm25.search("turbine CS-E engine certification specifications", top_k=10)
        id_to_chunk = {f"doc_{i}": c for i, c in enumerate(all_chunks)}
        top = [id_to_chunk[doc_id] for doc_id, _ in results if doc_id in id_to_chunk]
        cse_hits = [c for c in top if "CS-E" in c.get("metadata", {}).get("source", "")]
        assert len(cse_hits) >= 1, (
            f"BM25 top-10 for turbine query returned no CS-E chunks. "
            f"Sources: {[c.get('metadata', {}).get('source') for c in top]}"
        )

    def test_bm25_cross_reg_surge_returns_multi_source(self, bm25_index, all_chunks):
        """
        Cross-regulation query 'surge stall CCAR FAR CS-E compressor' must
        return results from >= 2 different regulation bodies in top-15.
        """
        bm25, _ = bm25_index
        results = bm25.search("surge stall CCAR FAR CS-E compressor margin", top_k=15)
        id_to_chunk = {f"doc_{i}": c for i, c in enumerate(all_chunks)}
        top = [id_to_chunk[doc_id] for doc_id, _ in results if doc_id in id_to_chunk]

        bodies = set()
        for c in top:
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
            f"Cross-reg surge query hit only {len(bodies)} body/bodies: {bodies}. "
            f"Expected >= 2 of {{CAAC, FAA, EASA}}."
        )

    def test_bm25_easa_endurance_test_retrieval(self, bm25_index, all_chunks):
        """BM25 search for 'EASA endurance test CS-E 440' must return CS-E chunks."""
        bm25, _ = bm25_index
        results = bm25.search("EASA endurance test CS-E 440 engine certification", top_k=10)
        id_to_chunk = {f"doc_{i}": c for i, c in enumerate(all_chunks)}
        top = [id_to_chunk[doc_id] for doc_id, _ in results if doc_id in id_to_chunk]
        cse_hits = [c for c in top if "CS-E" in c.get("metadata", {}).get("source", "")]
        assert len(cse_hits) >= 1, (
            f"EASA endurance query returned no CS-E hits. "
            f"Sources: {[c.get('metadata', {}).get('source') for c in top]}"
        )
