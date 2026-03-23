"""Debug Neo4j data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase
import os

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

print(f"Connecting to {uri}...")

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    # Get all keys
    result = session.run("MATCH (n) RETURN keys(n) AS keys LIMIT 1")
    keys = result.single()
    print(f"Node keys: {keys}")

    # Get raw nodes
    result = session.run("MATCH (n) RETURN n LIMIT 5")
    print("\nRaw nodes:")
    for record in result:
        node = record["n"]
        print(f"  {dict(node)}")

driver.close()
