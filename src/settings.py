import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", DATA_DIR / "raw")).resolve()
PROCESSED_DATA_DIR = Path(os.getenv("PROCESSED_DATA_DIR", DATA_DIR / "processed")).resolve()
CATALOG_DIR = Path(os.getenv("CATALOG_DIR", DATA_DIR / "catalog")).resolve()
CHROMA_DB_DIR = Path(os.getenv("CHROMA_DB_DIR", PROCESSED_DATA_DIR / "chroma_db")).resolve()
APP_MODE = os.getenv("APP_MODE", "mock").strip().lower()
APP_VERSION = os.getenv("APP_VERSION", "0.3.0").strip()
DOCUMENT_VERSION = os.getenv("DOCUMENT_VERSION", "ccar33-enriched-mock-v1").strip()
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "rag-prompt-v2").strip()
EMBEDDING_VERSION = os.getenv("EMBEDDING_VERSION", "simple-hash-v1").strip()
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "focused-subgraph-v3").strip()
SOURCE_CATALOG_VERSION = os.getenv("SOURCE_CATALOG_VERSION", "official-sources-v1").strip()
SOURCE_CATALOG_PATH = Path(
    os.getenv("SOURCE_CATALOG_PATH", CATALOG_DIR / "official_sources.json")
).resolve()


def ensure_data_dirs() -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)


def has_real_value(value: str | None) -> bool:
    if not value:
        return False

    normalized = value.strip()
    if not normalized:
        return False

    placeholders = {
        "your_api_key_here",
        "your_openai_api_key_here",
        "your_zhipu_api_key_here",
        "your_llama_cloud_api_key_here",
        "password",
    }
    return normalized not in placeholders
