from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag.semantic_chunker import StructuralChunker


def test_chunk_markdown_splits_by_headers(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    markdown = """# CCAR-33 Sample
## Chapter 1
### Clause 1
The compressor must maintain surge margin.
## Chapter 2
### Clause 2
The turbine disk must pass overspeed tests.
"""
    (processed_dir / "sample.md").write_text(markdown, encoding="utf-8")

    chunker = StructuralChunker(processed_dir=str(processed_dir))
    chunks = chunker.chunk_markdown("sample.md")

    assert len(chunks) == 2
    assert chunks[0]["metadata"]["source"] == "sample.md"
    assert chunks[0]["metadata"]["chapter"] == "Chapter 1"
    assert chunks[0]["metadata"]["section"] == "Clause 1"
    assert chunks[0]["text"].startswith("[CCAR-33 Sample > Chapter 1 > Clause 1]")
    assert "surge margin" in chunks[0]["text"]
    assert chunks[1]["metadata"]["chapter"] == "Chapter 2"
    assert chunks[1]["metadata"]["section"] == "Clause 2"


def test_chunk_markdown_missing_file_returns_empty_list(tmp_path):
    chunker = StructuralChunker(processed_dir=str(tmp_path))

    assert chunker.chunk_markdown("missing.md") == []
