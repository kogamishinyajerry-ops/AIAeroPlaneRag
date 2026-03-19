import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from settings import APP_MODE, DOCUMENT_VERSION, has_real_value

try:
    from llama_index.core import SimpleDirectoryReader
    from llama_parse import LlamaParse
except ImportError:
    LlamaParse = None
    SimpleDirectoryReader = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HighFidelityParser:
    """
    Parse aviation regulation documents into markdown while clearly separating
    real extraction from mock fallback behavior.
    """

    def __init__(self, raw_dir: str = "./data/raw", processed_dir: str = "./data/processed"):
        load_dotenv()
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.run_mode = APP_MODE
        self.document_version = DOCUMENT_VERSION
        self.api_key = os.getenv("LLAMA_CLOUD_API_KEY") if "os" in globals() else None

        if LlamaParse and has_real_value(self.api_key):
            self.parser = LlamaParse(
                api_key=self.api_key,
                result_type="markdown",
                verbose=True,
                language="zh",
                num_workers=4,
            )
        else:
            self.parser = None
            logger.warning("LlamaParse is unavailable or not configured with a real key.")

    def parse_document(self, filename: str, allow_mock: bool | None = None):
        filepath = self.raw_dir / filename
        if not filepath.exists():
            logger.error("File %s does not exist.", filepath)
            return []

        real_available = self._real_parse_available()
        if allow_mock is None:
            allow_mock = self.run_mode != "real"

        logger.info("Starting parsing of %s with app mode '%s'.", filename, self.run_mode)

        if real_available:
            documents = self._real_parse(filename, filepath)
            if documents:
                return documents
            if not allow_mock:
                raise RuntimeError("Real parsing failed and mock fallback is disabled.")

        if not allow_mock:
            raise RuntimeError("Real parsing is required but LlamaParse is not available.")

        logger.info("Falling back to mock parsing for development mode.")
        return self._mock_parse(filename)

    def _real_parse_available(self) -> bool:
        return bool(self.parser and SimpleDirectoryReader)

    def _real_parse(self, filename: str, filepath: Path):
        file_extractor = {".pdf": self.parser}
        try:
            reader = SimpleDirectoryReader(input_files=[str(filepath)], file_extractor=file_extractor)
            documents = reader.load_data()
            logger.info("Successfully extracted %s objects from %s.", len(documents), filename)
            self._save_markdown(filename, documents, content_mode="real", parser_name="llama_parse")
            return documents
        except Exception as exc:
            logger.error("Error during parsing %s: %s", filename, exc)
            return []

    def _save_markdown(self, filename: str, documents: list, content_mode: str, parser_name: str):
        stem = Path(filename).stem
        markdown_path = self.processed_dir / f"{stem}.md"
        full_text = "\n\n".join([doc.text for doc in documents])
        with open(markdown_path, "w", encoding="utf-8") as handle:
            handle.write(full_text)
        self._save_metadata(stem, filename, content_mode, parser_name, markdown_path)
        logger.info("Saved extracted markdown to %s", markdown_path)

    def _save_metadata(
        self,
        stem: str,
        source_filename: str,
        content_mode: str,
        parser_name: str,
        markdown_path: Path,
    ) -> None:
        metadata_path = self.processed_dir / f"{stem}.meta.json"
        metadata = {
            "document_id": stem,
            "source_filename": source_filename,
            "markdown_path": str(markdown_path.resolve()),
            "content_mode": content_mode,
            "document_version": self.document_version,
            "parser": parser_name,
            "app_mode": self.run_mode,
        }
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)

    def _mock_parse(self, filename: str):
        stem = Path(filename).stem
        mock_content = f"""# {stem} (Mock Extraction)

## 第三章 压气机

### 第 33.21 条 压气机设计要求
压气机必须被设计为能够在整个工作包线内承受所有产生的气动力、离心力和热应力。
压气机叶片必须具有足够的抗外物损伤能力。

### 第 33.23 条 喘振裕度
压气机在所有预期的飞行条件和发动机瞬变工况下，必须保持足够的喘振裕度，以防止压气机喘振。
对于典型民用涡扇发动机，巡航状态喘振裕度建议不低于 15%，起飞状态不低于 10%。
畸变进气条件下的喘振裕度需额外考虑，应通过进气畸变试验验证。
"""
        markdown_path = self.processed_dir / f"{stem}.md"
        with open(markdown_path, "w", encoding="utf-8") as handle:
            handle.write(mock_content)
        self._save_metadata(stem, filename, "mock", "mock_parser", markdown_path)
        logger.info("Saved mock markdown to %s", markdown_path)
        return [{"text": mock_content, "metadata": {"source": filename, "content_mode": "mock"}}]


if __name__ == "__main__":
    parser = HighFidelityParser(raw_dir="../../data/raw", processed_dir="../../data/processed")
    dummy_pdf = parser.raw_dir / "CCAR-33.pdf"
    if not dummy_pdf.exists():
        dummy_pdf.touch()
    parser.parse_document("CCAR-33.pdf")
