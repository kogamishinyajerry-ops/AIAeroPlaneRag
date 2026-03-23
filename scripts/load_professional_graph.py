"""Load professional CCAR-33-R2 graph to Neo4j."""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

# Connection
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

# Load professional graph
graph_file = Path(__file__).parent.parent / "data" / "processed" / "CCAR-33-R2_professional_graph.json"
with open(graph_file, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

entities = graph_data.get("entities", [])
relationships = graph_data.get("relationships", [])

print("=" * 60)
print(" Loading Professional CCAR-33-R2 Graph to Neo4j")
print("=" * 60)
print(f"\nEntities: {len(entities)}")
print(f"Relationships: {len(relationships)}")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    # Clear existing data
    print("\n[CLEAR] Clearing existing graph...")
    session.run("MATCH (n) DETACH DELETE n")

    # Create entities
    print(f"\n[CREATE] Loading {len(entities)} nodes...")
    entity_types = {}
    for entity in entities:
        entity_type = entity.get("type", "Entity")
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        session.run("""
            MERGE (n:Entity {id: $id})
            SET n.name = $name,
                n.type = $type,
                n.description = $description
        """,
            id=entity.get("id"),
            name=entity.get("name"),
            type=entity_type,
            description=entity.get("description", "")
        )

    print(f"  Entity types:")
    for etype, count in sorted(entity_types.items()):
        print(f"    - {etype}: {count}")

    # Create relationships
    print(f"\n[CREATE] Loading {len(relationships)} relationships...")
    rel_types = {}
    created = 0

    for rel in relationships:
        rel_type = rel.get("type", "RELATED_TO")
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1

        try:
            session.run("""
                MATCH (a:Entity {id: $source})
                MATCH (b:Entity {id: $target})
                MERGE (a)-[r:RELATIONSHIP {type: $type}]->(b)
                SET r.description = $description
            """,
                source=rel.get("source"),
                target=rel.get("target"),
                type=rel_type,
                description=rel.get("description", "")
            )
            created += 1
        except Exception as e:
            pass  # Skip if nodes don't exist

    print(f"  Created: {created} relationships")
    print(f"  Relationship types:")
    for rtype, count in sorted(rel_types.items()):
        print(f"    - {rtype}: {count}")

    # Verify
    result = session.run("MATCH (n) RETURN count(n) as count")
    node_count = result.single()["count"]
    result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
    rel_count = result.single()["count"] if result.single() else 0

    print(f"\n[VERIFY] Nodes: {node_count}, Relationships: {rel_count}")

driver.close()

print("\n[DONE] Professional graph loaded!")
print(f"\nNeo4j Browser: http://localhost:7474")
print(f"  User: {user}")
print(f"  Password: {password}")
