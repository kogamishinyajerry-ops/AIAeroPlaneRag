"""Direct Neo4j query test."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j not installed")
    exit(1)

import os

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

print(f"Connecting to {uri}...")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    # Count nodes
    result = session.run("MATCH (n) RETURN count(n) as count")
    count = result.single()["count"]
    print(f"Total nodes: {count}")

    # Get sample nodes
    result = session.run("MATCH (n) RETURN n.id AS id, n.name AS name, n.type AS type LIMIT 10")
    print("\nSample nodes:")
    for record in result:
        print(f"  - {record['id']} ({record.get('type', 'unknown')}): {record.get('name', '')[:40]}")

    # Get relationships
    result = session.run("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count")
    print("\nRelationships:")
    for record in result:
        print(f"  - {record['rel_type']}: {record['count']}")

driver.close()
print("\nNeo4j query complete!")
