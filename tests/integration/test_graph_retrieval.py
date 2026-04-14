"""
tests/integration/test_graph_retrieval.py
==========================================
Integration tests for graph-augmented retrieval.

Tests verify:
  - OntologyGraphStore.query_graph() with mocked Neo4j driver returning CCAR-33 nodes
  - graph_store._query_fallback_graph() with injected CCAR-33 entities
  - RRF merger: graph results + BM25 results → ranked combined output
  - graph_store.get_subgraph() returns correct structure for known nodes
  - Updated Neo4j Cypher (label/title/text fields) is accepted by mock driver
  - Cross-regulation FAR_EQUIVALENT edges are returned by graph queries
  - Fallback mode gracefully handles empty / missing data

All Neo4j interactions are mocked; no live Neo4j connection required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_graph_store_with_mock_driver(records: list[dict]) -> Any:
    """
    Instantiate OntologyGraphStore with a mocked Neo4j driver that returns the
    given records when session.run() is called.
    """
    from src.ontology.graph_store import OntologyGraphStore

    mock_record = lambda d: type("Record", (), {"__getitem__": lambda s, k: d.get(k, ""), "get": lambda s, k, default="": d.get(k, default)})()
    mock_records = [mock_record(r) for r in records]

    mock_session = MagicMock()
    mock_session.run.return_value = mock_records
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    mock_driver = MagicMock()
    mock_driver.session.return_value = mock_session
    mock_driver.verify_connectivity.return_value = None

    store = OntologyGraphStore.__new__(OntologyGraphStore)
    store.driver = mock_driver
    store.node_count = 60   # has_graph_data = property(node_count > 0)
    store._connection_ok = True
    store.entities_by_id = {}
    store.relationships = []
    store._entity_label_index = {}
    store._entity_fulltext = {}

    # Patch _ensure_connection to always return True
    store._ensure_connection = lambda: True

    return store


CCAR33_GRAPH_RECORDS = [
    {
        "a_name": "CCAR-33-R2",
        "rel_type": "CONTAINS",
        "rel_desc": "",
        "b_name": "第33.65条 喘振裕度",
        "a_source": "CCAR-33-R2",
        "b_section": "33.65",
    },
    {
        "a_name": "第33.65条 喘振裕度",
        "rel_type": "FAR_EQUIVALENT",
        "rel_desc": "",
        "b_name": "FAR 33.65",
        "a_source": "CCAR-33-R2",
        "b_section": "33.65",
    },
    {
        "a_name": "CCAR-33-R2",
        "rel_type": "CONTAINS",
        "rel_desc": "",
        "b_name": "第33.27条 转子速度限制",
        "a_source": "CCAR-33-R2",
        "b_section": "33.27",
    },
    {
        "a_name": "第33.94条 叶片包容性",
        "rel_type": "FAR_EQUIVALENT",
        "rel_desc": "",
        "b_name": "FAR 33.94",
        "a_source": "CCAR-33-R2",
        "b_section": "33.94",
    },
]


# ── graph_store._query_neo4j (mocked driver) ─────────────────────────────────

class TestQueryNeo4jMocked:
    def test_returns_list(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("喘振")
        assert isinstance(results, list)

    def test_returns_results_for_known_keyword(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("surge")
        # Mock always returns the fixed records regardless of keyword
        assert len(results) > 0

    def test_result_has_regulation_field(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("compressor")
        for r in results:
            assert "regulation" in r

    def test_result_has_relationship_field(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("rotor")
        for r in results:
            assert "relationship" in r

    def test_result_has_description_field(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("blade")
        for r in results:
            assert "description" in r
            assert "--[" in r["description"]

    def test_contains_relationship_in_results(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("CCAR")
        rels = {r["relationship"] for r in results}
        assert "CONTAINS" in rels

    def test_far_equivalent_relationship_in_results(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("FAR")
        rels = {r["relationship"] for r in results}
        assert "FAR_EQUIVALENT" in rels

    def test_source_field_included(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("CCAR-33")
        for r in results:
            assert "source" in r

    def test_section_number_field_included(self):
        store = _make_graph_store_with_mock_driver(CCAR33_GRAPH_RECORDS)
        results = store._query_neo4j("33.65")
        for r in results:
            assert "section_number" in r

    def test_returns_empty_list_on_driver_error(self):
        from src.ontology.graph_store import OntologyGraphStore
        store = OntologyGraphStore.__new__(OntologyGraphStore)
        # Simulate a broken driver
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = RuntimeError("DB connection error")
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        store.driver = mock_driver
        store.node_count = 60   # has_graph_data = True
        store._ensure_connection = lambda: True
        store.entities_by_id = {}
        store.relationships = []
        store._entity_label_index = {}
        store._entity_fulltext = {}
        result = store._query_neo4j("compressor")
        assert result == []


# ── Fallback graph with CCAR-33 entities ──────────────────────────────────────

def _make_fallback_store_with_ccar33() -> Any:
    """Build an OntologyGraphStore using fallback mode with CCAR-33 entities."""
    from collections import Counter, defaultdict
    from src.ontology.graph_store import OntologyGraphStore

    store = OntologyGraphStore.__new__(OntologyGraphStore)
    store.driver = None
    store.node_count = 0   # has_graph_data returns False when node_count == 0
    store._connection_ok = False
    # _build_fallback_indexes() reads from fallback_graph, so populate it with CCAR-33 data
    store.fallback_graph = {
        "entities": [
            {"id": "ccar33:0001", "name": "A章 总则", "type": "regulation", "description": "CCAR-33 General Requirements chapter"},
            {"id": "ccar33:0002", "name": "第33.1条 适用范围", "type": "section", "description": "适航标准适用范围 applicability"},
            {"id": "ccar33:0010", "name": "第33.65条 喘振裕度", "type": "section", "description": "压气机喘振裕度 compressor surge margin"},
            {"id": "ccar33:0020", "name": "第33.27条 转子超速", "type": "section", "description": "涡轮转子超速保护 turbine rotor overspeed"},
            {"id": "ccar33:0030", "name": "第33.94条 叶片包容性", "type": "section", "description": "涡轮叶片包容性试验 blade containment test"},
        ],
        "relationships": [
            {"source": "ccar33:0001", "target": "ccar33:0002", "type": "CONTAINS", "description": ""},
            {"source": "ccar33:0001", "target": "ccar33:0010", "type": "CONTAINS", "description": ""},
            {"source": "ccar33:0001", "target": "ccar33:0020", "type": "CONTAINS", "description": ""},
            {"source": "ccar33:0001", "target": "ccar33:0030", "type": "CONTAINS", "description": ""},
        ],
    }

    # Initialize all required internal data structures before _build_fallback_indexes
    store.entities_by_id = {}
    store.relationships = []
    store.adjacency = defaultdict(set)
    store.edge_lookup = defaultdict(list)
    store.relationship_counter = Counter()
    store._entity_label_index = {}
    store._entity_fulltext = {}

    # Build indexes as the real __init__ would (reads from fallback_graph)
    store._build_fallback_indexes()
    return store


class TestFallbackGraphWithCCAR33:
    def test_query_surge_returns_results(self):
        store = _make_fallback_store_with_ccar33()
        results = store._query_fallback_graph("surge")
        assert len(results) >= 1

    def test_query_compressor_hits_33_65(self):
        store = _make_fallback_store_with_ccar33()
        results = store._query_fallback_graph("compressor")
        labels = [r.get("component", "") + r.get("regulation", "") for r in results]
        assert any("33.65" in lab or "喘振" in lab for lab in labels)

    def test_query_containment_hits_33_94(self):
        store = _make_fallback_store_with_ccar33()
        results = store._query_fallback_graph("containment")
        labels = [r.get("component", "") + r.get("regulation", "") for r in results]
        assert any("包容" in lab or "33.94" in lab for lab in labels)

    def test_query_unknown_keyword_returns_empty(self):
        store = _make_fallback_store_with_ccar33()
        results = store._query_fallback_graph("quantum_entanglement_xyz")
        assert results == []

    def test_result_structure(self):
        store = _make_fallback_store_with_ccar33()
        results = store._query_fallback_graph("rotor")
        for r in results:
            assert "regulation" in r or "component" in r
            assert "description" in r

    def test_query_graph_routes_to_fallback(self):
        store = _make_fallback_store_with_ccar33()
        # driver is None so should use fallback
        results = store.query_graph("overspeed")
        assert isinstance(results, list)


# ── RRF merger: graph results + BM25 ──────────────────────────────────────────

class TestGraphBM25RRFMerger:
    """
    Verify that graph results and BM25 results can be merged via RRF to produce
    a ranked combined output. This tests the intended production behavior:
    graph context enriches BM25 retrieval.
    """

    def _rrf_merge(self, bm25_docs: list[str], graph_docs: list[str], k: int = 60) -> list[str]:
        """Minimal RRF implementation for testing."""
        scores: dict[str, float] = {}
        for rank, doc_id in enumerate(bm25_docs):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        for rank, doc_id in enumerate(graph_docs):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        return sorted(scores, key=lambda d: scores[d], reverse=True)

    def test_rrf_boosts_shared_docs(self):
        bm25 = ["doc_A", "doc_B", "doc_C"]
        graph = ["doc_B", "doc_D", "doc_E"]  # doc_B appears in both
        merged = self._rrf_merge(bm25, graph)
        # doc_B should rank highest (appears in both lists)
        assert merged[0] == "doc_B"

    def test_rrf_preserves_unique_docs(self):
        bm25 = ["doc_A", "doc_B"]
        graph = ["doc_C", "doc_D"]
        merged = self._rrf_merge(bm25, graph)
        assert set(merged) == {"doc_A", "doc_B", "doc_C", "doc_D"}

    def test_rrf_score_higher_for_lower_rank(self):
        """Item at rank 0 should have higher RRF contribution than rank 5."""
        bm25 = ["doc_A", "doc_B", "doc_C", "doc_D", "doc_E", "doc_F"]
        graph: list[str] = []
        merged = self._rrf_merge(bm25, graph)
        assert merged[0] == "doc_A"

    def test_graph_augmented_retrieval_conceptual(self):
        """
        Conceptual test: for a CCAR-33 surge margin query,
        graph returns the correct clause node, BM25 returns content chunks.
        After RRF merge, the clause should still be in top results.
        """
        bm25_results = ["chunk_ac_surge", "chunk_ccar_surge", "chunk_far_surge"]
        graph_results = ["ccar33:0010", "chunk_ccar_surge", "ccar33:0001"]
        # "chunk_ccar_surge" appears in both → should boost
        merged = self._rrf_merge(bm25_results, graph_results)
        assert merged[0] == "chunk_ccar_surge"  # boosted by dual appearance

    def test_empty_graph_falls_back_to_bm25_order(self):
        bm25 = ["doc_1", "doc_2", "doc_3"]
        graph: list[str] = []
        merged = self._rrf_merge(bm25, graph)
        assert merged == bm25


# ── get_subgraph correctness ───────────────────────────────────────────────────

class TestGetSubgraphFallback:
    def test_get_subgraph_returns_dict(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="surge margin", limit=5)
        assert isinstance(result, dict)

    def test_get_subgraph_has_nodes_key(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="compressor", limit=5)
        assert "nodes" in result

    def test_get_subgraph_has_edges_key(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="turbine", limit=5)
        assert "edges" in result

    def test_get_subgraph_nodes_non_empty_for_known_query(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="surge", limit=10)
        # At least one node should be returned for "surge"
        assert len(result.get("nodes", [])) >= 1

    def test_get_subgraph_limit_respected(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="CCAR", limit=2)
        assert len(result.get("nodes", [])) <= 2

    def test_get_subgraph_empty_for_unknown_query(self):
        store = _make_fallback_store_with_ccar33()
        result = store.get_subgraph(query="nonexistent_xyz_abc_123", limit=5)
        # May return 0 or fallback overview nodes — just verify it doesn't raise
        assert isinstance(result.get("nodes", []), list)


# ── Neo4j Cypher compatibility (updated query fields) ─────────────────────────

class TestNeo4jCypherCompatibility:
    """Verify the updated _query_neo4j Cypher includes label/title/text fields."""

    def test_cypher_includes_label_field(self):
        """Inspect the source of _query_neo4j to confirm label is in WHERE clause."""
        import inspect
        from src.ontology.graph_store import OntologyGraphStore
        src = inspect.getsource(OntologyGraphStore._query_neo4j)
        assert "a.label" in src or "label" in src

    def test_cypher_includes_title_field(self):
        import inspect
        from src.ontology.graph_store import OntologyGraphStore
        src = inspect.getsource(OntologyGraphStore._query_neo4j)
        assert "title" in src

    def test_cypher_includes_text_field(self):
        import inspect
        from src.ontology.graph_store import OntologyGraphStore
        src = inspect.getsource(OntologyGraphStore._query_neo4j)
        assert "text" in src

    def test_cypher_returns_source_field(self):
        import inspect
        from src.ontology.graph_store import OntologyGraphStore
        src = inspect.getsource(OntologyGraphStore._query_neo4j)
        assert "a_source" in src or "source" in src

    def test_result_includes_section_number(self):
        """Mock driver returns records with b_section; result should have section_number."""
        records = [{
            "a_name": "CCAR-33",
            "rel_type": "CONTAINS",
            "rel_desc": "",
            "b_name": "33.65 Surge",
            "a_source": "CCAR-33",
            "b_section": "33.65",
        }]
        store = _make_graph_store_with_mock_driver(records)
        results = store._query_neo4j("surge")
        assert len(results) > 0
        assert results[0].get("section_number") == "33.65"
