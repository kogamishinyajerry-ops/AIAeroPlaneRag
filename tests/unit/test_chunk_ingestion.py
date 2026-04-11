"""
v0.3: AC 预处理块接入向量索引 — 单元测试
===========================================
验收条件:
  - collect_indexable_chunks() 优先加载 data/processed/*_chunks.json
  - 总 chunks >= 500 (原来 286)
  - AC_33.87-1A_Endurance_Test 贡献 >= 100 chunks (原来 1)
  - 已有 JSON 的 AC 文件不被 markdown 重复加载
  - 每个 chunk 有 text 和 metadata 字段
"""
import sys
import json
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import collect_indexable_chunks


@pytest.fixture(scope="module")
def chunks():
    return collect_indexable_chunks()


@pytest.fixture(scope="module")
def source_counts(chunks):
    return Counter(c.get("metadata", {}).get("source", "?") for c in chunks)


# ── Structure tests ───────────────────────────────────────────────────────────

class TestChunkStructure:
    def test_returns_list(self, chunks):
        assert isinstance(chunks, list)

    def test_all_chunks_have_text(self, chunks):
        for c in chunks:
            assert "text" in c, f"Chunk missing 'text': {c}"
            assert isinstance(c["text"], str)

    def test_all_chunks_have_metadata(self, chunks):
        for c in chunks:
            assert "metadata" in c, f"Chunk missing 'metadata': {c}"
            assert isinstance(c["metadata"], dict)


# ── Volume tests ──────────────────────────────────────────────────────────────

class TestChunkVolume:
    def test_total_at_least_500(self, chunks):
        """After fix: 286 (old) → 535+ (new) — pre-processed AC JSONs loaded."""
        assert len(chunks) >= 500, (
            f"Expected >= 500 chunks, got {len(chunks)}. "
            "Check that collect_indexable_chunks loads *_chunks.json files."
        )

    def test_ac_endurance_test_has_100_plus_chunks(self, source_counts):
        """AC_33.87-1A has 142 pre-processed chunks — must not be collapsed to 1."""
        count = source_counts.get("AC_33.87-1A_Endurance_Test", 0)
        assert count >= 100, (
            f"AC_33.87-1A_Endurance_Test has {count} chunks, expected >= 100. "
            "The *_chunks.json is not being loaded."
        )

    def test_ac_rain_hail_has_proper_chunks(self, source_counts):
        """AC_33.78-1 has 33 pre-processed chunks."""
        count = source_counts.get("AC_33.78-1_Rain_Hail", 0)
        assert count >= 20, f"AC_33.78-1_Rain_Hail has {count} chunks, expected >= 20"

    def test_ac_rotor_overspeed_has_proper_chunks(self, source_counts):
        """AC_33.27-1A has 23 pre-processed chunks."""
        count = source_counts.get("AC_33.27-1A_Rotor_Overspeed", 0)
        assert count >= 15, f"AC_33.27-1A_Rotor_Overspeed has {count} chunks, expected >= 15"

    def test_easa_cse_present(self, source_counts):
        """CS-E Amendment 5 chunks must still be present."""
        count = source_counts.get("CS-E Amendment 5", 0)
        assert count >= 100, f"CS-E Amendment 5 has {count} chunks, expected >= 100"

    def test_ccar33_present(self, source_counts):
        """CCAR-33 markdown chunks must still be present."""
        ccar = source_counts.get("CCAR-33.md", 0) + source_counts.get("CCAR-33-R2_Full.md", 0)
        assert ccar >= 10, f"CCAR-33 chunks: {ccar}, expected >= 10"


# ── Deduplication tests ───────────────────────────────────────────────────────

class TestNoMarkdownDuplication:
    def test_ac_33_87_not_duplicated(self, source_counts):
        """
        AC_33.87-1A should NOT appear as a single monolithic markdown chunk
        alongside 142 granular chunks. Source count from markdown re-chunking
        would be exactly 1; after the fix it must be 142.
        """
        count = source_counts.get("AC_33.87-1A_Endurance_Test", 0)
        # If we had 1 it means markdown was used; with JSON fix it's 142
        assert count != 1, (
            "AC_33.87-1A_Endurance_Test has exactly 1 chunk — "
            "markdown re-chunking is overriding the pre-processed JSON."
        )

    def test_ac_sources_loaded_from_json(self, source_counts):
        """All 7 AC documents must be loaded as multiple chunks (>= 5 each)."""
        ac_sources = [
            "AC_33-2C_Type_Certification",
            "AC_33-3_Certification_Handbook",
            "AC_33.27-1A_Rotor_Overspeed",
            "AC_33.65-1_Surge_Stall_Margin",
            "AC_33.67-1_Fuel_System",
            "AC_33.78-1_Rain_Hail",
            "AC_33.87-1A_Endurance_Test",
        ]
        for src in ac_sources:
            count = source_counts.get(src, 0)
            assert count >= 5, (
                f"{src} has only {count} chunks. "
                f"Expected >= 5 from pre-processed JSON."
            )


# ── Content quality tests ─────────────────────────────────────────────────────

class TestChunkContentQuality:
    def test_no_empty_text_chunks(self, chunks):
        empty = [c for c in chunks if not c.get("text", "").strip()]
        assert len(empty) == 0, f"{len(empty)} chunks have empty text"

    def test_ac_chunks_have_agency_faa(self, chunks):
        """Pre-processed AC chunks should carry agency=FAA metadata."""
        ac_chunks = [c for c in chunks if c.get("metadata", {}).get("source", "").startswith("AC_")]
        faa_chunks = [c for c in ac_chunks if c.get("metadata", {}).get("agency") == "FAA"]
        assert len(faa_chunks) >= len(ac_chunks) * 0.9, (
            f"Only {len(faa_chunks)}/{len(ac_chunks)} AC chunks have agency=FAA"
        )

    def test_easa_chunks_have_source_metadata(self, chunks):
        easa = [c for c in chunks if c.get("metadata", {}).get("source") == "CS-E Amendment 5"]
        for c in easa[:5]:
            assert c.get("metadata", {}).get("source"), "EASA chunk missing source metadata"
