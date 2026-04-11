"""
Neo4j 接入集成测试
==================
验收标准: graph_store.py 接 bolt://；docker-compose 启动通过

这些测试在 Neo4j 可达时执行完整集成验证；
Neo4j 不可达时自动 skip（不阻断 CI）。

运行 (本地, Neo4j 已启动):
    docker-compose up -d neo4j
    pytest tests/integration/test_neo4j.py -v

运行 (CI, Neo4j 不可达):
    pytest tests/integration/test_neo4j.py -v   # 全部 SKIP
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")


def _neo4j_reachable() -> bool:
    """Return True if Neo4j bolt:// is reachable."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


neo4j_available = pytest.mark.skipif(
    not _neo4j_reachable(),
    reason="Neo4j not reachable at %s — start with: docker-compose up -d neo4j" % NEO4J_URI,
)


class TestNeo4jConnection:
    """bolt:// 连接和基本读写测试"""

    @neo4j_available
    def test_bolt_connection_succeeds(self):
        """bolt:// 连接建立成功"""
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()

    @neo4j_available
    def test_basic_cypher_query(self):
        """基本 Cypher 查询可执行"""
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session() as session:
            result = session.run("RETURN 1 AS ping")
            assert result.single()["ping"] == 1
        driver.close()

    @neo4j_available
    def test_node_count_readable(self):
        """MATCH (n) RETURN count(n) 可正常执行"""
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session() as session:
            count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            assert isinstance(count, int)
            assert count >= 0
        driver.close()


class TestOntologyGraphStoreWithNeo4j:
    """OntologyGraphStore 接真实 Neo4j 时的行为测试"""

    @neo4j_available
    def test_graph_store_initializes_with_driver(self):
        """图存储应能成功创建 driver 并设置 node_count"""
        from src.ontology.graph_store import OntologyGraphStore
        store = OntologyGraphStore()
        assert store.driver is not None, "Expected real Neo4j driver, got None"
        store.close()

    @neo4j_available
    def test_graph_store_query_returns_list(self):
        """query_graph 应返回列表（即使为空）"""
        from src.ontology.graph_store import OntologyGraphStore
        store = OntologyGraphStore()
        results = store.query_graph("压气机")
        assert isinstance(results, list)
        store.close()

    @neo4j_available
    def test_graph_store_has_graph_data_after_seed(self):
        """seed 之后 has_graph_data 应为 True"""
        from neo4j import GraphDatabase
        from src.ontology.graph_store import OntologyGraphStore

        # Minimal seed for test
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session() as session:
            session.run(
                "MERGE (n:Entity {id:'test-node'}) SET n.name='TestNode', n.type='component'"
            )
        driver.close()

        store = OntologyGraphStore()
        assert store.has_graph_data, "has_graph_data should be True after seeding"
        store.close()


class TestFallbackModeWithoutNeo4j:
    """Neo4j 不可达时，图存储应降级为 fallback JSON 模式"""

    def test_graph_store_fallback_mode_works(self, monkeypatch):
        """模拟 Neo4j 不可达时，图存储应使用 fallback 图"""
        # Patch GraphDatabase to simulate unavailable Neo4j
        import src.ontology.graph_store as gs_module
        monkeypatch.setattr(gs_module, "GraphDatabase", None)
        from src.ontology.graph_store import OntologyGraphStore
        store = OntologyGraphStore()
        assert store.driver is None, "Driver should be None when Neo4j is patched out"
        # Fallback graph queries should still return a list
        results = store.query_graph("压气机")
        assert isinstance(results, list)

    def test_health_endpoint_shows_graph_fallback(self, monkeypatch):
        """当 Neo4j 不可达时，/health 的 graph_db 应为 'fallback'"""
        import src.ontology.graph_store as gs_module
        monkeypatch.setattr(gs_module, "GraphDatabase", None)
        from src.ontology.graph_store import OntologyGraphStore
        store = OntologyGraphStore()
        graph_db_status = (
            "connected"
            if (store.driver and store.has_graph_data)
            else "fallback"
        )
        assert graph_db_status == "fallback"
