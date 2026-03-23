import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

from settings import has_real_value

try:
    import chromadb
    from chromadb.utils import embedding_functions
    from dotenv import load_dotenv
except ImportError:
    chromadb = None
    embedding_functions = None
    load_dotenv = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def tokenize_text(text: str) -> List[str]:
    tokens: List[str] = []
    buffer: List[str] = []

    def flush_buffer() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in (text or "").lower():
        if "\u4e00" <= char <= "\u9fff":
            flush_buffer()
            tokens.append(char)
        elif char.isalnum() or char == "_":
            buffer.append(char)
        else:
            flush_buffer()

    flush_buffer()
    return [token for token in tokens if token.strip()]


def extract_phrase_candidates(text: str) -> List[str]:
    phrases: List[str] = []
    for block in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9_\-]{2,}", text or ""):
        if len(block) >= 2:
            phrases.append(block.lower())
    return list(dict.fromkeys(phrases))


class SimpleHashEmbeddingFunction:
    """Offline-safe embedding fallback for local development."""

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in input:
            vector = [0.0] * self.dimension
            tokens = tokenize_text(text)
            if not tokens:
                embeddings.append(vector)
                continue

            for token in tokens:
                slot = hash(token) % self.dimension
                vector[slot] += 1.0

            norm = sum(value * value for value in vector) ** 0.5 or 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings

    def embed_query(self, input: List[str]) -> List[List[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "simple_hash"

    @staticmethod
    def build_from_config(config):
        return SimpleHashEmbeddingFunction(dimension=config.get("dimension", 256))

    def get_config(self):
        return {"dimension": self.dimension}


class VectorStoreEngine:
    """
    Handles indexing of document chunks into a vector database for semantic retrieval.
    """

    def __init__(self, db_dir: str = "./data/processed/chroma_db", collection_name: str = "regulations"):
        if load_dotenv:
            load_dotenv()

        configured_dir = os.getenv("CHROMA_DB_DIR", db_dir)
        self.db_dir = str(Path(configured_dir).resolve())
        self.collection_name = collection_name
        self._indexed_cache: Dict[str, Dict] = {}
        self._query_cache: Dict[tuple[str, int], List[Dict]] = {}

        if not chromadb:
            logger.warning("chromadb is not installed. Running in mock mode.")
            self.collection = None
            return

        self._repair_broken_store()
        self.client = chromadb.PersistentClient(path=self.db_dir)

        embedding_function = None
        if has_real_value(os.getenv("OPENAI_API_KEY")):
            logger.info("Using OpenAI embeddings.")
            embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small",
            )
        else:
            logger.info("OPENAI_API_KEY not found. Using offline hash embeddings.")
            embedding_function = SimpleHashEmbeddingFunction()
        self.embedding_function = embedding_function

        self.collection = self.client.get_or_create_collection(name=self.collection_name, embedding_function=embedding_function)
        logger.info("Initialized ChromaDB collection: %s", self.collection_name)

    def _repair_broken_store(self) -> None:
        db_path = Path(self.db_dir)
        db_path.mkdir(parents=True, exist_ok=True)

        sqlite_file = db_path / "chroma.sqlite3"
        journal_file = db_path / "chroma.sqlite3-journal"
        if sqlite_file.exists() and sqlite_file.stat().st_size == 0:
            logger.warning("Detected a zero-byte Chroma sqlite file. Rebuilding store directory.")
            sqlite_file.unlink(missing_ok=True)
            journal_file.unlink(missing_ok=True)

    def _make_chunk_id(self, chunk: Dict, index: int) -> str:
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "unknown")
        chapter = metadata.get("chapter", "")
        section = metadata.get("section", "")
        text = chunk.get("original_text") or chunk.get("text", "")
        stable_input = f"{source}|{chapter}|{section}|{text[:256]}|{index}"
        digest = hashlib.sha1(stable_input.encode("utf-8")).hexdigest()[:16]
        return f"{Path(source).stem}:{digest}"

    def index_chunks(self, chunks: List[Dict]) -> None:
        if not self.collection:
            logger.info("Mock Indexing: Would have indexed %s chunks.", len(chunks))
            return

        if not chunks:
            logger.warning("No chunks provided to index.")
            return

        normalized_chunks: List[Dict] = []
        seen_ids = set()
        for index, chunk in enumerate(chunks):
            chunk_id = chunk.get("metadata", {}).get("chunk_id") or self._make_chunk_id(chunk, index)
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)

            metadata = dict(chunk.get("metadata", {}))
            metadata["chunk_id"] = chunk_id
            normalized_chunks.append(
                {
                    "id": chunk_id,
                    "text": chunk.get("text", ""),
                    "original_text": chunk.get("original_text", ""),
                    "metadata": metadata,
                }
            )

        documents = [chunk["text"] for chunk in normalized_chunks]
        metadatas = [chunk["metadata"] for chunk in normalized_chunks]
        ids = [chunk["id"] for chunk in normalized_chunks]

        logger.info("Indexing %s document chunks into the database...", len(normalized_chunks))
        self._recreate_collection()
        if hasattr(self.collection, "upsert"):
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        else:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

        self._indexed_cache = {chunk["id"]: chunk for chunk in normalized_chunks}
        self._query_cache.clear()
        logger.info("Indexing complete.")

    def _recreate_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
        )

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.collection:
            logger.info("Mock Search Execution for query: '%s'", query)
            return [{"text": "Mock retrieved document segment", "metadata": {"source": "CCAR-33_mock"}}]

        cache_key = ((query or "").strip().lower(), top_k)
        if cache_key in self._query_cache:
            return list(self._query_cache[cache_key])

        candidate_count = max(top_k * 2, min(top_k * 4, 12))
        logger.info("Executing semantic search for: '%s'", query)
        results = self.collection.query(query_texts=[query], n_results=candidate_count)

        retrieved_items: List[Dict] = []
        if results and results.get("documents"):
            for index in range(len(results["documents"][0])):
                item = {
                    "text": results["documents"][0][index],
                    "metadata": results["metadatas"][0][index],
                    "id": results["ids"][0][index],
                }
                cached = self._indexed_cache.get(item["id"])
                if cached and cached.get("original_text"):
                    item["original_text"] = cached["original_text"]
                retrieved_items.append(item)

        reranked = self._rerank_by_keywords(query, retrieved_items, top_k)
        final_items = reranked[:top_k] if reranked else retrieved_items[:top_k]
        self._query_cache[cache_key] = list(final_items)
        return final_items

    def _rerank_by_keywords(self, query: str, items: List[Dict], top_k: int) -> List[Dict]:
        if not items:
            return []

        query_tokens = [token for token in tokenize_text(query) if len(token) > 1 or "\u4e00" <= token <= "\u9fff"]
        phrase_candidates = extract_phrase_candidates(query)[:6]
        if not query_tokens and not phrase_candidates:
            return items[:top_k]

        scored: List[tuple[int, Dict]] = []
        for item in items[: max(top_k * 3, 8)]:
            metadata = item.get("metadata", {})
            searchable_parts = [
                metadata.get("chapter", ""),
                metadata.get("section", ""),
                metadata.get("document", ""),
                item.get("text", "")[:800],
            ]
            haystack = " ".join(searchable_parts).lower()
            score = 0

            for token in query_tokens:
                if token in haystack:
                    score += 2 if len(token) == 1 else 4

            section_text = f"{metadata.get('chapter', '')} {metadata.get('section', '')}".lower()
            for phrase in phrase_candidates:
                if phrase in section_text:
                    score += 8
                elif phrase in haystack:
                    score += 3

            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        positive = [item for score, item in scored if score > 0]
        return positive[:top_k] if positive else [item for _, item in scored[:top_k]]


if __name__ == "__main__":
    from semantic_chunker import StructuralChunker

    chunker = StructuralChunker(processed_dir="../../data/processed")
    chunks = chunker.chunk_markdown("CCAR-33.md")

    engine = VectorStoreEngine(db_dir="../../data/processed/chroma_db")
    engine.index_chunks(chunks)

    results = engine.search("压气机的喘振裕度要求是什么？")
    print("\n--- Search Results for '压气机的喘振裕度要求是什么？' ---")
    for item in results:
        print(f"Source: {item['metadata']}")
        print(f"Content Outline: {item['text'][:100]}...\n")
