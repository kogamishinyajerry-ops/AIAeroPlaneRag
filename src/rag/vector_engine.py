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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def tokenize_text(text: str) -> List[str]:
    tokens: List[str] = []
    buffer = []

    def flush_buffer():
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in text.lower():
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
    for block in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        parts = re.split(r"(?:的是|什么|要求|如何|哪些|多少|是否|吗|？|\?)", block)
        phrases.extend(part for part in parts if len(part) >= 2)
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

            norm = sum(v * v for v in vector) ** 0.5 or 1.0
            embeddings.append([v / norm for v in vector])
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
    Handles indexing of document chunks into a vector database (ChromaDB) 
    for semantic retrieval based on engineer queries.
    """
    def __init__(self, db_dir: str = "./data/processed/chroma_db", collection_name: str = "regulations"):
        if load_dotenv:
            load_dotenv()
            
        configured_dir = os.getenv("CHROMA_DB_DIR", db_dir)
        self.db_dir = str(Path(configured_dir).resolve())
        self.collection_name = collection_name
        self._indexed_cache: List[Dict] = []
        
        if not chromadb:
            logger.warning("chromadb is not installed. Running in mock mode.")
            self.collection = None
            return

        self._repair_broken_store()

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=self.db_dir)
        
        # Determine embedding function (OpenAI by default if API key exists, otherwise local fallback)
        openai_ef = None
        if has_real_value(os.getenv("OPENAI_API_KEY")):
            logger.info("Using OpenAI embeddings.")
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"
            )
        else:
            logger.info("OPENAI_API_KEY not found. Using offline hash embeddings.")
            openai_ef = SimpleHashEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name, 
            embedding_function=openai_ef
        )
        logger.info(f"Initialized ChromaDB collection: {self.collection_name}")

    def _repair_broken_store(self):
        """Remove obviously broken sqlite artifacts before Chroma starts."""
        db_path = Path(self.db_dir)
        db_path.mkdir(parents=True, exist_ok=True)

        sqlite_file = db_path / "chroma.sqlite3"
        journal_file = db_path / "chroma.sqlite3-journal"

        if sqlite_file.exists() and sqlite_file.stat().st_size == 0:
            logger.warning("Detected a zero-byte Chroma sqlite file. Rebuilding store directory.")
            sqlite_file.unlink(missing_ok=True)
            journal_file.unlink(missing_ok=True)

    def index_chunks(self, chunks: List[Dict]):
        """
        Takes structured chunks (from StructuralChunker) and indexes them into ChromaDB.
        """
        if not self.collection:
            logger.info(f"Mock Indexing: Would have indexed {len(chunks)} chunks.")
            return

        if not chunks:
            logger.warning("No chunks provided to index.")
            return

        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        # Generate unique IDs based on source and section (Simplified for MVP)
        ids = [f"{c['metadata']['source']}_{c['metadata']['chapter']}_{idx}" for idx, c in enumerate(chunks)]

        logger.info(f"Indexing {len(documents)} document chunks into the database...")
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        self._indexed_cache = [
            {"text": doc, "metadata": meta, "id": chunk_id}
            for doc, meta, chunk_id in zip(documents, metadatas, ids)
        ]
        logger.info("Indexing complete.")

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Perform a semantic search for the most relevant regulations.
        """
        if not self.collection:
            logger.info(f"Mock Search Execution for query: '{query}'")
            return [{"text": "Mock retrieved document segment", "metadata": {"source": "CCAR-33_mock"}}]

        logger.info(f"Executing semantic search for: '{query}'")
        results = self.collection.query(
            query_texts=[query],
            n_results=max(top_k * 3, top_k)
        )
        
        retrieved_items = []
        if results and "documents" in results and results["documents"]:
            for i in range(len(results["documents"][0])):
                retrieved_items.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "id": results["ids"][0][i]
                })

        reranked = self._rerank_by_keywords(query, retrieved_items, top_k)
        if reranked:
            return reranked

        if self._indexed_cache:
            return self._rerank_by_keywords(query, self._indexed_cache, top_k)

        return retrieved_items[:top_k]

    def _rerank_by_keywords(self, query: str, items: List[Dict], top_k: int) -> List[Dict]:
        if not items:
            return []

        query_tokens = set(tokenize_text(query))
        phrase_candidates = extract_phrase_candidates(query)
        if not query_tokens:
            return items[:top_k]

        scored = []
        for item in items:
            metadata = item.get("metadata", {})
            haystack = " ".join(
                [
                    item.get("text", ""),
                    metadata.get("chapter", ""),
                    metadata.get("section", ""),
                    metadata.get("document", ""),
                ]
            ).lower()
            score = sum(1 for token in query_tokens if token and token in haystack)

            section_text = f"{metadata.get('chapter', '')} {metadata.get('section', '')}".lower()
            for phrase in phrase_candidates:
                phrase_lower = phrase.lower()
                if phrase_lower in section_text:
                    score += 10
                elif phrase_lower in haystack:
                    score += 4

            scored.append((score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for score, item in scored if score > 0][:top_k] or [item for _, item in scored[:top_k]]

if __name__ == "__main__":
    from semantic_chunker import StructuralChunker
    
    # 1. Chunk document
    chunker = StructuralChunker(processed_dir="../../data/processed")
    chunks = chunker.chunk_markdown("CCAR-33.md")
    
    # 2. Index into Vector DB
    engine = VectorStoreEngine(db_dir="../../data/processed/chroma_db")
    engine.index_chunks(chunks)
    
    # 3. Test Retrieval
    results = engine.search("什么是压气机的喘振裕度要求？")
    print(f"\n--- Search Results for '什么是压气机的喘振裕度要求？' ---")
    for r in results:
        print(f"Source: {r['metadata']}")
        print(f"Content Outline: {r['text'][:100]}...\n")
