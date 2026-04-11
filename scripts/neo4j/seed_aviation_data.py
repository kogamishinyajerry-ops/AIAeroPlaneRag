"""
Neo4j 航空法规本体图初始化脚本
================================
从 data/processed/CCAR-33-R2_professional_graph.json (或 fallback JSON)
向 Neo4j 导入节点和关系。

用法:
    python scripts/neo4j/seed_aviation_data.py [--clear]

选项:
    --clear    导入前清空 Neo4j 中所有现有节点和关系

环境变量 (.env):
    NEO4J_URI      bolt://localhost:7687
    NEO4J_USERNAME neo4j
    NEO4J_PASSWORD aeropower_rag_2026

前置条件:
    docker-compose up -d neo4j   # 等待 healthcheck 绿色
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError:
    print("❌ neo4j Python driver not installed. Run: pip install neo4j")
    sys.exit(2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

GRAPH_JSON_CANDIDATES = [
    ROOT / "data" / "processed" / "CCAR-33-R2_professional_graph.json",
    ROOT / "data" / "processed" / "CCAR-33_graph.json",
    ROOT / "data" / "data" / "cross_mappings.json",
]


def load_graph_json() -> dict:
    for path in GRAPH_JSON_CANDIDATES:
        if path.exists():
            logger.info("Loading graph JSON from %s", path)
            return json.loads(path.read_text(encoding="utf-8"))
    # Generate minimal seed data if no JSON found
    logger.warning("No graph JSON found; using minimal seed dataset")
    return {
        "entities": [
            {"id": "CCAR-33", "name": "CCAR-33", "type": "regulation",
             "description": "中国民用航空规章第33部 — 航空发动机适航标准"},
            {"id": "FAR-33",  "name": "FAR-33",  "type": "regulation",
             "description": "Federal Aviation Regulations Part 33 — Airworthiness Standards: Aircraft Engines"},
            {"id": "CS-E",    "name": "CS-E",    "type": "regulation",
             "description": "EASA Certification Specifications for Engines"},
            {"id": "CCAR-33-65", "name": "CCAR-33 §33.65", "type": "section",
             "description": "压气机喘振裕度要求"},
            {"id": "FAR-33-65",  "name": "FAR-33 §33.65",  "type": "section",
             "description": "Surge margin requirements"},
            {"id": "CS-E-560",   "name": "CS-E §560",       "type": "section",
             "description": "Compressor design requirements"},
            {"id": "compressor", "name": "压气机 / Compressor", "type": "component",
             "description": "航空发动机压气机组件"},
            {"id": "turbine",    "name": "涡轮 / Turbine",    "type": "component",
             "description": "航空发动机涡轮组件"},
            {"id": "surge-margin", "name": "喘振裕度 Surge Margin", "type": "parameter",
             "description": "压气机喘振裕度安全参数"},
        ],
        "relationships": [
            {"source": "CCAR-33",    "target": "CCAR-33-65", "type": "CONTAINS",
             "description": "CCAR-33 包含 §33.65"},
            {"source": "FAR-33",     "target": "FAR-33-65",  "type": "CONTAINS",
             "description": "FAR-33 contains §33.65"},
            {"source": "CS-E",       "target": "CS-E-560",   "type": "CONTAINS",
             "description": "CS-E contains §560"},
            {"source": "CCAR-33-65", "target": "FAR-33-65",  "type": "EQUIVALENT_TO",
             "description": "CCAR-33 §33.65 等效于 FAR-33 §33.65"},
            {"source": "CCAR-33-65", "target": "compressor",  "type": "REGULATES",
             "description": "条款规制压气机组件"},
            {"source": "compressor", "target": "surge-margin", "type": "HAS_PARAMETER",
             "description": "压气机需保持喘振裕度参数"},
            {"source": "CCAR-33-65", "target": "surge-margin", "type": "REQUIRES",
             "description": "条款要求喘振裕度满足标准"},
        ],
    }


def seed(driver, graph: dict, clear: bool = False) -> tuple[int, int]:
    with driver.session() as session:
        if clear:
            logger.warning("Clearing all existing nodes and relationships…")
            session.run("MATCH (n) DETACH DELETE n")

        # ── Create indexes ────────────────────────────────────────────────
        session.run("CREATE INDEX entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id)")

        # ── Insert entities ───────────────────────────────────────────────
        entities = graph.get("entities", [])
        entity_count = 0
        for ent in entities:
            eid = ent.get("id", "")
            if not eid:
                continue
            session.run(
                """
                MERGE (n:Entity {id: $id})
                SET n.name        = $name,
                    n.type        = $type,
                    n.description = $description,
                    n.label       = $label
                """,
                id=eid,
                name=ent.get("name", eid),
                type=ent.get("type", "unknown"),
                description=ent.get("description", ""),
                label=ent.get("type", "Entity").capitalize(),
            )
            entity_count += 1

        # ── Insert relationships ──────────────────────────────────────────
        rels = graph.get("relationships", [])
        rel_count = 0
        for rel in rels:
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            rtype = rel.get("type", "RELATED_TO").upper().replace(" ", "_").replace("-", "_")
            if not src or not tgt:
                continue
            # Dynamic relationship type requires string formatting (Cypher limitation)
            session.run(
                f"""
                MATCH (a:Entity {{id: $src}}), (b:Entity {{id: $tgt}})
                MERGE (a)-[r:{rtype}]->(b)
                SET r.description = $desc
                """,
                src=src,
                tgt=tgt,
                desc=rel.get("description", ""),
            )
            rel_count += 1

        node_count_result = session.run("MATCH (n) RETURN count(n) AS c").single()
        logger.info("Graph seeded: %d entities, %d relationships", entity_count, rel_count)
        logger.info("Total nodes in Neo4j: %d", node_count_result["c"])
        return entity_count, rel_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed aviation ontology data into Neo4j")
    parser.add_argument("--clear", action="store_true", help="Clear all existing data first")
    args = parser.parse_args()

    logger.info("Connecting to Neo4j at %s …", NEO4J_URI)
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        logger.info("✅ Connected to Neo4j")
    except ServiceUnavailable as exc:
        logger.error("❌ Cannot reach Neo4j: %s", exc)
        logger.error("   Make sure Neo4j is running: docker-compose up -d neo4j")
        return 1
    except Exception as exc:
        logger.error("❌ Neo4j connection error: %s", exc)
        return 1

    graph = load_graph_json()
    n_entities, n_rels = seed(driver, graph, clear=args.clear)
    driver.close()

    print(f"\n✅ Neo4j seed complete: {n_entities} entities, {n_rels} relationships")
    return 0


if __name__ == "__main__":
    sys.exit(main())
