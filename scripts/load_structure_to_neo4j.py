"""Load CCAR-33-R2 structured data to Neo4j."""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

try:
    from neo4j import GraphDatabase
except ImportError:
    print("[ERROR] neo4j not installed")
    sys.exit(1)

# Neo4j connection
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "aeropower_rag_2026")

# Load structure file
structure_file = Path(__file__).parent.parent / "data" / "processed" / "CCAR-33-R2_structure.json"
with open(structure_file, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 60)
print(" Loading CCAR-33-R2 Structure to Neo4j")
print("=" * 60)

# Connect
driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    # Clear
    print("\n[CLEAN] Clearing existing data...")
    session.run("MATCH (n) DETACH DELETE n")

    # Track stats
    stats = {
        "regulations": 0,
        "paragraphs": 0,
        "entities": 0,
        "references": 0
    }

    # Load chapters and sections
    print("\n[LOAD] Loading regulations...")
    for chapter in data.get("chapters", []):
        chapter_id = chapter.get("chapter_id")
        chapter_title = chapter.get("chapter_title")

        # Create chapter node
        session.run("""
            MERGE (ch:Chapter {id: $id})
            SET ch.title = $title
        """, id=chapter_id, title=chapter_title)

        for section in chapter.get("sections", []):
            section_id = section.get("section_id")
            section_title = section.get("section_title")

            # Create section node
            session.run("""
                MERGE (s:Section {id: $id})
                SET s.title = $title,
                    s.chapter_id = $chapter_id
            """, id=section_id, title=section_title, chapter_id=chapter_id)

            # Link chapter to section
            session.run("""
                MATCH (ch:Chapter {id: $chapter_id})
                MATCH (s:Section {id: $section_id})
                MERGE (ch)-[:HAS_SECTION]->(s)
            """, chapter_id=chapter_id, section_id=section_id)

            stats["regulations"] += 1

            # Load paragraphs and entities
            for para in section.get("paragraphs", []):
                para_id = para.get("paragraph_id")
                content = para.get("content", "")

                # Create paragraph node
                session.run("""
                    MERGE (p:Paragraph {id: $id})
                    SET p.content = $content
                """, id=para_id, content=content[:500])

                # Link to section
                session.run("""
                    MATCH (s:Section {id: $section_id})
                    MATCH (p:Paragraph {id: $para_id})
                    MERGE (s)-[:HAS_PARAGRAPH]->(p)
                """, section_id=section_id, para_id=para_id)

                stats["paragraphs"] += 1

                # Entities
                for entity in para.get("key_entities", []):
                    session.run("""
                        MERGE (e:Entity {name: $name})
                        SET e.type = 'concept'
                    """, name=entity)

                    # Link
                    session.run("""
                        MATCH (p:Paragraph {id: $para_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (p)-[:MENTIONS]->(e)
                    """, para_id=para_id, name=entity)

                    stats["entities"] += 1

                # References
                for ref in para.get("references", []):
                    session.run("""
                        MERGE (r:Reference {name: $name})
                    """, name=ref)

                    session.run("""
                        MATCH (p:Paragraph {id: $para_id})
                        MATCH (r:Reference {name: $name})
                        MERGE (p)-[:REFERS_TO]->(r)
                    """, para_id=para_id, name=ref)

                    stats["references"] += 1

    # Load entities from CSV data
    entities_file = Path(__file__).parent.parent / "data" / "processed" / "CCAR-33-R2_entities.csv"
    if entities_file.exists():
        print("\n[LOAD] Loading entities from CSV...")
        import csv
        with open(entities_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entity_type = row.get("entity_type", "Entity")
                entity_name = row.get("entity_name", "")
                section_ref = row.get("section_reference", "")
                description = row.get("description", "")

                session.run("""
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type,
                        e.description = $description
                """, name=entity_name, type=entity_type, description=description)

                if section_ref:
                    session.run("""
                        MATCH (s:Section {id: $section_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (s)-[:DEFINES]->(e)
                    """, section_id=section_ref, name=entity_name)

    # Load references
    refs_file = Path(__file__).parent.parent / "data" / "processed" / "CCAR-33-R2_references.csv"
    if refs_file.exists():
        print("\n[LOAD] Loading references from CSV...")
        with open(refs_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                source = row.get("source_section", "")
                target = row.get("target_section", "")
                ref_type = row.get("reference_type", "REFERS_TO")

                if source and target:
                    session.run("""
                        MATCH (s:Section {id: $source})
                        MATCH (t:Section {id: $target})
                        MERGE (s)-[r:REFERS_TO]->(t)
                        SET r.type = $type
                    """, source=source, target=target, type=ref_type)

    # Verify
    result = session.run("MATCH (n) RETURN count(n) as count")
    node_count = result.single()["count"]
    result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
    rel_count = result.single()["count"] if result.single() else 0

    print(f"\n[STATS]")
    print(f"  Regulations loaded: {stats['regulations']}")
    print(f"  Paragraphs loaded: {stats['paragraphs']}")
    print(f"  Entities loaded: {stats['entities']}")
    print(f"  References loaded: {stats['references']}")
    print(f"\n[VERIFY] Total nodes: {node_count}, relationships: {rel_count}")

driver.close()

print("\n[DONE] Structure loaded to Neo4j!")
print(f"\nExplore at: http://localhost:7474")
print(f"  User: {user}")
print(f"  Password: {password}")
