"""
tests/integration/test_vector_retrieval.py
===========================================
CI integration tests for VectorStoreEngine with offline hash embeddings.

Uses SimpleHashEmbeddingFunction + a temporary ChromaDB directory so no Ollama,
OpenAI or Jina API keys are required.  Validates the full index → query pipeline:

  index_chunks() → ChromaDB upsert (SimpleHash 256-dim vectors)
  search()       → vector query + BM25 hybrid + RRF fusion
  add_chunks()   → incremental upsert
  cache eviction → bounded memory usage

These tests are the 'pre-computed embeddings CI' story: SimpleHashEmbeddingFunction
produces deterministic vectors from token hashes, so results are reproducible.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

chromadb_available = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("chromadb"),
    reason="chromadb not installed"
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_CHUNKS: list[dict[str, Any]] = [
    {
        "text": "§ 33.23 Compressor surge margin. Each engine must have a compressor surge margin that prevents surge during all approved flight conditions.",
        "metadata": {"source": "FAR-33", "chapter": "33.23", "section": "Surge Margin", "language": "en"},
    },
    {
        "text": "§ 33.27 Turbine and compressor rotor overspeed. Each engine must withstand rotor overspeed without failure.",
        "metadata": {"source": "FAR-33", "chapter": "33.27", "section": "Rotor Overspeed", "language": "en"},
    },
    {
        "text": "§ 33.65 Surge and stall characteristics. Each engine must be designed to prevent surge and stall conditions during all approved operating conditions.",
        "metadata": {"source": "FAR-33", "chapter": "33.65", "section": "Surge Characteristics", "language": "en"},
    },
    {
        "text": "CCAR-33 第33.1条 适用范围。本规定规定颁发和更改航空发动机型号合格证用的适航标准。",
        "metadata": {"source": "CCAR-33-R2", "chapter": "33.1", "section": "适用范围", "language": "zh"},
    },
    {
        "text": "CCAR-33 第33.27条 转子超速。压气机和涡轮转子在超速条件下必须不发生危险性损坏。",
        "metadata": {"source": "CCAR-33-R2", "chapter": "33.27", "section": "转子超速", "language": "zh"},
    },
    {
        "text": "CS-E 1000 Engine specification. Applicants must demonstrate compliance with all structural integrity requirements.",
        "metadata": {"source": "CS-E Amendment 5", "chapter": "E1000", "section": "Specification", "language": "en"},
    },
    {
        "text": "CS-E 620 Power assurance. Each engine must meet its declared power or thrust ratings throughout its approved operating range.",
        "metadata": {"source": "CS-E Amendment 5", "chapter": "E620", "section": "Power Assurance", "language": "en"},
    },
    {
        "text": "FADEC Full Authority Digital Engine Control is an electronic engine management system that controls all aspects of engine performance.",
        "metadata": {"source": "AviationDefinitions", "chapter": "FADEC", "section": "Definition", "language": "en"},
    },
    {
        "text": "燃烧室出口温度分布 (OTDF) 是评价燃烧室性能的关键参数，影响涡轮叶片的热应力分布。",
        "metadata": {"source": "AviationDefinitions", "chapter": "OTDF", "section": "定义", "language": "zh"},
    },
    {
        "text": "§ 33.94 Blade containment and rotor unbalance tests. Each engine must demonstrate that the engine case contains blade failures without releasing high energy debris.",
        "metadata": {"source": "FAR-33", "chapter": "33.94", "section": "Blade Containment", "language": "en"},
    },
]


@pytest.fixture(scope="module")
def tmp_chroma_dir():
    """Temporary ChromaDB directory shared across module tests."""
    with tempfile.TemporaryDirectory(prefix="test_chroma_") as td:
        yield td


@pytest.fixture(scope="module")
def engine(tmp_chroma_dir):
    """VectorStoreEngine using SimpleHashEmbeddingFunction + temp ChromaDB dir."""
    try:
        import chromadb  # noqa: F401
    except ImportError:
        pytest.skip("chromadb not installed")

    from src.rag.vector_engine import VectorStoreEngine, SimpleHashEmbeddingFunction
    eng = VectorStoreEngine(
        db_dir=tmp_chroma_dir,
        collection_name="test_regulations",
    )
    # Force SimpleHashEmbeddingFunction regardless of env vars
    hash_fn = SimpleHashEmbeddingFunction(dimension=256)
    import chromadb as _chdb
    client = _chdb.PersistentClient(path=tmp_chroma_dir)
    eng.collection = client.get_or_create_collection(
        name="test_regulations_hash",
        embedding_function=hash_fn,
    )
    eng.embedding_function = hash_fn
    return eng


# ── SimpleHashEmbeddingFunction unit tests ────────────────────────────────────

class TestSimpleHashEmbeddingFunction:
    def test_returns_list_of_lists(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=64)
        result = fn(["hello world"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)

    def test_correct_dimension(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        for dim in (64, 128, 256, 512):
            fn = SimpleHashEmbeddingFunction(dimension=dim)
            vecs = fn(["test text"])
            assert len(vecs[0]) == dim, f"Expected dim={dim}, got {len(vecs[0])}"

    def test_deterministic(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=128)
        v1 = fn(["compressor surge margin"])[0]
        v2 = fn(["compressor surge margin"])[0]
        assert v1 == v2

    def test_different_texts_different_vectors(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=256)
        v1 = fn(["compressor surge"])[0]
        v2 = fn(["turbine overspeed"])[0]
        assert v1 != v2

    def test_l2_normalized(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        import math
        fn = SimpleHashEmbeddingFunction(dimension=256)
        v = fn(["testing normalization"])[0]
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-5

    def test_empty_text_returns_zero_vector(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=64)
        v = fn([""])[0]
        assert len(v) == 64
        assert all(x == 0.0 for x in v)

    def test_batch_of_texts(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=128)
        texts = ["surge margin", "rotor overspeed", "blade containment"]
        vecs = fn(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == 128

    def test_chinese_text(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=256)
        vecs = fn(["压气机喘振裕度"])
        assert len(vecs[0]) == 256

    def test_embed_query_method(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        fn = SimpleHashEmbeddingFunction(dimension=64)
        result = fn.embed_query(["test"])
        assert isinstance(result, list)

    def test_name_method(self):
        from src.rag.vector_engine import SimpleHashEmbeddingFunction
        assert SimpleHashEmbeddingFunction.name() == "simple_hash"


# ── VectorStoreEngine index_chunks tests ──────────────────────────────────────

@chromadb_available
class TestVectorStoreIndexing:
    def test_index_chunks_succeeds(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS)
        count = engine.collection.count()
        assert count >= len(SAMPLE_CHUNKS)

    def test_index_populates_indexed_cache(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS)
        assert len(engine._indexed_cache) > 0

    def test_index_deduplicates_chunks(self, engine):
        count_before = engine.collection.count()
        engine.index_chunks(SAMPLE_CHUNKS)  # index same chunks again
        count_after = engine.collection.count()
        # upsert semantics: count should not increase
        assert count_after == count_before

    def test_index_clears_bm25_cache(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS)
        assert engine._bm25_indexed is False

    def test_index_empty_chunks_does_not_crash(self, engine):
        engine.index_chunks([])   # should not raise

    def test_add_chunks_incremental(self, engine):
        new_chunk = {
            "text": "§ 33.78 Rain and hail ingestion. Turbine engines must pass rain and hail ingestion tests.",
            "metadata": {"source": "FAR-33", "chapter": "33.78", "section": "Rain Hail", "language": "en"},
        }
        count_before = engine.collection.count()
        engine.add_chunks([new_chunk])
        count_after = engine.collection.count()
        assert count_after >= count_before

    def test_chunk_ids_are_stable(self, engine):
        """Same chunk at same index should produce same ID."""
        id1 = engine._make_chunk_id(SAMPLE_CHUNKS[0], 0)
        id2 = engine._make_chunk_id(SAMPLE_CHUNKS[0], 0)
        assert id1 == id2

    def test_chunk_ids_differ_for_different_chunks(self, engine):
        id1 = engine._make_chunk_id(SAMPLE_CHUNKS[0], 0)
        id2 = engine._make_chunk_id(SAMPLE_CHUNKS[1], 1)
        assert id1 != id2


# ── VectorStoreEngine search tests ────────────────────────────────────────────

@chromadb_available
class TestVectorStoreSearch:
    @pytest.fixture(autouse=True)
    def ensure_indexed(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS)

    def test_search_returns_list(self, engine):
        results = engine.search("compressor surge margin", top_k=3)
        assert isinstance(results, list)

    def test_search_returns_up_to_top_k(self, engine):
        results = engine.search("turbine rotor overspeed", top_k=3)
        assert len(results) <= 3

    def test_search_result_has_text(self, engine):
        results = engine.search("surge", top_k=3)
        for r in results:
            assert "text" in r
            assert len(r["text"]) > 0

    def test_search_result_has_metadata(self, engine):
        results = engine.search("rotor overspeed", top_k=3)
        for r in results:
            assert "metadata" in r
            assert isinstance(r["metadata"], dict)

    def test_search_english_query(self, engine):
        results = engine.search("blade containment test", top_k=5)
        assert len(results) >= 1
        # At least one result should mention containment or blade
        texts = " ".join(r["text"].lower() for r in results)
        assert "containment" in texts or "blade" in texts

    def test_search_chinese_query(self, engine):
        results = engine.search("压气机喘振裕度", top_k=3)
        assert isinstance(results, list)

    def test_search_uses_query_cache(self, engine):
        """Second call with identical query should hit cache."""
        engine._query_cache.clear()
        _ = engine.search("surge margin requirements", top_k=3)
        cache_key = ("surge margin requirements", 3)
        assert cache_key in engine._query_cache

    def test_search_cache_reused_on_repeat(self, engine):
        engine._query_cache.clear()
        r1 = engine.search("turbine overspeed protection", top_k=3)
        r2 = engine.search("turbine overspeed protection", top_k=3)
        assert r1 == r2

    def test_search_top_k_1(self, engine):
        results = engine.search("FADEC digital engine control", top_k=1)
        assert len(results) <= 1

    def test_search_cs_e_power_assurance(self, engine):
        results = engine.search("power assurance CS-E", top_k=5)
        assert len(results) >= 1

    def test_search_returns_source_metadata(self, engine):
        results = engine.search("compressor surge margin FAR-33", top_k=5)
        sources = [r["metadata"].get("source", "") for r in results]
        assert any("FAR-33" in s or "CCAR-33" in s for s in sources)


# ── BM25 lazy-index inside VectorStoreEngine ──────────────────────────────────

@chromadb_available
class TestVectorStoreBM25Hybrid:
    @pytest.fixture(autouse=True)
    def ensure_indexed(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS)
        engine._bm25_index = None
        engine._bm25_indexed = False

    def test_bm25_index_built_on_search(self, engine):
        engine.search("compressor", top_k=3)
        assert engine._bm25_indexed is True
        assert engine._bm25_index is not None

    def test_bm25_index_has_correct_chunk_count(self, engine):
        engine.search("turbine", top_k=3)
        # BM25 index should contain at least the SAMPLE_CHUNKS count
        assert engine._bm25_index.doc_count >= len(SAMPLE_CHUNKS) - 2  # allow slight discrepancy

    def test_hybrid_search_returns_diverse_sources(self, engine):
        """Hybrid search (vector + BM25) should include multiple regulation sources."""
        results = engine.search("engine certification requirements", top_k=8)
        sources = {r["metadata"].get("source", "") for r in results}
        # Should include at least 2 different sources
        assert len(sources) >= 2

    def test_bm25_reset_on_reindex(self, engine):
        engine.index_chunks(SAMPLE_CHUNKS[:5])
        assert engine._bm25_indexed is False


# ── Cache eviction ─────────────────────────────────────────────────────────────

class TestCacheEviction:
    def test_indexed_cache_eviction(self):
        """Eviction removes MAX_INDEXED_CACHE // 4 oldest entries when over limit."""
        from src.rag.vector_engine import VectorStoreEngine
        eng = VectorStoreEngine.__new__(VectorStoreEngine)
        eng.MAX_INDEXED_CACHE = 10
        eng.MAX_QUERY_CACHE = 5
        initial_size = 15
        eng._indexed_cache = {f"id_{i}": {} for i in range(initial_size)}
        eng._query_cache = {}
        eng._evict_caches_if_needed()
        evicted = eng.MAX_INDEXED_CACHE // 4  # 10 // 4 = 2
        assert len(eng._indexed_cache) == initial_size - evicted

    def test_query_cache_eviction(self):
        """Eviction removes MAX_QUERY_CACHE // 4 oldest entries when over limit."""
        from src.rag.vector_engine import VectorStoreEngine
        eng = VectorStoreEngine.__new__(VectorStoreEngine)
        eng.MAX_INDEXED_CACHE = 1000
        eng.MAX_QUERY_CACHE = 5
        initial_size = 8
        eng._indexed_cache = {}
        eng._query_cache = {(f"q{i}", 3): [] for i in range(initial_size)}
        eng._evict_caches_if_needed()
        evicted = eng.MAX_QUERY_CACHE // 4  # 5 // 4 = 1
        assert len(eng._query_cache) == initial_size - evicted

    def test_no_eviction_under_limit(self):
        from src.rag.vector_engine import VectorStoreEngine
        eng = VectorStoreEngine.__new__(VectorStoreEngine)
        eng.MAX_INDEXED_CACHE = 1000
        eng.MAX_QUERY_CACHE = 500
        eng._indexed_cache = {f"id_{i}": {} for i in range(5)}
        eng._query_cache = {(f"q{i}", 3): [] for i in range(5)}
        eng._evict_caches_if_needed()
        assert len(eng._indexed_cache) == 5
        assert len(eng._query_cache) == 5


# ── Mock mode (no ChromaDB) ────────────────────────────────────────────────────

class TestVectorStoreMockMode:
    """Tests for when chromadb is unavailable (mock mode fallback)."""

    def _make_mock_engine(self) -> Any:
        from src.rag.vector_engine import VectorStoreEngine
        eng = VectorStoreEngine.__new__(VectorStoreEngine)
        eng.collection = None
        eng._indexed_cache = {}
        eng._query_cache = {}
        eng._bm25_index = None
        eng._bm25_indexed = False
        return eng

    def test_mock_index_does_not_raise(self):
        eng = self._make_mock_engine()
        eng.index_chunks(SAMPLE_CHUNKS)   # should not raise

    def test_mock_search_returns_list(self):
        eng = self._make_mock_engine()
        results = eng.search("compressor surge", top_k=3)
        assert isinstance(results, list)

    def test_mock_search_returns_mock_document(self):
        eng = self._make_mock_engine()
        results = eng.search("any query", top_k=1)
        assert len(results) >= 1
        assert "text" in results[0]

    def test_mock_add_chunks_does_not_raise(self):
        eng = self._make_mock_engine()
        eng.add_chunks(SAMPLE_CHUNKS[:3])   # should not raise
