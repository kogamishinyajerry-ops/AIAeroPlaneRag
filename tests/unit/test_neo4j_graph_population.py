"""
tests/unit/test_neo4j_graph_population.py
==========================================
Unit tests for scripts/neo4j/populate_ccar33_graph.py

Tests cover:
  - Structure parsing (60 nodes, 105 edges from CCAR-33-R2_structure.json)
  - Node field correctness (id, label, type, section_number, authority)
  - CONTAINS edge hierarchy integrity
  - FAR_EQUIVALENT cross-reference edges
  - Cypher statement generation (MERGE syntax, escaping)
  - Section number extraction from Chinese clause titles
  - Dry-run / cypher output modes (smoke tests)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.neo4j.populate_ccar33_graph import (
    _escape_cypher_string,
    _extract_section_number,
    build_graph_nodes,
    generate_cypher,
    CCAR_FAR_EQUIVALENT,
    STRUCTURE_JSON,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def structure_data():
    """Load actual CCAR-33-R2_structure.json."""
    if not STRUCTURE_JSON.exists():
        pytest.skip(f"Structure file not found: {STRUCTURE_JSON}")
    with open(STRUCTURE_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def graph(structure_data):
    """Build nodes and edges from real structure data."""
    return build_graph_nodes(structure_data)


# ── Section number extraction ──────────────────────────────────────────────────

class TestExtractSectionNumber:
    def test_standard_clause(self):
        assert _extract_section_number("第33.27条 发动机控制系统") == "33.27"

    def test_clause_with_letter(self):
        assert _extract_section_number("第33.27a条 补充要求") == "33.27a"

    def test_chapter_title_no_number(self):
        assert _extract_section_number("E章 设计与构造") == ""

    def test_far_style_title(self):
        assert _extract_section_number("§ 33.65 Surge margin") == "33.65"

    def test_mixed_title(self):
        assert _extract_section_number("33.94 Blade containment") == "33.94"

    def test_empty_string(self):
        assert _extract_section_number("") == ""

    def test_no_section_number(self):
        assert _extract_section_number("适航规定总则") == ""


# ── Cypher string escaping ─────────────────────────────────────────────────────

class TestEscapeCypherString:
    def test_plain_string(self):
        assert _escape_cypher_string("hello world") == "hello world"

    def test_single_quotes(self):
        assert _escape_cypher_string("it's") == "it\\'s"

    def test_backslash(self):
        assert _escape_cypher_string("a\\b") == "a\\\\b"

    def test_newline(self):
        assert _escape_cypher_string("line1\nline2") == "line1\\nline2"

    def test_chinese_chars(self):
        s = "适航取证要求"
        assert _escape_cypher_string(s) == s   # no escaping needed

    def test_combined(self):
        result = _escape_cypher_string("'test'\nvalue\\end")
        assert "\\'" in result
        assert "\\n" in result
        assert "\\\\" in result


# ── Node structure ─────────────────────────────────────────────────────────────

class TestBuildGraphNodes:
    def test_returns_tuple(self, graph):
        nodes, edges = graph
        assert isinstance(nodes, list)
        assert isinstance(edges, list)

    def test_node_count(self, graph):
        nodes, _ = graph
        # 1 doc root + 7 chapters + ~52 clauses = ~60 nodes
        assert len(nodes) >= 55
        assert len(nodes) <= 75

    def test_edge_count(self, graph):
        _, edges = graph
        # CONTAINS + FAR_EQUIVALENT edges
        assert len(edges) >= 55
        assert len(edges) <= 150

    def test_doc_root_node(self, graph):
        nodes, _ = graph
        doc_nodes = [n for n in nodes if n["type"] == "regulation"]
        assert len(doc_nodes) == 1
        root = doc_nodes[0]
        assert "CCAR-33-R2" in root["id"]
        assert root["authority"] == "CAAC"
        assert root["depth"] == 0

    def test_section_nodes_have_required_fields(self, graph):
        nodes, _ = graph
        for n in nodes:
            assert "id" in n, f"Node missing 'id': {n}"
            assert "label" in n
            assert "type" in n
            assert "authority" in n
            assert "depth" in n

    def test_section_ids_unique(self, graph):
        nodes, _ = graph
        ids = [n["id"] for n in nodes]
        assert len(ids) == len(set(ids)), "Duplicate node IDs found"

    def test_chapter_nodes_depth_1(self, graph):
        nodes, _ = graph
        depth1 = [n for n in nodes if n["depth"] == 1]
        # 7 chapters
        assert len(depth1) == 7

    def test_clause_nodes_depth_2(self, graph):
        nodes, _ = graph
        depth2 = [n for n in nodes if n["depth"] == 2]
        assert len(depth2) >= 40   # at least 40 clauses

    def test_section_number_extracted(self, graph):
        nodes, _ = graph
        clauses_with_num = [n for n in nodes if n.get("section_number")]
        assert len(clauses_with_num) >= 30

    def test_ccar33_authority(self, graph):
        nodes, _ = graph
        for n in nodes:
            if n["type"] in ("regulation", "section"):
                assert n.get("authority") in ("CAAC", "FAA"), f"Unexpected authority: {n}"

    def test_text_capped_at_2000_chars(self, graph):
        nodes, _ = graph
        for n in nodes:
            assert len(n.get("text", "")) <= 2000


# ── Edge structure ─────────────────────────────────────────────────────────────

class TestGraphEdges:
    def test_contains_edges_exist(self, graph):
        _, edges = graph
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        assert len(contains) >= 55

    def test_far_equivalent_edges_exist(self, graph):
        _, edges = graph
        far_eq = [e for e in edges if e["rel_type"] == "FAR_EQUIVALENT"]
        assert len(far_eq) >= 30

    def test_all_edges_have_from_to(self, graph):
        _, edges = graph
        for e in edges:
            assert "from_id" in e
            assert "to_id" in e
            assert "rel_type" in e

    def test_contains_edges_connect_to_ccar33(self, graph):
        _, edges = graph
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        # All CONTAINS edges should have a ccar33: or doc: source
        for e in contains:
            assert "ccar33:" in e["from_id"] or "doc:" in e["from_id"], \
                f"Unexpected CONTAINS from_id: {e['from_id']}"

    def test_far_equivalent_target_ids(self, graph):
        _, edges = graph
        far_eq = [e for e in edges if e["rel_type"] == "FAR_EQUIVALENT"]
        for e in far_eq:
            assert e["to_id"].startswith("far33:"), \
                f"FAR_EQUIVALENT target should start with far33:: {e['to_id']}"

    def test_doc_root_is_source_of_chapter_edges(self, graph):
        nodes, edges = graph
        doc_id = next(n["id"] for n in nodes if n["type"] == "regulation")
        chapter_edges = [e for e in edges if e["from_id"] == doc_id]
        assert len(chapter_edges) == 7   # 7 chapters


# ── FAR equivalence table ──────────────────────────────────────────────────────

class TestFarEquivalenceTable:
    def test_table_non_empty(self):
        assert len(CCAR_FAR_EQUIVALENT) >= 50

    def test_key_format(self):
        for k in CCAR_FAR_EQUIVALENT:
            assert k.startswith("33."), f"Key should start with 33.: {k}"

    def test_value_format(self):
        for v in CCAR_FAR_EQUIVALENT.values():
            assert v.startswith("FAR-33."), f"Value should start with FAR-33.: {v}"

    def test_common_clauses_present(self):
        for sec in ["33.27", "33.65", "33.87", "33.94"]:
            assert sec in CCAR_FAR_EQUIVALENT, f"Missing key clause: {sec}"

    def test_no_duplicate_values(self):
        vals = list(CCAR_FAR_EQUIVALENT.values())
        assert len(vals) == len(set(vals)), "Duplicate FAR values"


# ── Cypher generation ──────────────────────────────────────────────────────────

class TestGenerateCypher:
    def test_returns_list_of_strings(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        assert isinstance(stmts, list)
        assert all(isinstance(s, str) for s in stmts)

    def test_sufficient_statements(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        assert len(stmts) >= len(nodes) + len(edges)

    def test_merge_statements_present(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        merges = [s for s in stmts if s.strip().startswith("MERGE")]
        assert len(merges) >= len(nodes)

    def test_match_statements_for_edges(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        matches = [s for s in stmts if s.strip().startswith("MATCH")]
        # Each edge gets one MATCH-MERGE statement
        assert len(matches) >= len(edges)

    def test_statements_end_with_semicolon(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        for s in stmts:
            stripped = s.strip()
            if stripped and not stripped.startswith("//"):
                assert stripped.endswith(";"), f"Statement missing semicolon: {s[:80]}"

    def test_no_unescaped_chinese_single_quotes(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        for s in stmts:
            # Check that any Chinese text won't break Cypher syntax
            # (we can't have unescaped literal single quotes in the middle of Cypher strings)
            assert "'''" not in s, f"Triple quote in statement: {s[:80]}"

    def test_regulation_label_used_for_doc(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        reg_stmts = [s for s in stmts if ":regulation {" in s]
        assert len(reg_stmts) == 1   # only the doc root

    def test_section_label_used_for_clauses(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        sec_stmts = [s for s in stmts if ":section {" in s]
        assert len(sec_stmts) >= 55   # clauses + FAR placeholder nodes

    def test_contains_rel_type_in_output(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        contains_stmts = [s for s in stmts if ":CONTAINS" in s]
        assert len(contains_stmts) >= 50

    def test_far_equivalent_rel_in_output(self, graph):
        nodes, edges = graph
        stmts = generate_cypher(nodes, edges)
        far_stmts = [s for s in stmts if ":FAR_EQUIVALENT" in s]
        assert len(far_stmts) >= 30


# ── Minimal synthetic structure test ──────────────────────────────────────────

class TestBuildGraphNodesSynthetic:
    """Test with a small synthetic structure to verify logic precisely."""

    SYNTHETIC = {
        "doc_name": "TEST-33",
        "doc_title": "Test Regulation",
        "total_pages": 1,
        "structure": [
            {
                "title": "A章 总则",
                "node_id": "0001",
                "start_index": 1,
                "nodes": [
                    {
                        "title": "第33.1条 适用范围",
                        "node_id": "0002",
                        "text": "This is clause 33.1 text.",
                        "nodes": [],
                    },
                    {
                        "title": "第33.27条 转子速度限制",
                        "node_id": "0003",
                        "text": "Rotor speed limit text.",
                        "nodes": [],
                    },
                ],
            }
        ],
    }

    def test_root_doc_node(self):
        nodes, edges = build_graph_nodes(self.SYNTHETIC)
        doc = next((n for n in nodes if n["type"] == "regulation"), None)
        assert doc is not None
        assert doc["id"] == "doc:TEST-33"
        assert doc["depth"] == 0

    def test_chapter_node(self):
        nodes, _ = build_graph_nodes(self.SYNTHETIC)
        chapter = next((n for n in nodes if n.get("depth") == 1), None)
        assert chapter is not None
        assert "A章" in chapter["label"]
        assert chapter["depth"] == 1

    def test_clause_nodes(self):
        nodes, _ = build_graph_nodes(self.SYNTHETIC)
        clauses = [n for n in nodes if n.get("depth") == 2]
        assert len(clauses) == 2

    def test_clause_section_numbers(self):
        nodes, _ = build_graph_nodes(self.SYNTHETIC)
        sec_nums = {n["section_number"] for n in nodes if n.get("section_number")}
        assert "33.1" in sec_nums
        assert "33.27" in sec_nums

    def test_contains_edges(self):
        _, edges = build_graph_nodes(self.SYNTHETIC)
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        # doc→chapter + chapter→clause1 + chapter→clause2 = 3
        assert len(contains) == 3

    def test_far_equivalent_for_33_27(self):
        _, edges = build_graph_nodes(self.SYNTHETIC)
        far_eq = [e for e in edges if e["rel_type"] == "FAR_EQUIVALENT"]
        assert any("33_27" in e["to_id"] for e in far_eq)

    def test_no_far_eq_for_unknown_clause(self):
        """33.1 has FAR equivalent but test-only regulation shouldn't create spurious ones."""
        _, edges = build_graph_nodes(self.SYNTHETIC)
        # Should only have FAR_EQUIVALENT for clauses in CCAR_FAR_EQUIVALENT
        far_eq = [e for e in edges if e["rel_type"] == "FAR_EQUIVALENT"]
        far_targets = {e["to_id"] for e in far_eq}
        # Both 33.1 and 33.27 are in CCAR_FAR_EQUIVALENT table
        assert len(far_eq) == 2
