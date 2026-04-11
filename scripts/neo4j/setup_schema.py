"""
scripts/neo4j/setup_schema.py
==============================
AeroPower-RAG Neo4j 模式初始化脚本 (P2: 图数据库真实接入)

功能:
  1. 创建节点唯一性约束 (section, component, regulation, support)
  2. 创建全文搜索索引 (label, title, text)
  3. 创建范围索引 (authority, source_file)
  4. 验证约束和索引创建成功

运行:
    python scripts/neo4j/setup_schema.py
    python scripts/neo4j/setup_schema.py --verify-only   # 仅验证，不创建
    python scripts/neo4j/setup_schema.py --drop          # 删除后重建

前置条件:
    docker compose up -d neo4j
    # 等待 healthcheck 变绿 (~30s)

环境变量:
    NEO4J_URI      bolt://localhost:7687  (默认)
    NEO4J_USERNAME neo4j                  (默认)
    NEO4J_PASSWORD aeropower_rag_2026     (默认)
"""
from __future__ import annotations

import argparse
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
    from neo4j.exceptions import ClientError, ServiceUnavailable
except ImportError:
    print("❌ neo4j Python driver not installed.  Run:  pip install neo4j")
    sys.exit(2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

# ── Schema definitions ────────────────────────────────────────────────────────

UNIQUENESS_CONSTRAINTS = [
    # (constraint_name, label, property)
    ("section_id_unique",    "section",    "id"),
    ("component_id_unique",  "component",  "id"),
    ("regulation_id_unique", "regulation", "id"),
    ("support_id_unique",    "support",    "id"),
    ("document_id_unique",   "document",   "id"),
]

BTREE_INDEXES = [
    # (index_name, label, properties)
    ("section_label_idx",      "section",    ["label"]),
    ("component_label_idx",    "component",  ["label"]),
    ("section_source_idx",     "section",    ["source_file"]),
    ("regulation_authority",   "regulation", ["authority"]),
]

FULLTEXT_INDEXES = [
    # (index_name, labels, properties)
    ("node_fulltext_search", ["section", "component", "regulation", "support"],
     ["label", "title", "text"]),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(session, cypher: str, description: str) -> bool:
    """Execute a Cypher statement and return True on success."""
    try:
        session.run(cypher)
        logger.info("  ✅ %s", description)
        return True
    except ClientError as exc:
        if "already exists" in str(exc).lower() or "equivalent" in str(exc).lower():
            logger.info("  ⏭  %s (already exists — skipped)", description)
            return True
        logger.error("  ❌ %s  →  %s", description, exc)
        return False


def setup_constraints(session) -> int:
    """Create uniqueness constraints. Returns count of successful ops."""
    logger.info("Creating uniqueness constraints...")
    ok = 0
    for name, label, prop in UNIQUENESS_CONSTRAINTS:
        cypher = (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        if _run(session, cypher, f"CONSTRAINT {name} ({label}.{prop})"):
            ok += 1
    return ok


def setup_btree_indexes(session) -> int:
    logger.info("Creating B-tree indexes...")
    ok = 0
    for name, label, props in BTREE_INDEXES:
        props_str = ", ".join(f"n.{p}" for p in props)
        cypher = (
            f"CREATE INDEX {name} IF NOT EXISTS "
            f"FOR (n:{label}) ON ({props_str})"
        )
        if _run(session, cypher, f"INDEX {name} ({label}.{props})"):
            ok += 1
    return ok


def setup_fulltext_indexes(session) -> int:
    logger.info("Creating full-text indexes...")
    ok = 0
    for name, labels, props in FULLTEXT_INDEXES:
        labels_str = "|".join(labels)
        props_str  = ", ".join(f"n.{p}" for p in props)
        cypher = (
            f"CREATE FULLTEXT INDEX {name} IF NOT EXISTS "
            f"FOR (n:{labels_str}) ON EACH [{props_str}]"
        )
        if _run(session, cypher, f"FULLTEXT {name}"):
            ok += 1
    return ok


def drop_all(session) -> None:
    """Drop all AeroPower constraints and indexes (for clean rebuild)."""
    logger.warning("Dropping all AeroPower constraints...")
    for name, _, _ in UNIQUENESS_CONSTRAINTS:
        _run(session, f"DROP CONSTRAINT {name} IF EXISTS", f"DROP CONSTRAINT {name}")
    for name, _, _ in BTREE_INDEXES:
        _run(session, f"DROP INDEX {name} IF EXISTS", f"DROP INDEX {name}")
    for name, _, _ in FULLTEXT_INDEXES:
        _run(session, f"DROP INDEX {name} IF EXISTS", f"DROP FULLTEXT {name}")


def verify_schema(session) -> dict[str, list[str]]:
    """Return dict of existing constraints and indexes."""
    constraints = [
        r["name"] for r in session.run(
            "SHOW CONSTRAINTS YIELD name WHERE name STARTS WITH 'section_' "
            "OR name STARTS WITH 'component_' OR name STARTS WITH 'regulation_' "
            "OR name STARTS WITH 'support_' OR name STARTS WITH 'document_' "
            "RETURN name"
        )
    ]
    indexes = [
        r["name"] for r in session.run(
            "SHOW INDEXES YIELD name WHERE name ENDS WITH '_idx' "
            "OR name ENDS WITH '_search' OR name ENDS WITH '_authority' "
            "RETURN name"
        )
    ]
    return {"constraints": constraints, "indexes": indexes}


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="AeroPower-RAG Neo4j Schema Setup")
    parser.add_argument("--verify-only", action="store_true",
                        help="Print existing schema without creating anything")
    parser.add_argument("--drop", action="store_true",
                        help="Drop all AeroPower constraints/indexes before recreating")
    args = parser.parse_args()

    logger.info("Connecting to Neo4j at %s ...", NEO4J_URI)
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity()
        logger.info("  ✅ Connected")
    except ServiceUnavailable as exc:
        logger.error("❌ Cannot connect to Neo4j: %s", exc)
        logger.error("   Start Neo4j first:  docker compose up -d neo4j")
        return 1
    except Exception as exc:
        logger.error("❌ Connection error: %s", exc)
        return 1

    with driver.session() as session:
        if args.verify_only:
            schema = verify_schema(session)
            print(f"\nConstraints ({len(schema['constraints'])}):")
            for c in schema["constraints"]:
                print(f"  - {c}")
            print(f"\nIndexes ({len(schema['indexes'])}):")
            for i in schema["indexes"]:
                print(f"  - {i}")
            driver.close()
            return 0

        if args.drop:
            drop_all(session)

        total = (
            setup_constraints(session)
            + setup_btree_indexes(session)
            + setup_fulltext_indexes(session)
        )
        expected = (
            len(UNIQUENESS_CONSTRAINTS)
            + len(BTREE_INDEXES)
            + len(FULLTEXT_INDEXES)
        )

        logger.info("")
        logger.info("Schema setup complete: %d/%d operations succeeded.", total, expected)

        schema = verify_schema(session)
        logger.info(
            "Verified: %d constraints, %d indexes in Neo4j.",
            len(schema["constraints"]), len(schema["indexes"]),
        )

    driver.close()
    return 0 if total == expected else 1


if __name__ == "__main__":
    sys.exit(main())
