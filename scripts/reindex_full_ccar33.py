"""Re-index complete CCAR-33-R2 to vector database."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.semantic_chunker import StructuralChunker
from rag.vector_engine import VectorStoreEngine
from settings import PROCESSED_DATA_DIR

print("=" * 60)
print(" Re-indexing Complete CCAR-33-R2")
print("=" * 60)

# Path to full official file
raw_file = Path(__file__).parent.parent / "data" / "raw" / "CCAR-33-R2_official_full.md"

if not raw_file.exists():
    print(f"[ERROR] File not found: {raw_file}")
    sys.exit(1)

print(f"\n[FILE] {raw_file}")
print(f"[SIZE] {raw_file.stat().st_size:,} bytes")

# Chunk the document
print("\n[CHUNK] Processing document...")
chunker = StructuralChunker(processed_dir=str(raw_file.parent))
chunks = chunker.chunk_markdown("CCAR-33-R2_official_full.md")
print(f"[OK] Generated {len(chunks)} chunks")

# Index to vector DB
print("\n[INDEX] Loading to vector database...")
engine = VectorStoreEngine(db_dir=str(PROCESSED_DATA_DIR / "chroma_db"))
engine.index_chunks(chunks)
print(f"[OK] Indexed {len(chunks)} chunks")

# Verify
if engine.collection:
    count = engine.collection.count()
    print(f"\n[VERIFY] Collection now has {count} chunks")

print("\n[DONE] Re-indexing complete!")
