"""
Load CCAR-33-R2 Knowledge Graph to Neo4j

This script loads the professional knowledge graph into Neo4j database.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

try:
    from neo4j import GraphDatabase
except ImportError:
    print("[ERROR] neo4j library not installed. Run: pip install neo4j")
    sys.exit(1)

from settings import PROCESSED_DATA_DIR


def load_graph_to_neo4j():
    """Load knowledge graph JSON to Neo4j."""

    # Neo4j connection settings
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

    print("=" * 60)
    print(" Loading CCAR-33-R2 Graph to Neo4j")
    print("=" * 60)
    print(f"URI: {uri}")
    print(f"User: {user}")

    # Read graph JSON
    graph_path = PROCESSED_DATA_DIR / "CCAR-33-R2_professional_graph.json"
    if not graph_path.exists():
        print(f"[ERROR] Graph file not found: {graph_path}")
        print("Please run the graph builder first:")
        print("  python src/ontology/professional_extractor.py")
        return False

    import json
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    entities = graph_data.get("entities", [])
    relationships = graph_data.get("relationships", [])

    print(f"\n[DATA] Found {len(entities)} entities and {len(relationships)} relationships")

    # Connect to Neo4j
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("[OK] Connected to Neo4j")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Neo4j: {e}")
        print("\nPlease ensure Neo4j is running:")
        print("  - Docker: docker compose up -d neo4j")
        print("  - Or install Neo4j locally: see docs/NEO4J_SETUP.md")
        return False

    try:
        with driver.session() as session:
            # Clear existing data
            print("\n[CLEAN] Clearing existing graph data...")
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            count = summary.counters.nodes_deleted
            print(f"[OK] Deleted {count} existing nodes")

            # Create entities (nodes)
            print(f"\n[CREATE] Creating {len(entities)} nodes...")
            entity_count = 0
            for entity in entities:
                try:
                    cypher = f"""
                    MERGE (n:{entity['type']} {{id: $id}})
                    SET n.name = $name,
                        n.description = $description,
                        n.type = $entity_type
                    """
                    session.run(cypher,
                        id=entity["id"],
                        name=entity["name"],
                        description=entity.get("description", ""),
                        entity_type=entity["type"]
                    )
                    entity_count += 1
                except Exception as e:
                    print(f"  [WARN] Failed to create entity {entity['id']}: {e}")

            print(f"[OK] Created {entity_count} nodes")

            # Print entity type summary
            type_counts = {}
            for e in entities:
                type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
            print("\n  Entity types:")
            for etype, count in sorted(type_counts.items()):
                print(f"    - {etype}: {count}")

            # Create relationships
            print(f"\n[CREATE] Creating {len(relationships)} relationships...")
            rel_count = 0
            for rel in relationships:
                try:
                    cypher = f"""
                    MATCH (a {{id: $source}})
                    MATCH (b {{id: $target}})
                    MERGE (a)-[r:{rel['type']}]->(b)
                    SET r.description = $description
                    """
                    session.run(cypher,
                        source=rel["source"],
                        target=rel["target"],
                        description=rel.get("description", "")
                    )
                    rel_count += 1
                except Exception as e:
                    print(f"  [WARN] Failed to create relationship {rel['source']}->{rel['target']}: {e}")

            print(f"[OK] Created {rel_count} relationships")

            # Print relationship type summary
            rel_types = {}
            for r in relationships:
                rel_types[r["type"]] = rel_types.get(r["type"], 0) + 1
            print("\n  Relationship types:")
            for rtype, count in sorted(rel_types.items()):
                print(f"    - {rtype}: {count}")

            # Verify data
            print("\n[VERIFY] Verifying loaded data...")
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_record = result.single()
            node_count = node_record["count"] if node_record else 0
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_record = result.single()
            rel_count_result = rel_record["count"] if rel_record else 0

            print(f"[OK] Verification: {node_count} nodes, {rel_count_result} relationships")

        print("\n" + "=" * 60)
        print(" SUCCESS! Graph loaded to Neo4j")
        print("=" * 60)
        print(f"\nYou can now explore the graph at:")
        print(f"  Neo4j Browser: http://localhost:7474")
        print(f"  User: {user}")
        print(f"  Password: {password}")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to load graph: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.close()


if __name__ == "__main__":
    success = load_graph_to_neo4j()
    sys.exit(0 if success else 1)
