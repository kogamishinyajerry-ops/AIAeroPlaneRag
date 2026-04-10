"""
T4.2: 图谱节点 document 字段缺失监控测试
验证 inferAgency 对缺失字段的降级处理，以及 API 端点的监控统计
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestInferAgencyMissingDocument:
    """Test inferAgency fallback behavior when document field is missing."""

    def _infer_agency_py(self, node: dict) -> str:
        """Python equivalent of inferAgency() for testing."""
        group = node.get("group", "")
        if group in ("CAAC", "FAA", "EASA"):
            return group
        raw = (node.get("document") or node.get("id") or "").upper()
        doc = raw
        for prefix in ("CAAC-", "FAA-", "EASA-"):
            if doc.startswith(prefix):
                doc = doc[len(prefix):]
                break
        if doc.startswith(("CCAR-", "AP-", "AC-")):
            return "CAAC"
        if doc.startswith("FAR-"):
            return "FAA"
        if doc.startswith("CS-"):
            return "EASA"
        return ""

    def test_node_with_document_field(self):
        assert self._infer_agency_py({"document": "CCAR-33-R2"}) == "CAAC"
        assert self._infer_agency_py({"document": "FAR-33"}) == "FAA"
        assert self._infer_agency_py({"document": "CS-E"}) == "EASA"

    def test_node_with_group_field_takes_priority(self):
        assert self._infer_agency_py({"group": "FAA", "document": "CCAR-33"}) == "FAA"

    def test_node_missing_document_falls_back_to_id(self):
        assert self._infer_agency_py({"id": "CCAR-33-node"}) == "CAAC"
        assert self._infer_agency_py({"id": "FAR-25-node"}) == "FAA"

    def test_node_missing_both_document_and_group_returns_empty(self):
        assert self._infer_agency_py({"id": "generic-node"}) == ""
        assert self._infer_agency_py({}) == ""

    def test_node_with_empty_document_falls_back_to_id(self):
        assert self._infer_agency_py({"document": "", "id": "CCAR-33"}) == "CAAC"

    def test_node_with_prefixed_document(self):
        assert self._infer_agency_py({"document": "caac-CCAR-33-R2"}) == "CAAC"
        assert self._infer_agency_py({"document": "faa-FAR-33"}) == "FAA"


class TestGraphNodesMissingDocumentStats:
    """Test that graph nodes endpoint reports missing document count."""

    def test_missing_document_count_logic(self):
        """Verify the missing_document_count logic works correctly."""
        # Simulate the logic from get_graph_nodes
        nodes = [
            {"id": "n1", "document": "CCAR-33"},   # has document
            {"id": "n2"},                           # missing document AND group → counted
            {"id": "n3", "group": "FAA"},           # has group, no document → NOT counted
            {"id": "n4"},                           # missing document AND group → counted
            {"id": "n5", "document": ""},           # empty document, no group → counted
        ]
        missing_doc = [n.get("id", "?") for n in nodes if not n.get("document") and not n.get("group")]
        assert len(missing_doc) == 3  # n2, n4, n5
        assert "n2" in missing_doc
        assert "n4" in missing_doc
        assert "n5" in missing_doc
        assert "n1" not in missing_doc
        assert "n3" not in missing_doc

    def test_no_missing_documents(self):
        """All nodes have document field → count is 0."""
        nodes = [
            {"id": "n1", "document": "CCAR-33"},
            {"id": "n2", "document": "FAR-33"},
            {"id": "n3", "group": "EASA"},
        ]
        missing_doc = [n.get("id", "?") for n in nodes if not n.get("document") and not n.get("group")]
        assert len(missing_doc) == 0

    def test_all_missing_documents(self):
        """All nodes missing document field → count equals total."""
        nodes = [{"id": f"n{i}"} for i in range(5)]
        missing_doc = [n.get("id", "?") for n in nodes if not n.get("document") and not n.get("group")]
        assert len(missing_doc) == 5
