"""
Re-index Vector Database with Real CCAR-33-R2 Data

This script clears the existing ChromaDB collection and re-indexes it
with the real CCAR-33-R2 chapter files.
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rag.semantic_chunker import StructuralChunker
from rag.vector_engine import VectorStoreEngine
from settings import PROCESSED_DATA_DIR

# Path to CCAR-33-R2 chapters
CHAPTERS_DIR = PROCESSED_DATA_DIR / "CCAR-33-R2_chapters"

# Chapter files to index (in order)
CHAPTER_FILES = [
    "A-总则.md",
    "B-设计与构造总则.md",
    "C-设计与构造活塞发动机.md",
    "D-台架试验活塞发动机.md",
    "E-设计与构造涡轮发动机.md",
    "F-台架试验涡轮发动机.md",
    "G-ETOPS专用要求.md",
]


def clear_collection(engine: VectorStoreEngine) -> bool:
    """Clear the existing ChromaDB collection."""
    if not engine.client:
        print("[WARN] ChromaDB client not available. Skipping clear.")
        return False

    try:
        # Delete and recreate collection
        engine.client.delete_collection(name=engine.collection_name)
        print(f"[OK] Deleted collection: {engine.collection_name}")

        # Recreate with same embedding function
        from settings import has_real_value
        if has_real_value(os.getenv("OPENAI_API_KEY")):
            from chromadb.utils import embedding_functions
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"
            )
        else:
            openai_ef = engine.collection._embedding_function

        engine.collection = engine.client.get_or_create_collection(
            name=engine.collection_name,
            embedding_function=openai_ef
        )
        print(f"[OK] Recreated collection: {engine.collection_name}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to clear collection: {e}")
        return False


def index_chapters(engine: VectorStoreEngine, chunker: StructuralChunker) -> dict:
    """Index all CCAR-33-R2 chapter files."""
    results = {
        "total_chunks": 0,
        "files_processed": [],
        "errors": []
    }

    chapters_path = PROCESSED_DATA_DIR / "CCAR-33-R2_chapters"
    if not chapters_path.exists():
        results["errors"].append(f"Chapters directory not found: {chapters_path}")
        return results

    for filename in CHAPTER_FILES:
        filepath = chapters_path / filename
        if not filepath.exists():
            results["errors"].append(f"File not found: {filename}")
            continue

        print(f"\n[PROCESS] {filename}")
        try:
            chunks = chunker.chunk_markdown(f"CCAR-33-R2_chapters/{filename}")
            if chunks:
                # Update metadata to reflect real source
                for chunk in chunks:
                    chunk["metadata"]["content_mode"] = "real"
                    chunk["metadata"]["document_version"] = "CCAR-33-R2-2016"

                engine.index_chunks(chunks)
                results["total_chunks"] += len(chunks)
                results["files_processed"].append({
                    "file": filename,
                    "chunks": len(chunks)
                })
                print(f"[OK] Indexed {len(chunks)} chunks from {filename}")
            else:
                results["errors"].append(f"No chunks generated from {filename}")
        except Exception as e:
            results["errors"].append(f"Error processing {filename}: {e}")
            print(f"[ERROR] Failed to process {filename}: {e}")

    return results


def main():
    print("=" * 60)
    print(" CCAR-33-R2 Vector Database Re-Indexing")
    print("=" * 60)

    # Initialize components
    print("\n[INIT] Initializing vector engine...")
    engine = VectorStoreEngine(db_dir=str(PROCESSED_DATA_DIR / "chroma_db"))

    print("[INIT] Initializing structural chunker...")
    chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))

    # Clear existing collection
    print("\n[CLEAR] Clearing existing collection...")
    if not clear_collection(engine):
        print("[WARN] Proceeding without clearing...")

    # Index chapters
    print("\n[INDEX] Indexing CCAR-33-R2 chapters...")
    results = index_chapters(engine, chunker)

    # Summary
    print("\n" + "=" * 60)
    print(" RE-INDEXING SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {len(results['files_processed'])}")
    print(f"Total chunks indexed: {results['total_chunks']}")

    if results['files_processed']:
        print("\nFile breakdown:")
        for item in results['files_processed']:
            print(f"  - {item['file']}: {item['chunks']} chunks")

    if results['errors']:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results['errors']:
            print(f"  - {error}")

    # Verify indexing
    if engine.collection:
        try:
            count = engine.collection.count()
            print(f"\n[VERIFY] Collection count: {count} chunks")
        except Exception as e:
            print(f"[WARN] Could not verify count: {e}")

    print("\n[DONE] Re-indexing complete!")


if __name__ == "__main__":
    main()
