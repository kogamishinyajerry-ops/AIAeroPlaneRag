"""
scripts/neo4j/populate_far33_cse_graph.py
==========================================
Populate Neo4j graph with FAR-33 and CS-E regulation hierarchies.

Reads:
  - data/processed/FAR-33_structure.json  → 6 real Subparts + 65 section nodes
  - data/processed/CS-E_structure.json    → 3 Books + 158 section nodes

The FAR-33 section nodes (far33:33_27 etc.) are created as MERGE stubs by
populate_ccar33_graph.py.  This script uses ON CREATE / ON MATCH SET to
upgrade those placeholders with real content (title, text, depth).

CS-E nodes get a fresh ``cse:`` id-prefix hierarchy.  A FAR_HARMONISED
relationship links CS-E Subpart Book A ↔ FAR-33 equivalent subpart where
a clear structural mapping exists.

Output modes:
  --dry-run   print Cypher to stdout only
  --cypher    write to scripts/neo4j/populate_far33_cse.cypher
  (default)   connect to Neo4j and execute

Usage:
    python scripts/neo4j/populate_far33_cse_graph.py --dry-run
    python scripts/neo4j/populate_far33_cse_graph.py --cypher
    python scripts/neo4j/populate_far33_cse_graph.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

FAR33_STRUCTURE_JSON = ROOT / "data" / "processed" / "FAR-33_structure.json"
CSE_STRUCTURE_JSON   = ROOT / "data" / "processed" / "CS-E_structure.json"

# CS-E Book → FAR-33 Subpart structural harmonisation mapping
# CS-E Appendix 1 Section 3 documents the mapping at chapter level
CSE_FAR_HARMONISED: dict[str, str] = {
    "A": "SubpartA",   # CS-E Book A General ↔ FAR-33 Subpart A General
    "C": "SubpartF",   # CS-E Book C Type Substantiation ↔ FAR-33 Subpart F Block Tests
}


def _escape_cypher_string(s: str) -> str:
    """Escape a string for inline Cypher single-quoted value."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _far33_section_id(section_num: str) -> str:
    """Convert section number like '33.27' to node id 'far33:33_27'."""
    return "far33:" + section_num.replace(".", "_")


def _cse_section_id(section_num: str) -> str:
    """Convert CS-E section number like 'E.10' to node id 'cse:E_10'."""
    return "cse:" + section_num.replace(".", "_")


def build_far33_nodes(
    structure_data: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """
    Parse FAR-33_structure.json into nodes and edges.

    FAR-33 structure uses ``structure.chapters[]`` with chapter.id (letter) and
    chapter.sections[] (list of {number, title, content_parts, summary}).

    Node IDs:
        doc:FAR-33               — root regulation node
        far33:subpart_{A}        — subpart nodes (depth=1)
        far33:{33_27}            — section nodes (depth=2); matches CCAR stubs
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    doc_name = structure_data.get("doc_name", "FAR-33")
    doc_title = structure_data.get("doc_title", "14 CFR Part 33 Airworthiness Standards")

    doc_id = f"doc:{doc_name}"
    nodes.append({
        "id": doc_id,
        "label": doc_name,
        "type": "regulation",
        "title": doc_title,
        "text": f"{doc_name}: {doc_title}",
        "section_number": "",
        "source": "FAR-33",
        "authority": "FAA",
        "depth": 0,
    })

    inner = structure_data.get("structure", {})
    chapters = inner.get("chapters", []) if isinstance(inner, dict) else []

    # Track per-letter counts to disambiguate duplicate subpart IDs
    # (FAR-33 has duplicate chapter letters for emission standards)
    subpart_letter_count: dict[str, int] = {}

    for chapter in chapters:
        ch_id_letter = chapter.get("id", "?")
        ch_title = chapter.get("title", f"Subpart {ch_id_letter}").strip()

        subpart_letter_count[ch_id_letter] = subpart_letter_count.get(ch_id_letter, 0) + 1
        count = subpart_letter_count[ch_id_letter]
        # First occurrence uses clean id; duplicates get a numeric suffix
        if count == 1:
            subpart_id = f"far33:subpart_{ch_id_letter}"
        else:
            subpart_id = f"far33:subpart_{ch_id_letter}_{count}"

        nodes.append({
            "id": subpart_id,
            "label": ch_title,
            "type": "section",
            "title": ch_title,
            "text": ch_title,
            "section_number": "",
            "source": "FAR-33",
            "authority": "FAA",
            "depth": 1,
            "subpart": ch_id_letter,
        })
        edges.append({"from_id": doc_id, "to_id": subpart_id, "rel_type": "CONTAINS"})

        for sec in chapter.get("sections", []):
            sec_num = sec.get("number", "")
            sec_title = sec.get("title", sec_num).strip()
            sec_text = sec.get("summary", "") or sec_title

            # Build text from content_parts if available
            if sec.get("content_parts"):
                sec_text = "\n".join(sec["content_parts"])

            sec_id = _far33_section_id(sec_num) if sec_num else f"far33:{subpart_id}_{sec_title[:15]}"

            nodes.append({
                "id": sec_id,
                "label": sec_title,
                "type": "section",
                "title": sec_title,
                "text": (sec_text or sec_title)[:2000],
                "section_number": sec_num,
                "source": "FAR-33",
                "authority": "FAA",
                "depth": 2,
            })
            edges.append({"from_id": subpart_id, "to_id": sec_id, "rel_type": "CONTAINS"})

    return nodes, edges


def build_cse_nodes(
    structure_data: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """
    Parse CS-E_structure.json into nodes and edges.

    CS-E structure uses ``structure.chapters[]`` with chapter.id (letter) and
    chapter.sections[] (list of {number, title, content_parts, summary}).

    Node IDs:
        doc:CS-E                 — root regulation node
        cse:book_{A}             — book nodes (depth=1)
        cse:{A}_{E_10}           — section nodes (depth=2); book-prefix avoids
                                   duplicate E.XXX numbers across books A/B/C
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    doc_name = structure_data.get("doc_name", "CS-E")
    doc_title = structure_data.get("doc_title", "EASA CS-E Certification Specifications for Engines")

    doc_id = f"doc:{doc_name}"
    nodes.append({
        "id": doc_id,
        "label": doc_name,
        "type": "regulation",
        "title": doc_title,
        "text": f"{doc_name}: {doc_title}",
        "section_number": "",
        "source": "CS-E",
        "authority": "EASA",
        "depth": 0,
    })

    inner = structure_data.get("structure", {})
    chapters = inner.get("chapters", []) if isinstance(inner, dict) else []

    for chapter in chapters:
        ch_id_letter = chapter.get("id", "?")
        ch_title = chapter.get("title", f"Book {ch_id_letter}").strip()
        book_id = f"cse:book_{ch_id_letter}"

        nodes.append({
            "id": book_id,
            "label": ch_title,
            "type": "section",
            "title": ch_title,
            "text": ch_title,
            "section_number": "",
            "source": "CS-E",
            "authority": "EASA",
            "depth": 1,
            "book": ch_id_letter,
        })
        edges.append({"from_id": doc_id, "to_id": book_id, "rel_type": "CONTAINS"})

        # CS-E ↔ FAR-33 structural harmonisation edge at book level
        if ch_id_letter in CSE_FAR_HARMONISED:
            far_subpart_id = f"far33:{CSE_FAR_HARMONISED[ch_id_letter]}"
            edges.append({
                "from_id": book_id,
                "to_id": far_subpart_id,
                "rel_type": "FAR_HARMONISED",
            })

        for sec in chapter.get("sections", []):
            sec_num = sec.get("number", "")
            sec_title = sec.get("title", sec_num).strip()
            sec_text = sec.get("summary", "") or sec_title

            if sec.get("content_parts"):
                sec_text = "\n".join(sec["content_parts"])

            # Include book prefix to avoid duplicate IDs across books
            # (CS-E has the same E.XXX numbers in Books A, B, and C)
            if sec_num:
                sec_id = f"cse:{ch_id_letter}_{_cse_section_id(sec_num).replace('cse:', '')}"
            else:
                sec_id = f"cse:{ch_id_letter}_{sec_title[:15].replace(' ', '_')}"

            nodes.append({
                "id": sec_id,
                "label": sec_title,
                "type": "section",
                "title": sec_title,
                "text": (sec_text or sec_title)[:2000],
                "section_number": sec_num,
                "source": "CS-E",
                "authority": "EASA",
                "depth": 2,
            })
            edges.append({"from_id": book_id, "to_id": sec_id, "rel_type": "CONTAINS"})

    return nodes, edges


def generate_cypher(
    far33_nodes: list[dict],
    far33_edges: list[dict],
    cse_nodes: list[dict],
    cse_edges: list[dict],
) -> list[str]:
    """Generate MERGE Cypher for FAR-33 and CS-E nodes + edges."""
    stmts: list[str] = []
    stmts.append("// ── FAR-33 + CS-E Graph Population ───────────────────────────")
    stmts.append("// Generated by scripts/neo4j/populate_far33_cse_graph.py")
    stmts.append("")

    def add_nodes(nodes: list[dict], comment: str) -> None:
        stmts.append(f"// {comment}")
        for node in nodes:
            n_id     = _escape_cypher_string(node["id"])
            label    = _escape_cypher_string(node.get("label", ""))
            title    = _escape_cypher_string(node.get("title", ""))
            text     = _escape_cypher_string(node.get("text", "")[:500])
            sec_num  = _escape_cypher_string(node.get("section_number", ""))
            source   = _escape_cypher_string(node.get("source", ""))
            authority= _escape_cypher_string(node.get("authority", ""))
            depth    = node.get("depth", 0)
            n_type   = node.get("type", "section")
            cy_label = "regulation" if n_type == "regulation" else "section"
            # Use ON CREATE / ON MATCH so FAR-33 stub nodes are upgraded
            stmts.append(
                f"MERGE (n:{cy_label} {{id: '{n_id}'}})"
                f" ON CREATE SET n.label = '{label}', n.title = '{title}',"
                f" n.text = '{text}', n.section_number = '{sec_num}',"
                f" n.source = '{source}', n.authority = '{authority}', n.depth = {depth}"
                f" ON MATCH SET n.title = CASE WHEN n.title IS NULL OR n.title = '' THEN '{title}' ELSE n.title END,"
                f" n.text = CASE WHEN n.text IS NULL OR n.text = '' THEN '{text}' ELSE n.text END,"
                f" n.source = '{source}', n.authority = '{authority}';"
            )
        stmts.append("")

    def add_edges(edges: list[dict], comment: str) -> None:
        stmts.append(f"// {comment}")
        for edge in edges:
            from_id = _escape_cypher_string(edge["from_id"])
            to_id   = _escape_cypher_string(edge["to_id"])
            rel     = edge["rel_type"]
            stmts.append(
                f"MERGE (a {{id: '{from_id}'}}) MERGE (b {{id: '{to_id}'}})"
                f" MERGE (a)-[:{rel}]->(b);"
            )
        stmts.append("")

    add_nodes(far33_nodes, "FAR-33 nodes")
    add_edges(far33_edges, "FAR-33 edges")
    add_nodes(cse_nodes, "CS-E nodes")
    add_edges(cse_edges, "CS-E edges")

    return stmts


def execute_cypher(stmts: list[str]) -> None:
    """Connect to Neo4j and execute Cypher statements."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.error("neo4j Python driver not installed.  pip install neo4j")
        sys.exit(2)

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as exc:
        logger.error("Cannot connect to Neo4j at %s: %s", NEO4J_URI, exc)
        sys.exit(1)

    success = errors = 0
    with driver.session() as session:
        for stmt in stmts:
            stmt = stmt.strip()
            if not stmt or stmt.startswith("//"):
                continue
            try:
                session.run(stmt)
                success += 1
            except Exception as exc:
                logger.warning("Cypher error: %s\n  stmt: %s", exc, stmt[:120])
                errors += 1

    driver.close()
    logger.info("Neo4j population complete: %d OK, %d errors", success, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate Neo4j with FAR-33 + CS-E graph data"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print Cypher to stdout, no DB connection")
    parser.add_argument("--cypher", action="store_true",
                        help="Write Cypher to scripts/neo4j/populate_far33_cse.cypher")
    parser.add_argument("--far33", default=str(FAR33_STRUCTURE_JSON),
                        help="Path to FAR-33 structure JSON")
    parser.add_argument("--cse", default=str(CSE_STRUCTURE_JSON),
                        help="Path to CS-E structure JSON")
    args = parser.parse_args()

    far33_path = Path(args.far33)
    cse_path   = Path(args.cse)

    if not far33_path.exists():
        logger.error("FAR-33 structure not found: %s", far33_path)
        sys.exit(1)
    if not cse_path.exists():
        logger.error("CS-E structure not found: %s", cse_path)
        sys.exit(1)

    with open(far33_path, encoding="utf-8") as f:
        far33_data = json.load(f)
    with open(cse_path, encoding="utf-8") as f:
        cse_data = json.load(f)

    far33_nodes, far33_edges = build_far33_nodes(far33_data)
    cse_nodes,   cse_edges   = build_cse_nodes(cse_data)

    stmts = generate_cypher(far33_nodes, far33_edges, cse_nodes, cse_edges)

    logger.info(
        "FAR-33: %d nodes, %d edges | CS-E: %d nodes, %d edges | %d Cypher statements",
        len(far33_nodes), len(far33_edges),
        len(cse_nodes),   len(cse_edges),
        len(stmts),
    )

    if args.dry_run:
        for s in stmts:
            print(s)
        return

    if args.cypher:
        out_path = Path(__file__).parent / "populate_far33_cse.cypher"
        out_path.write_text("\n".join(stmts), encoding="utf-8")
        logger.info("Cypher written to %s", out_path)
        return

    execute_cypher(stmts)


if __name__ == "__main__":
    main()
