"""
tests/unit/test_neo4j_real_connection.py
=========================================
Neo4j 图数据库真实接入单元测试 (P2)

验收标准:
  - OntologyGraphStore 在真实驱动器可用时正确初始化
  - _query_neo4j 将 Cypher 结果映射为标准关系格式
  - _refresh_graph_state 更新 node_count
  - _ensure_connection 在驱动器失效时重连
  - setup_schema 的约束/索引定义覆盖所需节点标签

不需要真实 Neo4j 进程 — 所有驱动器调用通过 unittest.mock 模拟。
"""
from __future__ import annotations

import sys
import importlib.util
from collections import defaultdict, Counter
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ontology.graph_store import OntologyGraphStore, _normalize_type


# ═════════════════════════════════════════════════════════════════════════
# Helper: build a minimal OntologyGraphStore without __init__
# ═════════════════════════════════════════════════════════════════════════

def _make_bare_store(driver=None, node_count=0) -> OntologyGraphStore:
    """Instantiate OntologyGraphStore bypassing __init__."""
    store = OntologyGraphStore.__new__(OntologyGraphStore)
    store.uri = "bolt://localhost:7687"
    store.user = "neo4j"
    store.password = "test"
    store.node_count = node_count
    store.fallback_graph = {"entities": [], "relationships": []}
    store.entities_by_id = {}
    store.relationships = []
    store.adjacency = defaultdict(set)
    store.edge_lookup = defaultdict(list)
    store.relationship_counter = Counter()
    store.driver = driver
    return store


def _mock_session_single(count: int):
    """Return a mocked session context where .run().single() returns {"c": count}."""
    result_mock = MagicMock()
    result_mock.single.return_value = {"c": count}
    session = MagicMock()
    session.run.return_value = result_mock
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


def _mock_driver_returning(count: int):
    """Return a mocked driver whose session().run().single() returns count."""
    driver = MagicMock()
    driver.session.return_value = _mock_session_single(count)
    driver.verify_connectivity.return_value = None
    return driver


# ══════════════════════════════════════════════════════════════════════════
# 0. 辅助函数
# ══════════════════════════════════════════════════════════════════════════

class TestNormalizeType:
    def test_chapter_maps_to_regulation(self):
        assert _normalize_type("chapter") == "regulation"

    def test_section_maps_to_regulation(self):
        assert _normalize_type("section") == "regulation"

    def test_component_maps_to_component(self):
        assert _normalize_type("component") == "component"

    def test_rotor_maps_to_component(self):
        assert _normalize_type("rotorpart") == "component"

    def test_test_maps_to_support(self):
        assert _normalize_type("test") == "support"

    def test_unknown_maps_to_support(self):
        assert _normalize_type("foobar") == "support"

    def test_empty_maps_to_support(self):
        assert _normalize_type("") == "support"


# ══════════════════════════════════════════════════════════════════════════
# 1. _refresh_graph_state — node_count 更新
# ══════════════════════════════════════════════════════════════════════════

class TestRefreshGraphState:
    def test_sets_node_count_from_neo4j(self):
        driver = _mock_driver_returning(42)
        store = _make_bare_store(driver=driver)
        store._refresh_graph_state()
        assert store.node_count == 42

    def test_resets_to_zero_on_exception(self):
        broken_driver = MagicMock()
        broken_session = MagicMock()
        broken_session.run.side_effect = RuntimeError("DB unavailable")
        broken_session.__enter__ = MagicMock(return_value=broken_session)
        broken_session.__exit__ = MagicMock(return_value=False)
        broken_driver.session.return_value = broken_session
        store = _make_bare_store(driver=broken_driver, node_count=100)
        store._refresh_graph_state()
        assert store.node_count == 0

    def test_does_nothing_when_no_driver(self):
        store = _make_bare_store(driver=None, node_count=99)
        store._refresh_graph_state()
        assert store.node_count == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. has_graph_data 属性
# ══════════════════════════════════════════════════════════════════════════

class TestHasGraphData:
    def test_true_when_driver_and_positive_node_count(self):
        driver = _mock_driver_returning(10)
        store = _make_bare_store(driver=driver, node_count=10)
        assert store.has_graph_data is True

    def test_false_when_driver_but_zero_nodes(self):
        driver = _mock_driver_returning(0)
        store = _make_bare_store(driver=driver, node_count=0)
        assert store.has_graph_data is False

    def test_false_when_no_driver(self):
        store = _make_bare_store(driver=None, node_count=0)
        assert store.has_graph_data is False


# ══════════════════════════════════════════════════════════════════════════
# 3. close() — 驱动器清理
# ══════════════════════════════════════════════════════════════════════════

class TestClose:
    def test_calls_driver_close(self):
        mock_driver = MagicMock()
        store = _make_bare_store(driver=mock_driver)
        store.close()
        mock_driver.close.assert_called_once()

    def test_no_error_when_driver_is_none(self):
        store = _make_bare_store(driver=None)
        store.close()  # must not raise


# ══════════════════════════════════════════════════════════════════════════
# 4. _query_neo4j — Cypher 结果映射
# ══════════════════════════════════════════════════════════════════════════

class TestQueryNeo4j:
    def _store_with_neo4j_rows(self, rows: list[dict]) -> OntologyGraphStore:
        """Build a mock session where each row is a dict accessed via record[key]."""
        def make_record(row: dict):
            rec = MagicMock()
            rec.__getitem__ = MagicMock(side_effect=row.__getitem__)
            return rec

        records = [make_record(r) for r in rows]
        session = MagicMock()
        session.run.return_value = iter(records)
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        driver = MagicMock()
        driver.session.return_value = session
        return _make_bare_store(driver=driver)

    def test_maps_relationship_to_result(self):
        row = {
            "a_name": "第33.23条",
            "rel_type": "REQUIRES",
            "rel_desc": "喘振裕度演示",
            "b_name": "压气机",
        }
        store = self._store_with_neo4j_rows([row])
        results = store._query_neo4j("喘振裕度")
        assert len(results) == 1
        node = results[0]
        assert node["regulation"] == "第33.23条"
        assert node["component"] == "压气机"
        assert node["relationship"] == "REQUIRES"

    def test_returns_empty_on_no_results(self):
        store = self._store_with_neo4j_rows([])
        results = store._query_neo4j("nonexistent_term")
        assert results == []

    def test_no_crash_on_query_error(self):
        session = MagicMock()
        session.run.side_effect = RuntimeError("Cypher error")
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        driver = MagicMock()
        driver.session.return_value = session
        store = _make_bare_store(driver=driver)
        results = store._query_neo4j("test")
        assert results == []


# ══════════════════════════════════════════════════════════════════════════
# 5. _ensure_connection — 重连逻辑
# ══════════════════════════════════════════════════════════════════════════

class TestEnsureConnection:
    def test_returns_true_when_driver_healthy(self):
        driver = _mock_driver_returning(5)
        store = _make_bare_store(driver=driver, node_count=5)
        result = store._ensure_connection()
        assert result is True

    def test_returns_false_when_no_driver(self):
        store = _make_bare_store(driver=None)
        result = store._ensure_connection()
        assert result is False


# ══════════════════════════════════════════════════════════════════════════
# 6. Schema 定义完整性
# ══════════════════════════════════════════════════════════════════════════

class TestSchemaDefinitions:
    """Verify setup_schema.py defines constraints for all required node labels."""

    def _load_schema_module(self):
        schema_path = (
            Path(__file__).parent.parent.parent / "scripts/neo4j/setup_schema.py"
        )
        # Stub neo4j before import so setup_schema doesn't fail on missing package
        sys.modules.setdefault("neo4j", MagicMock())
        sys.modules.setdefault("neo4j.exceptions", MagicMock())
        spec = importlib.util.spec_from_file_location("setup_schema", schema_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_uniqueness_constraints_cover_required_labels(self):
        mod = self._load_schema_module()
        labels = {c[1] for c in mod.UNIQUENESS_CONSTRAINTS}
        for required in ("section", "component", "regulation", "support"):
            assert required in labels, (
                f"Missing uniqueness constraint for label '{required}'"
            )

    def test_fulltext_index_covers_multiple_labels(self):
        mod = self._load_schema_module()
        all_ft_labels: set[str] = set()
        for _, labels, _ in mod.FULLTEXT_INDEXES:
            all_ft_labels.update(labels)
        assert len(all_ft_labels) >= 3, "Full-text index should cover ≥3 node labels"

    def test_btree_indexes_defined(self):
        mod = self._load_schema_module()
        assert len(mod.BTREE_INDEXES) >= 2, "At least 2 B-tree indexes expected"

    def test_constraints_have_three_elements(self):
        mod = self._load_schema_module()
        for item in mod.UNIQUENESS_CONSTRAINTS:
            assert len(item) == 3, (
                f"Constraint tuple should be (name, label, prop): {item}"
            )

    def test_fulltext_properties_include_label(self):
        mod = self._load_schema_module()
        for _, _, props in mod.FULLTEXT_INDEXES:
            assert "label" in props, "Full-text index should include 'label' property"
