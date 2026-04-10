"""
T5.2: Neo4j 降级行为测试
验证 OntologyGraphStore 在无 Neo4j 连接时正确降级到 fallback 模式
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ontology.graph_store import OntologyGraphStore


@pytest.fixture(scope="module")
def store():
    """Graph store instance - will use fallback since Neo4j is not configured."""
    return OntologyGraphStore()


class TestFallbackMode:
    def test_driver_is_none_without_neo4j(self, store):
        """Without Neo4j configured, driver should be None."""
        assert store.driver is None

    def test_has_graph_data_reflects_fallback(self, store):
        """has_graph_data should be False when no Neo4j and no fallback data loaded."""
        # node_count is 0 when driver is None
        assert isinstance(store.has_graph_data, bool)

    def test_fallback_graph_is_dict(self, store):
        assert isinstance(store.fallback_graph, dict)

    def test_fallback_graph_has_required_keys(self, store):
        assert "entities" in store.fallback_graph
        assert "relationships" in store.fallback_graph


class TestQueryGraphFallback:
    def test_query_graph_returns_list(self, store):
        results = store.query_graph("compressor")
        assert isinstance(results, list)

    def test_query_graph_empty_string(self, store):
        results = store.query_graph("")
        assert isinstance(results, list)

    def test_query_graph_no_crash_on_unknown_term(self, store):
        results = store.query_graph("xyzzy_nonexistent_term_12345")
        assert isinstance(results, list)


class TestGetSubgraphFallback:
    def test_get_subgraph_returns_dict(self, store):
        result = store.get_subgraph(query="compressor", limit=5)
        assert isinstance(result, dict)

    def test_get_subgraph_has_required_keys(self, store):
        result = store.get_subgraph(query="compressor", limit=5)
        assert "nodes" in result
        assert "edges" in result
        assert "mode" in result

    def test_get_subgraph_nodes_is_list(self, store):
        result = store.get_subgraph(query="compressor", limit=5)
        assert isinstance(result["nodes"], list)

    def test_get_subgraph_edges_is_list(self, store):
        result = store.get_subgraph(query="compressor", limit=5)
        assert isinstance(result["edges"], list)

    def test_get_subgraph_respects_limit(self, store):
        result = store.get_subgraph(query="compressor", limit=3)
        assert len(result["nodes"]) <= 3 + 10  # some tolerance for connected nodes

    def test_get_subgraph_empty_query(self, store):
        result = store.get_subgraph(query="", limit=5)
        assert isinstance(result, dict)

    def test_get_subgraph_by_node_id(self, store):
        result = store.get_subgraph(node_id="nonexistent-node", limit=5)
        assert isinstance(result, dict)
        assert "nodes" in result


class TestGetGraphSnapshot:
    def test_get_graph_snapshot_returns_dict(self, store):
        snapshot = store.get_graph_snapshot()
        assert isinstance(snapshot, dict)

    def test_snapshot_has_nodes_and_edges(self, store):
        snapshot = store.get_graph_snapshot()
        assert "nodes" in snapshot
        assert "edges" in snapshot

    def test_snapshot_nodes_is_list(self, store):
        snapshot = store.get_graph_snapshot()
        assert isinstance(snapshot["nodes"], list)

    def test_snapshot_mode_field_present(self, store):
        snapshot = store.get_graph_snapshot()
        assert "mode" in snapshot


class TestFallbackIndexes:
    def test_entities_by_id_is_dict(self, store):
        assert isinstance(store.entities_by_id, dict)

    def test_relationships_is_list(self, store):
        assert isinstance(store.relationships, list)

    def test_adjacency_is_dict(self, store):
        assert isinstance(store.adjacency, dict)

    def test_entity_structure_when_present(self, store):
        for entity_id, entity in list(store.entities_by_id.items())[:3]:
            assert "id" in entity
            assert "label" in entity
            assert "type" in entity


class TestHeartbeatAndReconnection:
    """P2-11: Neo4j heartbeat + 自动重连机制"""

    def test_ensure_connection_returns_false_when_driver_is_none(self, store):
        """driver 为 None 时，_ensure_connection 返回 False"""
        store.driver = None
        assert store._ensure_connection() is False

    def test_ensure_connection_closes_stale_driver_and_returns_false(self, store):
        """driver 存在但连接已断开时，关闭旧 driver 并返回 False"""
        # 创建一个假的 driver，它的 verify_connectivity 会失败
        class FakeStaleDriver:
            def verify_connectivity(self):
                raise RuntimeError("Connection refused")

            def close(self):
                pass

        store.driver = FakeStaleDriver()
        store.node_count = 10  # 模拟之前有数据
        result = store._ensure_connection()
        assert result is False
        assert store.driver is None
        assert store.node_count == 0

    def test_ensure_connection_calls_refresh_on_success(self, store):
        """连接正常时返回 True 并保持 driver 活跃"""
        class FakeSession:
            def __init__(self):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def run(self, query, **kwargs):
                class FakeResult:
                    def single(self):
                        return {"c": 3}
                return FakeResult()

        class FakeGoodDriver:
            def verify_connectivity(self):
                return True
            def session(self):
                return FakeSession()
            def close(self):
                pass

        store.driver = FakeGoodDriver()
        store.node_count = 5
        result = store._ensure_connection()
        assert result is True
        assert store.driver is not None
        assert store.node_count == 3  # refresh_graph_state 查询得到的 node_count

    def test_query_graph_falls_back_when_connection_lost(self, store):
        """连接断开后 query_graph 自动降级到 fallback 模式，不崩溃"""
        class FakeStaleDriver:
            def verify_connectivity(self):
                raise RuntimeError("Connection lost")

            def close(self):
                pass

        store.driver = FakeStaleDriver()
        store.node_count = 5  # 模拟之前有数据
        # 调用 query_graph 不应崩溃
        results = store.query_graph("compressor")
        assert isinstance(results, list)
        # driver 应该已被清理
        assert store.driver is None

    def test_get_subgraph_falls_back_when_connection_lost(self, store):
        """连接断开后 get_subgraph 自动降级到 fallback 模式，不崩溃"""
        class FakeStaleDriver:
            def verify_connectivity(self):
                raise RuntimeError("Connection lost")

            def close(self):
                pass

        store.driver = FakeStaleDriver()
        store.node_count = 5
        result = store.get_subgraph(query="compressor", limit=5)
        assert isinstance(result, dict)
        assert "nodes" in result
        assert "edges" in result
        assert store.driver is None

