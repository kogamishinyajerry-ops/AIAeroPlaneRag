"""Run the entity extraction pipeline."""
import sys
import os
import json
import traceback

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from settings import PROCESSED_DATA_DIR

try:
    from ontology.entity_extractor import LLMEntityExtractor
    print("[OK] LLMEntityExtractor imported.")
except Exception as e:
    print(f"[ERROR] Import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    extractor = LLMEntityExtractor()
    print("[OK] Extractor initialized.")

    ccar33_path = PROCESSED_DATA_DIR / "CCAR-33.md"
    if not ccar33_path.exists():
        print(f"[ERROR] File not found: {ccar33_path}")
        sys.exit(1)

    print(f"[INFO] Processing {ccar33_path}...")
    graph_data = extractor.extract_from_document(str(ccar33_path))

    entity_count = len(graph_data.get("entities", []))
    rel_count = len(graph_data.get("relationships", []))

    print(f"\n{'='*60}")
    print(f" EXTRACTION COMPLETE")
    print(f" Entities:      {entity_count}")
    print(f" Relationships: {rel_count}")
    print(f"{'='*60}")

    # Print entity summary
    types = {}
    for e in graph_data.get("entities", []):
        t = e.get("type", "Unknown")
        types[t] = types.get(t, 0) + 1

    print("\nEntity Breakdown:")
    for t, c in sorted(types.items()):
        print(f"  {t}: {c}")

    # Print first few relationships
    print("\nSample Relationships:")
    for r in graph_data.get("relationships", [])[:10]:
        print(f"  {r['source']} --[{r['type']}]--> {r['target']}")

    # Try loading to Neo4j
    extractor.load_to_neo4j(graph_data)
    extractor.close()

except Exception as e:
    print(f"[ERROR] Extraction failed: {e}")
    traceback.print_exc()
    sys.exit(1)
