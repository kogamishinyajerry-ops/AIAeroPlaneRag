"""
T4.3: PageIndex 树检索引擎单元测试
验证 search_by_keywords、get_node_by_id、get_tree_path 等核心功能
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.pageindex_engine import PageIndexEngine, TreeNode


STRUCTURE_PATH = str(Path(__file__).parent.parent.parent / "data/processed/CCAR-33-R2_structure.json")


@pytest.fixture(scope="module")
def engine():
    return PageIndexEngine(STRUCTURE_PATH)


class TestPageIndexEngineInit:
    def test_loads_nodes(self, engine):
        assert len(engine.node_map) > 0

    def test_has_tree_root(self, engine):
        assert len(engine.tree_root) > 0

    def test_node_map_contains_tree_nodes(self, engine):
        for node_id, node in list(engine.node_map.items())[:3]:
            assert isinstance(node, TreeNode)
            assert node.node_id == node_id

    def test_get_all_sections_returns_list(self, engine):
        sections = engine.get_all_sections()
        assert isinstance(sections, list)
        assert len(sections) > 0

    def test_sections_have_required_fields(self, engine):
        sections = engine.get_all_sections()
        for s in sections[:5]:
            assert "node_id" in s
            assert "title" in s


class TestSearchByKeywords:
    def test_returns_list(self, engine):
        results = engine.search_by_keywords("涡轮", top_k=3)
        assert isinstance(results, list)

    def test_respects_top_k(self, engine):
        results = engine.search_by_keywords("涡轮", top_k=2)
        assert len(results) <= 2

    def test_result_has_required_keys(self, engine):
        results = engine.search_by_keywords("涡轮叶片", top_k=3)
        assert len(results) > 0
        for r in results:
            assert "text" in r
            assert "metadata" in r
            assert "source" in r["metadata"]
            assert "search_method" in r["metadata"]

    def test_search_method_is_pageindex(self, engine):
        results = engine.search_by_keywords("压气机", top_k=3)
        for r in results:
            assert r["metadata"]["search_method"] == "pageindex_tree"

    def test_chinese_query_finds_results(self, engine):
        results = engine.search_by_keywords("压气机喘振裕度", top_k=3)
        assert len(results) >= 1

    def test_turbine_query_finds_results(self, engine):
        results = engine.search_by_keywords("涡轮叶片", top_k=3)
        assert len(results) >= 1

    def test_fuel_system_query(self, engine):
        results = engine.search_by_keywords("燃油系统", top_k=3)
        assert len(results) >= 1

    def test_empty_query_returns_empty_or_default(self, engine):
        results = engine.search_by_keywords("", top_k=3)
        assert isinstance(results, list)

    def test_results_have_score_in_metadata(self, engine):
        results = engine.search_by_keywords("涡轮", top_k=3)
        for r in results:
            assert "score" in r["metadata"]
            assert r["metadata"]["score"] >= 0

    def test_results_sorted_by_score(self, engine):
        results = engine.search_by_keywords("涡轮", top_k=5)
        if len(results) >= 2:
            scores = [r["metadata"]["score"] for r in results]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"

    def test_source_is_ccar33(self, engine):
        results = engine.search_by_keywords("压气机", top_k=3)
        for r in results:
            assert "CCAR" in r["metadata"]["source"] or "33" in r["metadata"]["source"]


class TestGetNodeById:
    def test_returns_node_for_valid_id(self, engine):
        node_ids = list(engine.node_map.keys())
        node = engine.get_node_by_id(node_ids[0])
        assert node is not None
        assert isinstance(node, TreeNode)

    def test_returns_none_for_invalid_id(self, engine):
        node = engine.get_node_by_id("nonexistent-node-xyz")
        assert node is None

    def test_returned_node_has_title(self, engine):
        node_ids = list(engine.node_map.keys())
        node = engine.get_node_by_id(node_ids[0])
        assert node.title


class TestGetTreePath:
    def test_returns_list(self, engine):
        node_ids = list(engine.node_map.keys())
        path = engine.get_tree_path(node_ids[0])
        assert isinstance(path, list)

    def test_path_contains_node_info(self, engine):
        node_ids = list(engine.node_map.keys())
        path = engine.get_tree_path(node_ids[0])
        if path:
            for item in path:
                assert "node_id" in item or "title" in item

    def test_invalid_id_returns_empty(self, engine):
        path = engine.get_tree_path("nonexistent-xyz")
        assert path == [] or path is None or isinstance(path, list)


class TestTreeNode:
    def test_from_dict_roundtrip(self):
        data = {
            "node_id": "test-001",
            "title": "测试节点",
            "start_index": 0,
            "end_index": 100,
            "summary": "测试摘要",
            "text": "测试内容",
            "nodes": []
        }
        node = TreeNode.from_dict(data)
        assert node.node_id == "test-001"
        assert node.title == "测试节点"
        assert node.text == "测试内容"

    def test_to_dict_has_required_keys(self):
        node = TreeNode(node_id="n1", title="标题", start_index=0)
        d = node.to_dict()
        assert "node_id" in d
        assert "title" in d
        assert "nodes" in d

    def test_nested_nodes(self):
        child = TreeNode(node_id="child", title="子节点", start_index=10)
        parent = TreeNode(node_id="parent", title="父节点", start_index=0, nodes=[child])
        assert len(parent.nodes) == 1
        assert parent.nodes[0].node_id == "child"


class TestLeafNodeContentEnrichment:
    """Acceptance tests for PageIndex content enrichment (scripts/enrich_pageindex.py)."""

    def test_majority_leaf_nodes_have_text(self, engine):
        """After enrichment, >= 80% of leaf nodes must have non-empty text."""
        leaf_nodes = [n for n in engine.node_map.values() if not n.nodes]
        with_text = [n for n in leaf_nodes if n.text]
        ratio = len(with_text) / len(leaf_nodes) if leaf_nodes else 0
        assert ratio >= 0.8, (
            f"Only {len(with_text)}/{len(leaf_nodes)} leaf nodes have text "
            f"({ratio:.0%} < 80%)."
        )

    def test_total_nodes_with_text_at_least_40(self, engine):
        """Overall: >= 40 nodes must have text."""
        total_with_text = sum(1 for n in engine.node_map.values() if n.text)
        assert total_with_text >= 40, (
            f"Only {total_with_text} nodes have text (< 40)."
        )

    def test_from_dict_reads_content_parts(self):
        """TreeNode.from_dict() must read content_parts into text when text is absent."""
        from rag.pageindex_engine import TreeNode
        node = TreeNode.from_dict({
            "node_id": "cp-001",
            "title": "第33.99条 测试条款",
            "start_index": 1,
            "content_parts": ["第一段正文。", "第二段正文。"],
        })
        assert node.text == "第一段正文。\n\n第二段正文。"

    def test_search_results_have_content_text(self, engine):
        """Search results should carry the enriched article text."""
        results = engine.search_by_keywords("涡轮", top_k=3)
        for r in results:
            assert len(r.get("text", "")) > 0, "Search result missing text content"
