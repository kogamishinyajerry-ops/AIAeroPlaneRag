"""
v0.7: Aviation Definitions Chunk Ingestion Tests
==================================================
Validates that aviation_definitions_chunks.json is correctly ingested by
collect_indexable_chunks() and that the definitions improve BM25 recall
for 'general' category golden set questions.

验收条件:
  1. aviation_definitions_chunks.json 存在且包含 ≥ 5 条定义
  2. collect_indexable_chunks() 总 chunk 数 ≥ 605 (原604 + 5条定义)
  3. 定义块包含 '核心机' / 'FADEC' / '活塞式发动机' 关键词
  4. BM25 对 '核心机' 查询能检索到定义块 (keyword hit)
  5. BM25 对 'FADEC' 查询能检索到定义块 (keyword hit)
  6. n-gram 扩展能从长中文句子中提取 '核心机' 作为候选词
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

DEFS_FILE = ROOT / "data" / "processed" / "aviation_definitions_chunks.json"


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def defs_chunks():
    assert DEFS_FILE.exists(), f"Missing definitions file: {DEFS_FILE}"
    return json.loads(DEFS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def all_chunks():
    from rag.vector_engine import collect_indexable_chunks
    return collect_indexable_chunks()


@pytest.fixture(scope="module")
def bm25_index(all_chunks):
    from rag.vector_engine import BM25
    docs = [{"id": f"d{i}", "text": c["text"]} for i, c in enumerate(all_chunks)]
    bm25 = BM25()
    bm25.index(docs)
    return bm25, {f"d{i}": c for i, c in enumerate(all_chunks)}


# ── File structure tests ──────────────────────────────────────────────────────

class TestDefinitionsFile:

    def test_file_exists(self, defs_chunks):
        assert isinstance(defs_chunks, list)

    def test_has_at_least_5_definitions(self, defs_chunks):
        assert len(defs_chunks) >= 5, f"Expected ≥5 definitions, got {len(defs_chunks)}"

    def test_each_chunk_has_text(self, defs_chunks):
        for i, chunk in enumerate(defs_chunks):
            assert "text" in chunk and chunk["text"].strip(), f"Chunk {i} missing text"

    def test_each_chunk_has_metadata(self, defs_chunks):
        for i, chunk in enumerate(defs_chunks):
            assert "metadata" in chunk, f"Chunk {i} missing metadata"

    def test_metadata_has_source(self, defs_chunks):
        for chunk in defs_chunks:
            assert "source" in chunk["metadata"], f"Missing 'source' in metadata: {chunk['metadata']}"

    def test_core_engine_definition_present(self, defs_chunks):
        texts = [c["text"] for c in defs_chunks]
        assert any("核心机" in t for t in texts), "No 核心机 definition found"

    def test_fadec_definition_present(self, defs_chunks):
        texts = [c["text"] for c in defs_chunks]
        assert any("FADEC" in t for t in texts), "No FADEC definition found"

    def test_piston_engine_definition_present(self, defs_chunks):
        texts = [c["text"] for c in defs_chunks]
        assert any("活塞" in t for t in texts), "No piston engine definition found"

    def test_chunk_ids_unique(self, defs_chunks):
        ids = [c["metadata"].get("chunk_id") for c in defs_chunks if "metadata" in c]
        ids_notnone = [i for i in ids if i]
        assert len(ids_notnone) == len(set(ids_notnone)), "Duplicate chunk_ids found"


# ── Ingestion tests ───────────────────────────────────────────────────────────

class TestDefinitionsIngestion:

    def test_total_chunks_includes_definitions(self, all_chunks):
        """collect_indexable_chunks should return ≥ 609 chunks (604 + ≥5 definitions)."""
        assert len(all_chunks) >= 609, (
            f"Expected ≥609 total chunks, got {len(all_chunks)}"
        )

    def test_definitions_source_in_chunks(self, all_chunks):
        """At least one chunk should have source='AviationDefinitions'."""
        sources = [c["metadata"].get("source", "") for c in all_chunks]
        assert "AviationDefinitions" in sources, (
            "No AviationDefinitions chunk found in collect_indexable_chunks()"
        )

    def test_core_engine_text_in_all_chunks(self, all_chunks):
        texts = " ".join(c["text"] for c in all_chunks)
        assert "核心机" in texts

    def test_fadec_text_in_all_chunks(self, all_chunks):
        texts = " ".join(c["text"] for c in all_chunks)
        assert "FADEC" in texts


# ── BM25 recall tests ─────────────────────────────────────────────────────────

class TestDefinitionsBM25Recall:
    """Verify definitions chunks are retrieved for definitional queries."""

    def _search_top_k(self, bm25_index, query: str, k: int = 5) -> list[dict]:
        from rag.vector_engine import expand_mixed_query
        bm25, cmap = bm25_index
        expanded = expand_mixed_query(query)
        seen, results = set(), []
        for term in [query] + expanded:
            for did, _ in bm25.search(term, top_k=k):
                if did not in seen:
                    seen.add(did)
                    if did in cmap:
                        results.append(cmap[did])
        return results[:k]

    def test_core_engine_query_hits_definition(self, bm25_index):
        """'核心机' query must retrieve a chunk containing '核心机'."""
        results = self._search_top_k(bm25_index, "什么是燃气涡轮发动机的核心机？")
        texts = " ".join(c["text"] for c in results)
        assert "核心机" in texts, (
            f"BM25 top-5 for '核心机' query did not hit any chunk with '核心机'\n"
            f"Top sources: {[c['metadata'].get('source') for c in results]}"
        )

    def test_fadec_query_hits_definition(self, bm25_index):
        """'FADEC' query must retrieve a chunk containing 'FADEC'."""
        results = self._search_top_k(bm25_index, "发动机控制系统的FADEC是什么意思？")
        texts = " ".join(c["text"] for c in results)
        assert "FADEC" in texts, (
            f"BM25 top-5 for 'FADEC' query did not hit any chunk with 'FADEC'\n"
            f"Top sources: {[c['metadata'].get('source') for c in results]}"
        )

    def test_piston_vs_turbine_query_hits_definition(self, bm25_index):
        """活塞vs燃气涡轮 query must retrieve relevant chunk."""
        results = self._search_top_k(
            bm25_index, "燃气涡轮发动机与活塞式发动机在适航要求上有什么本质区别？"
        )
        texts = " ".join(c["text"] for c in results)
        has_turbine = "燃气涡轮" in texts or "涡轮" in texts
        has_piston = "活塞" in texts
        assert has_turbine and has_piston, (
            f"Query should hit chunks with both turbine+piston content. "
            f"has_turbine={has_turbine}, has_piston={has_piston}"
        )


# ── n-gram extraction tests ───────────────────────────────────────────────────

class TestNGramExpansion:
    """Verify expand_mixed_query extracts sub-terms via sliding n-gram."""

    def test_heji_extracted_from_long_sentence(self):
        from rag.vector_engine import expand_mixed_query
        expanded = expand_mixed_query("什么是燃气涡轮发动机的核心机？")
        assert "核心机" in expanded, f"'核心机' not found in expanded: {expanded[:10]}"

    def test_fadec_extracted_via_en_part(self):
        from rag.vector_engine import expand_mixed_query
        expanded = expand_mixed_query("发动机控制系统的FADEC是什么意思？")
        expanded_lower = [t.lower() for t in expanded]
        assert "fadec" in expanded_lower, f"'FADEC' not found in expanded: {expanded[:10]}"

    def test_core_engine_synonym_from_heji(self):
        from rag.vector_engine import expand_mixed_query
        expanded = expand_mixed_query("什么是燃气涡轮发动机的核心机？")
        en_hits = [t for t in expanded if "core" in t.lower() or "gas core" in t.lower()]
        assert en_hits, f"No English 'core engine' synonyms in expanded: {expanded[:15]}"

    def test_gas_turbine_extracted_from_sentence(self):
        from rag.vector_engine import expand_mixed_query
        expanded = expand_mixed_query("燃气涡轮发动机的适航要求")
        has_zh = any("燃气涡轮" in t for t in expanded)
        has_en = any("gas turbine" in t.lower() for t in expanded)
        assert has_zh or has_en, f"No gas turbine term found in expanded: {expanded[:12]}"
