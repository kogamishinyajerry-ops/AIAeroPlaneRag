import json
import logging
import re
from pathlib import Path
from typing import Dict, List

from settings import DOCUMENT_VERSION


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class StructuralChunker:
    """
    Chunk markdown documents by structure and preserve document-level metadata
    for later citation and traceability.
    """

    def __init__(self, processed_dir: str = "./data/processed"):
        self.processed_dir = Path(processed_dir)

    def chunk_markdown(self, filename: str) -> List[Dict]:
        filepath = self.processed_dir / filename
        if not filepath.exists():
            logger.error("File not found: %s", filepath)
            return []

        logger.info("Chunking %s based on document structure...", filename)
        content = filepath.read_text(encoding="utf-8")
        doc_meta = self._load_document_metadata(filepath)

        chunks = []
        current_h1 = "Unknown Document"
        current_h2 = "General Chapter"
        current_h3 = "General Clause"
        current_text: List[str] = []

        for raw_line in content.split("\n"):
            line = raw_line.strip()
            h1_match = re.match(r"^#\s+(.+)", line)
            h2_match = re.match(r"^##\s+(.+)", line)
            h3_match = re.match(r"^###\s+(.+)", line)

            if h1_match or h2_match or h3_match:
                if "".join(current_text).strip():
                    chunks.append(
                        self._create_chunk_dict(
                            current_h1,
                            current_h2,
                            current_h3,
                            "\n".join(current_text),
                            filename,
                            filepath,
                            doc_meta,
                        )
                    )
                    current_text = []

                if h1_match:
                    current_h1 = h1_match.group(1)
                    current_h2 = "General Chapter"
                    current_h3 = "General Clause"
                elif h2_match:
                    current_h2 = h2_match.group(1)
                    current_h3 = "General Section"
                elif h3_match:
                    current_h3 = h3_match.group(1)
            elif line:
                current_text.append(line)

        if "".join(current_text).strip():
            chunks.append(
                self._create_chunk_dict(
                    current_h1,
                    current_h2,
                    current_h3,
                    "\n".join(current_text),
                    filename,
                    filepath,
                    doc_meta,
                )
            )

        logger.info("Generated %s structural chunks for %s.", len(chunks), filename)
        return chunks

    def _load_document_metadata(self, filepath: Path) -> Dict:
        sidecar = filepath.with_suffix(".meta.json")
        if sidecar.exists():
            try:
                return json.loads(sidecar.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to read metadata file %s: %s", sidecar, exc)

        first_line = ""
        try:
            first_line = filepath.read_text(encoding="utf-8").splitlines()[0]
        except Exception:
            first_line = ""

        inferred_mode = "mock" if "Mock Extraction" in first_line else "real"
        return {
            "document_id": filepath.stem,
            "document_version": DOCUMENT_VERSION,
            "content_mode": inferred_mode,
            "markdown_path": str(filepath.resolve()),
        }

    def _create_chunk_dict(
        self,
        h1: str,
        h2: str,
        h3: str,
        text: str,
        source: str,
        filepath: Path,
        doc_meta: Dict,
    ) -> Dict:
        contextualized_text = f"[{h1} > {h2} > {h3}]\n{text}"
        return {
            "text": contextualized_text,
            "metadata": {
                "source": source,
                "document": h1,
                "chapter": h2,
                "section": h3,
                "document_id": doc_meta.get("document_id", filepath.stem),
                "document_version": doc_meta.get("document_version", DOCUMENT_VERSION),
                "content_mode": doc_meta.get("content_mode", "unknown"),
                "source_path": doc_meta.get("markdown_path", str(filepath.resolve())),
            },
        }


if __name__ == "__main__":
    chunker = StructuralChunker(processed_dir="../../data/processed")
    chunks = chunker.chunk_markdown("CCAR-33.md")
    for chunk in chunks:
        print(f"--- Meta: {chunk['metadata']} ---\n{chunk['text'][:100]}...\n")
