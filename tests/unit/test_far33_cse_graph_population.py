"""
tests/unit/test_far33_cse_graph_population.py
=============================================
Unit tests for scripts/neo4j/populate_far33_cse_graph.py

Tests cover:
  - FAR-33 node / edge construction from FAR-33_structure.json
  - CS-E node / edge construction from CS-E_structure.json
  - Node ID formats (far33:33_27, cse:E_10, etc.)
  - Subpart / book container nodes (depth=1)
  - CONTAINS edge hierarchy integrity
  - FAR_HARMONISED cross-regulation edges (CS-E Book A/C → FAR-33 Subpart)
  - Cypher generation (MERGE + ON CREATE + ON MATCH syntax)
  - Synthetic structure validation for precise logic checks
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.neo4j.populate_far33_cse_graph import (
    build_far33_nodes,
    build_cse_nodes,
    generate_cypher,
    _escape_cypher_string,
    _far33_section_id,
    _cse_section_id,
    FAR33_STRUCTURE_JSON,
    CSE_STRUCTURE_JSON,
    CSE_FAR_HARMONISED,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def far33_data():
    if not FAR33_STRUCTURE_JSON.exists():
        pytest.skip(f"FAR-33 structure file not found: {FAR33_STRUCTURE_JSON}")
    with open(FAR33_STRUCTURE_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cse_data():
    if not CSE_STRUCTURE_JSON.exists():
        pytest.skip(f"CS-E structure file not found: {CSE_STRUCTURE_JSON}")
    with open(CSE_STRUCTURE_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def far33_graph(far33_data):
    return build_far33_nodes(far33_data)


@pytest.fixture(scope="module")
def cse_graph(cse_data):
    return build_cse_nodes(cse_data)


# ── ID helpers ────────────────────────────────────────────────────────────────

class TestIdHelpers:
    def test_far33_section_id_standard(self):
        assert _far33_section_id("33.27") == "far33:33_27"

    def test_far33_section_id_dot_replacement(self):
        assert _far33_section_id("33.201") == "far33:33_201"

    def test_cse_section_id_standard(self):
        assert _cse_section_id("E.10") == "cse:E_10"

    def test_cse_section_id_dot_replacement(self):
        assert _cse_section_id("E.130") == "cse:E_130"

    def test_escape_cypher_single_quote(self):
        assert _escape_cypher_string("it's") == "it\\'s"

    def test_escape_cypher_backslash(self):
        assert _escape_cypher_string("a\\b") == "a\\\\b"


# ── FAR-33 graph structure ────────────────────────────────────────────────────

class TestFar33GraphNodes:
    def test_returns_tuple(self, far33_graph):
        nodes, edges = far33_graph
        assert isinstance(nodes, list)
        assert isinstance(edges, list)

    def test_node_count(self, far33_graph):
        nodes, _ = far33_graph
        # 1 doc root + subpart nodes + section nodes
        assert len(nodes) >= 50
        assert len(nodes) <= 120

    def test_doc_root_exists(self, far33_graph):
        nodes, _ = far33_graph
        doc = next((n for n in nodes if n["type"] == "regulation"), None)
        assert doc is not None
        assert doc["id"] == "doc:FAR-33"
        assert doc["authority"] == "FAA"
        assert doc["depth"] == 0

    def test_subpart_nodes_exist(self, far33_graph):
        nodes, _ = far33_graph
        subparts = [n for n in nodes if n["id"].startswith("far33:subpart_")]
        assert len(subparts) >= 5  # at least 5 subparts with sections

    def test_subpart_depth_is_1(self, far33_graph):
        nodes, _ = far33_graph
        subparts = [n for n in nodes if n["id"].startswith("far33:subpart_")]
        for s in subparts:
            assert s["depth"] == 1, f"Subpart {s['id']} has depth {s['depth']}"

    def test_section_depth_is_2(self, far33_graph):
        nodes, _ = far33_graph
        sections = [n for n in nodes if n["id"].startswith("far33:33_")]
        assert len(sections) >= 30
        for s in sections:
            assert s["depth"] == 2, f"Section {s['id']} has depth {s['depth']}"

    def test_known_sections_present(self, far33_graph):
        nodes, _ = far33_graph
        ids = {n["id"] for n in nodes}
        for sec_num in ["33.1", "33.27", "33.65", "33.87", "33.94"]:
            expected_id = _far33_section_id(sec_num)
            assert expected_id in ids, f"Missing FAR-33 section {sec_num}"

    def test_all_nodes_have_required_fields(self, far33_graph):
        nodes, _ = far33_graph
        for n in nodes:
            assert "id" in n
            assert "label" in n
            assert "type" in n
            assert "authority" in n
            assert n["authority"] == "FAA"
            assert "depth" in n

    def test_no_duplicate_node_ids(self, far33_graph):
        nodes, _ = far33_graph
        ids = [n["id"] for n in nodes]
        assert len(ids) == len(set(ids)), "Duplicate node IDs in FAR-33 graph"

    def test_text_capped_at_2000_chars(self, far33_graph):
        nodes, _ = far33_graph
        for n in nodes:
            assert len(n.get("text", "")) <= 2000


class TestFar33GraphEdges:
    def test_contains_edges_exist(self, far33_graph):
        _, edges = far33_graph
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        assert len(contains) >= 40

    def test_all_edges_have_fields(self, far33_graph):
        _, edges = far33_graph
        for e in edges:
            assert "from_id" in e
            assert "to_id" in e
            assert "rel_type" in e

    def test_doc_root_is_source_of_subpart_edges(self, far33_graph):
        nodes, edges = far33_graph
        doc_id = "doc:FAR-33"
        doc_edges = [e for e in edges if e["from_id"] == doc_id]
        assert len(doc_edges) >= 5  # at least 5 subparts

    def test_subpart_is_source_of_section_edges(self, far33_graph):
        _, edges = far33_graph
        subpart_edges = [e for e in edges if e["from_id"].startswith("far33:subpart_")]
        assert len(subpart_edges) >= 30

    def test_no_self_loops(self, far33_graph):
        _, edges = far33_graph
        for e in edges:
            assert e["from_id"] != e["to_id"], f"Self-loop edge: {e}"


# ── CS-E graph structure ──────────────────────────────────────────────────────

class TestCseGraphNodes:
    def test_returns_tuple(self, cse_graph):
        nodes, edges = cse_graph
        assert isinstance(nodes, list)
        assert isinstance(edges, list)

    def test_node_count(self, cse_graph):
        nodes, _ = cse_graph
        # 1 doc root + 3 books + 158 sections
        assert len(nodes) >= 100
        assert len(nodes) <= 200

    def test_doc_root_exists(self, cse_graph):
        nodes, _ = cse_graph
        doc = next((n for n in nodes if n["type"] == "regulation"), None)
        assert doc is not None
        assert doc["id"] == "doc:CS-E"
        assert doc["authority"] == "EASA"
        assert doc["depth"] == 0

    def test_book_nodes_exist(self, cse_graph):
        nodes, _ = cse_graph
        books = [n for n in nodes if n["id"].startswith("cse:book_")]
        assert len(books) == 3  # Book A, B, C

    def test_book_depth_is_1(self, cse_graph):
        nodes, _ = cse_graph
        books = [n for n in nodes if n["id"].startswith("cse:book_")]
        for b in books:
            assert b["depth"] == 1

    def test_section_depth_is_2(self, cse_graph):
        nodes, _ = cse_graph
        # Section IDs now include book prefix: cse:A_E_10, cse:C_E_210 etc.
        sections = [n for n in nodes if re.search(r"cse:[ABC]_E_\d", n["id"])]
        assert len(sections) >= 50
        for s in sections:
            assert s["depth"] == 2

    def test_known_cse_sections_present(self, cse_graph):
        nodes, _ = cse_graph
        ids = {n["id"] for n in nodes}
        # CS-E section IDs include book prefix: cse:{book}_{section}
        for expected_id in ["cse:A_E_10", "cse:A_E_15"]:
            assert expected_id in ids, f"Missing CS-E section {expected_id}"

    def test_all_nodes_have_easa_authority(self, cse_graph):
        nodes, _ = cse_graph
        for n in nodes:
            assert n.get("authority") == "EASA"

    def test_no_duplicate_node_ids(self, cse_graph):
        nodes, _ = cse_graph
        ids = [n["id"] for n in nodes]
        assert len(ids) == len(set(ids))


class TestCseGraphEdges:
    def test_contains_edges_exist(self, cse_graph):
        _, edges = cse_graph
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        assert len(contains) >= 100

    def test_far_harmonised_edges_exist(self, cse_graph):
        _, edges = cse_graph
        harmonised = [e for e in edges if e["rel_type"] == "FAR_HARMONISED"]
        assert len(harmonised) >= 1

    def test_far_harmonised_source_ids(self, cse_graph):
        _, edges = cse_graph
        harmonised = [e for e in edges if e["rel_type"] == "FAR_HARMONISED"]
        for e in harmonised:
            assert e["from_id"].startswith("cse:book_")

    def test_far_harmonised_target_ids(self, cse_graph):
        _, edges = cse_graph
        harmonised = [e for e in edges if e["rel_type"] == "FAR_HARMONISED"]
        for e in harmonised:
            assert e["to_id"].startswith("far33:"), \
                f"FAR_HARMONISED target should start with far33:: {e['to_id']}"


# ── CSE_FAR_HARMONISED table ──────────────────────────────────────────────────

class TestCseFarHarmonisedTable:
    def test_table_non_empty(self):
        assert len(CSE_FAR_HARMONISED) >= 1

    def test_keys_are_single_letters(self):
        for k in CSE_FAR_HARMONISED:
            assert len(k) == 1 and k.isalpha()

    def test_values_start_with_subpart(self):
        for v in CSE_FAR_HARMONISED.values():
            assert v.startswith("Subpart"), f"Expected Subpart prefix: {v}"

    def test_book_a_maps_to_far33_subpart_a(self):
        assert "A" in CSE_FAR_HARMONISED
        assert "SubpartA" in CSE_FAR_HARMONISED["A"]


# ── Cypher generation ─────────────────────────────────────────────────────────

class TestGenerateCypher:
    def test_returns_list_of_strings(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        assert isinstance(stmts, list)
        assert all(isinstance(s, str) for s in stmts)

    def test_sufficient_statements(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        total_nodes = len(fn) + len(cn)
        total_edges = len(fe) + len(ce)
        assert len(stmts) >= total_nodes + total_edges

    def test_merge_statements_present(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        merges = [s for s in stmts if "MERGE" in s]
        assert len(merges) >= len(fn) + len(cn)

    def test_on_create_set_in_node_statements(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        on_create = [s for s in stmts if "ON CREATE SET" in s]
        assert len(on_create) >= len(fn) + len(cn)

    def test_on_match_set_in_node_statements(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        on_match = [s for s in stmts if "ON MATCH SET" in s]
        assert len(on_match) >= len(fn) + len(cn)

    def test_statements_end_with_semicolon(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        for s in stmts:
            stripped = s.strip()
            if stripped and not stripped.startswith("//"):
                assert stripped.endswith(";"), f"Missing semicolon: {s[:80]}"

    def test_far33_doc_root_in_output(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        doc_stmts = [s for s in stmts if "doc:FAR-33" in s]
        assert len(doc_stmts) >= 1

    def test_cse_doc_root_in_output(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        doc_stmts = [s for s in stmts if "doc:CS-E" in s]
        assert len(doc_stmts) >= 1

    def test_far_harmonised_rel_in_output(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        harmonised = [s for s in stmts if "FAR_HARMONISED" in s]
        assert len(harmonised) >= 1

    def test_contains_rel_in_output(self, far33_graph, cse_graph):
        fn, fe = far33_graph
        cn, ce = cse_graph
        stmts = generate_cypher(fn, fe, cn, ce)
        contains = [s for s in stmts if ":CONTAINS" in s]
        assert len(contains) >= 50


# ── Synthetic structure tests ─────────────────────────────────────────────────

class TestFar33SyntheticStructure:
    SYNTHETIC = {
        "doc_name": "FAR-33",
        "doc_title": "Test FAR-33",
        "agency": "FAA",
        "structure": {
            "chapters": [
                {
                    "id": "A",
                    "title": "A - General",
                    "page": 1,
                    "sections": [
                        {"number": "33.1", "title": "§ 33.1 Applicability.", "summary": "Applicability text"},
                        {"number": "33.3", "title": "§ 33.3 General.", "summary": "General requirements"},
                    ],
                }
            ]
        },
    }

    def test_doc_root_created(self):
        nodes, _ = build_far33_nodes(self.SYNTHETIC)
        doc = next((n for n in nodes if n["type"] == "regulation"), None)
        assert doc["id"] == "doc:FAR-33"

    def test_subpart_node_created(self):
        nodes, _ = build_far33_nodes(self.SYNTHETIC)
        sub = next((n for n in nodes if n["id"] == "far33:subpart_A"), None)
        assert sub is not None
        assert sub["depth"] == 1

    def test_section_nodes_created(self):
        nodes, _ = build_far33_nodes(self.SYNTHETIC)
        sections = [n for n in nodes if n["id"].startswith("far33:33_")]
        assert len(sections) == 2

    def test_section_ids_correct(self):
        nodes, _ = build_far33_nodes(self.SYNTHETIC)
        ids = {n["id"] for n in nodes}
        assert "far33:33_1" in ids
        assert "far33:33_3" in ids

    def test_contains_edges(self):
        _, edges = build_far33_nodes(self.SYNTHETIC)
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        # doc→subpartA + subpartA→33.1 + subpartA→33.3 = 3
        assert len(contains) == 3


class TestCseSyntheticStructure:
    SYNTHETIC = {
        "doc_name": "CS-E",
        "doc_title": "Test CS-E",
        "agency": "EASA",
        "structure": {
            "chapters": [
                {
                    "id": "A",
                    "title": "A - GENERAL",
                    "page": 1,
                    "sections": [
                        {"number": "E.10", "title": "§ E.10 Applicability", "summary": "Applicability text"},
                        {"number": "E.15", "title": "§ E.15 Terminology", "summary": "Terminology definitions"},
                    ],
                }
            ]
        },
    }

    def test_doc_root_created(self):
        nodes, _ = build_cse_nodes(self.SYNTHETIC)
        doc = next((n for n in nodes if n["type"] == "regulation"), None)
        assert doc["id"] == "doc:CS-E"
        assert doc["authority"] == "EASA"

    def test_book_node_created(self):
        nodes, _ = build_cse_nodes(self.SYNTHETIC)
        book = next((n for n in nodes if n["id"] == "cse:book_A"), None)
        assert book is not None
        assert book["depth"] == 1

    def test_section_nodes_created(self):
        nodes, _ = build_cse_nodes(self.SYNTHETIC)
        # IDs now include book prefix: cse:A_E_10
        sections = [n for n in nodes if n["depth"] == 2]
        assert len(sections) == 2

    def test_section_ids_correct(self):
        nodes, _ = build_cse_nodes(self.SYNTHETIC)
        ids = {n["id"] for n in nodes}
        # CS-E section IDs include book prefix: cse:{book}_{section}
        assert "cse:A_E_10" in ids
        assert "cse:A_E_15" in ids

    def test_far_harmonised_edge_for_book_a(self):
        _, edges = build_cse_nodes(self.SYNTHETIC)
        harmonised = [e for e in edges if e["rel_type"] == "FAR_HARMONISED"]
        assert len(harmonised) == 1
        assert harmonised[0]["from_id"] == "cse:book_A"
        assert harmonised[0]["to_id"] == "far33:SubpartA"

    def test_contains_edges(self):
        _, edges = build_cse_nodes(self.SYNTHETIC)
        contains = [e for e in edges if e["rel_type"] == "CONTAINS"]
        # doc→bookA + bookA→E.10 + bookA→E.15 = 3
        assert len(contains) == 3
