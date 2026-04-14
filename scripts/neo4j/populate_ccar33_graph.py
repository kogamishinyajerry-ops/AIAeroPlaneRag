"""
scripts/neo4j/populate_ccar33_graph.py
=======================================
Populate Neo4j graph with CCAR-33-R2 regulation hierarchy.

读取 data/processed/CCAR-33-R2_structure.json，将:
  - 每个章节 → :regulation 节点 (doc level)
  - 每个章 (chapter) → :section 节点
  - 每个条款 (clause) → :section 子节点
  - CONTAINS 关系连接父→子
  - FAR_EQUIVALENT 关系 (基于已知 CCAR-33 ↔ FAR-33 对应表)

输出模式:
  --dry-run   仅打印 Cypher 语句，不连接 Neo4j
  --cypher    将 Cypher 写入 scripts/neo4j/populate_ccar33.cypher
  (默认)      连接 Neo4j bolt:// 并执行

运行:
    python scripts/neo4j/populate_ccar33_graph.py --dry-run
    python scripts/neo4j/populate_ccar33_graph.py --cypher
    python scripts/neo4j/populate_ccar33_graph.py   # 需要 Neo4j 运行中
"""
from __future__ import annotations

import argparse
import json
import logging
import os
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

STRUCTURE_JSON = ROOT / "data" / "processed" / "CCAR-33-R2_structure.json"

# Known CCAR-33 ↔ FAR-33 clause equivalence (section number → FAR-33 section)
# Based on CAAC/FAA bilateral harmonisation table (representative subset)
CCAR_FAR_EQUIVALENT: dict[str, str] = {
    "33.1": "FAR-33.1",
    "33.3": "FAR-33.3",
    "33.5": "FAR-33.5",
    "33.7": "FAR-33.7",
    "33.9": "FAR-33.9",
    "33.11": "FAR-33.11",
    "33.13": "FAR-33.13",
    "33.15": "FAR-33.15",
    "33.17": "FAR-33.17",
    "33.19": "FAR-33.19",
    "33.21": "FAR-33.21",
    "33.23": "FAR-33.23",
    "33.27": "FAR-33.27",
    "33.28": "FAR-33.28",
    "33.29": "FAR-33.29",
    "33.31": "FAR-33.31",
    "33.33": "FAR-33.33",
    "33.34": "FAR-33.34",
    "33.35": "FAR-33.35",
    "33.37": "FAR-33.37",
    "33.39": "FAR-33.39",
    "33.41": "FAR-33.41",
    "33.43": "FAR-33.43",
    "33.45": "FAR-33.45",
    "33.47": "FAR-33.47",
    "33.49": "FAR-33.49",
    "33.51": "FAR-33.51",
    "33.53": "FAR-33.53",
    "33.55": "FAR-33.55",
    "33.57": "FAR-33.57",
    "33.59": "FAR-33.59",
    "33.61": "FAR-33.61",
    "33.63": "FAR-33.63",
    "33.65": "FAR-33.65",
    "33.67": "FAR-33.67",
    "33.68": "FAR-33.68",
    "33.69": "FAR-33.69",
    "33.70": "FAR-33.70",
    "33.71": "FAR-33.71",
    "33.72": "FAR-33.72",
    "33.73": "FAR-33.73",
    "33.74": "FAR-33.74",
    "33.75": "FAR-33.75",
    "33.76": "FAR-33.76",
    "33.77": "FAR-33.77",
    "33.78": "FAR-33.78",
    "33.79": "FAR-33.79",
    "33.81": "FAR-33.81",
    "33.82": "FAR-33.82",
    "33.83": "FAR-33.83",
    "33.84": "FAR-33.84",
    "33.85": "FAR-33.85",
    "33.86": "FAR-33.86",
    "33.87": "FAR-33.87",
    "33.88": "FAR-33.88",
    "33.89": "FAR-33.89",
    "33.90": "FAR-33.90",
    "33.91": "FAR-33.91",
    "33.92": "FAR-33.92",
    "33.93": "FAR-33.93",
    "33.94": "FAR-33.94",
    "33.95": "FAR-33.95",
    "33.96": "FAR-33.96",
    "33.97": "FAR-33.97",
}


def _extract_section_number(title: str) -> str:
    """Extract numeric section number from title like '第33.27条 发动机控制系统'."""
    import re
    m = re.search(r"33\.(\d+[a-zA-Z]?)", title)
    if m:
        return f"33.{m.group(1)}"
    return ""


def _escape_cypher_string(s: str) -> str:
    """Escape a string for inline Cypher single-quoted value."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def build_graph_nodes(structure_data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """
    Parse CCAR-33-R2 structure JSON into flat lists of nodes and edges.

    Returns:
        nodes: list of {id, label, type, title, text, section_number, source, depth}
        edges: list of {from_id, to_id, rel_type}
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    doc_name = structure_data.get("doc_name", "CCAR-33-R2")
    doc_title = structure_data.get("doc_title", "航空发动机适航规定")

    # Root document node
    doc_id = f"doc:{doc_name}"
    nodes.append({
        "id": doc_id,
        "label": doc_name,
        "type": "regulation",
        "title": doc_title,
        "text": f"{doc_name} {doc_title}",
        "section_number": "",
        "source": doc_name,
        "authority": "CAAC",
        "depth": 0,
    })

    def process_node(node: dict, parent_id: str, depth: int) -> None:
        node_id_raw = node.get("node_id", "")
        title = node.get("title", "").strip()
        text = node.get("text", "") or ""
        # Content may be in content_parts list if text is empty
        if not text and node.get("content_parts"):
            text = "\n\n".join(node["content_parts"])

        section_num = _extract_section_number(title)
        n_id = f"ccar33:{node_id_raw}" if node_id_raw else f"ccar33:t_{title[:20]}"
        n_type = "section"

        nodes.append({
            "id": n_id,
            "label": title,
            "type": n_type,
            "title": title,
            "text": text[:2000] if text else "",   # cap to 2 KB per node
            "section_number": section_num,
            "source": doc_name,
            "authority": "CAAC",
            "depth": depth,
        })

        edges.append({"from_id": parent_id, "to_id": n_id, "rel_type": "CONTAINS"})

        # FAR equivalent cross-reference
        if section_num and section_num in CCAR_FAR_EQUIVALENT:
            far_id = f"far33:{section_num.replace('.', '_')}"
            edges.append({
                "from_id": n_id,
                "to_id": far_id,
                "rel_type": "FAR_EQUIVALENT",
            })

        for child in node.get("nodes", []):
            process_node(child, n_id, depth + 1)

    for chapter in structure_data.get("structure", []):
        process_node(chapter, doc_id, 1)

    return nodes, edges


def generate_cypher(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Generate Cypher MERGE statements for all nodes and edges."""
    stmts: list[str] = []

    stmts.append("// ── CCAR-33-R2 Graph Population ─────────────────────────────")
    stmts.append("// Generated by scripts/neo4j/populate_ccar33_graph.py")
    stmts.append("")

    # Create FAR-33 equivalent placeholder nodes first (so edge targets exist)
    far_ids = {e["to_id"] for e in edges if e["rel_type"] == "FAR_EQUIVALENT"}
    for far_id in sorted(far_ids):
        sec = far_id.replace("far33:", "").replace("_", ".")
        stmts.append(
            f"MERGE (n:section {{id: '{_escape_cypher_string(far_id)}'}})"
            f" ON CREATE SET n.label = 'FAR {sec}', n.source = 'FAR-33', n.authority = 'FAA';"
        )
    if far_ids:
        stmts.append("")

    # Document root
    for node in nodes:
        n_id = _escape_cypher_string(node["id"])
        label = _escape_cypher_string(node.get("label", ""))
        title = _escape_cypher_string(node.get("title", ""))
        text = _escape_cypher_string(node.get("text", "")[:500])
        section_num = _escape_cypher_string(node.get("section_number", ""))
        source = _escape_cypher_string(node.get("source", ""))
        authority = _escape_cypher_string(node.get("authority", ""))
        n_type = node.get("type", "section")
        depth = node.get("depth", 0)
        cypher_label = "regulation" if n_type == "regulation" else "section"
        stmts.append(
            f"MERGE (n:{cypher_label} {{id: '{n_id}'}})"
            f" ON CREATE SET n.label = '{label}', n.title = '{title}',"
            f" n.text = '{text}', n.section_number = '{section_num}',"
            f" n.source = '{source}', n.authority = '{authority}', n.depth = {depth};"
        )

    stmts.append("")
    stmts.append("// ── Edges ────────────────────────────────────────────────────")

    for edge in edges:
        from_id = _escape_cypher_string(edge["from_id"])
        to_id = _escape_cypher_string(edge["to_id"])
        rel = edge["rel_type"]
        stmts.append(
            f"MATCH (a {{id: '{from_id}'}}), (b {{id: '{to_id}'}})"
            f" MERGE (a)-[:{rel}]->(b);"
        )

    return stmts


def execute_cypher(stmts: list[str]) -> None:
    """Connect to Neo4j and execute Cypher statements."""
    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import ServiceUnavailable
    except ImportError:
        logger.error("neo4j Python driver not installed.  pip install neo4j")
        sys.exit(2)

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
    except Exception as exc:
        logger.error("Cannot connect to Neo4j at %s: %s", NEO4J_URI, exc)
        sys.exit(1)

    success = 0
    errors = 0
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
    parser = argparse.ArgumentParser(description="Populate Neo4j with CCAR-33-R2 graph data")
    parser.add_argument("--dry-run", action="store_true", help="Print Cypher to stdout, no DB connection")
    parser.add_argument("--cypher", action="store_true", help="Write Cypher to scripts/neo4j/populate_ccar33.cypher")
    parser.add_argument("--structure", default=str(STRUCTURE_JSON), help="Path to structure JSON")
    args = parser.parse_args()

    structure_path = Path(args.structure)
    if not structure_path.exists():
        logger.error("Structure file not found: %s", structure_path)
        sys.exit(1)

    with open(structure_path, encoding="utf-8") as f:
        structure_data = json.load(f)

    nodes, edges = build_graph_nodes(structure_data)
    stmts = generate_cypher(nodes, edges)

    logger.info("Graph: %d nodes, %d edges, %d Cypher statements", len(nodes), len(edges), len(stmts))

    if args.dry_run:
        for s in stmts:
            print(s)
        return

    if args.cypher:
        out_path = Path(__file__).parent / "populate_ccar33.cypher"
        out_path.write_text("\n".join(stmts), encoding="utf-8")
        logger.info("Cypher written to %s", out_path)
        return

    # Default: connect and execute
    execute_cypher(stmts)


if __name__ == "__main__":
    main()
