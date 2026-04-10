from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeCollection:
    def __init__(self, count: int = 2):
        self._count = count
        self.added = []

    def count(self) -> int:
        return self._count

    def add(self, *, documents, metadatas, ids):
        self.added.append({"documents": documents, "metadatas": metadatas, "ids": ids})
        self._count += len(documents)


class FakeVectorStoreEngine:
    def __init__(self, db_dir: str = "./data/processed/chroma_db", collection_name: str = "regulations"):
        self.db_dir = db_dir
        self.collection_name = collection_name
        self.collection = FakeCollection()
        self.indexed_chunks = []
        self.search_results = []

    def index_chunks(self, chunks):
        self.indexed_chunks = list(chunks)
        self.collection.add(
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[chunk["metadata"] for chunk in chunks],
            ids=[chunk["metadata"].get("chunk_id", f"chunk-{index}") for index, chunk in enumerate(chunks)],
        )

    def _recreate_collection(self):
        self.collection = FakeCollection()

    def search(self, query: str, top_k: int = 3):
        return list(self.search_results)[:top_k]

    def search_hybrid(self, query: str, top_k: int = 3):
        return list(self.search_results)[:top_k]



class FakeGraphStore:
    def __init__(self):
        self.driver = None
        self.has_graph_data = False
        self.node_count = 0

    def query_graph(self, keyword: str):
        return []

    def get_graph_snapshot(self):
        return {
            "mode": "fallback",
            "summary": "test graph snapshot",
            "nodes": [
                {"id": "reg-1", "label": "Clause 1", "type": "regulation", "description": "Clause 1"},
                {"id": "comp-1", "label": "Compressor", "type": "component", "description": "Compressor"},
            ],
            "edges": [{"source": "reg-1", "target": "comp-1", "type": "CONSTRAINS", "description": ""}],
            "stats": {"nodeCount": 2, "edgeCount": 1},
        }

    def get_subgraph(self, *, query: str = "", node_id: str | None = None, limit: int = 18, include_parameters: bool = False):
        return {
            "mode": "fallback",
            "query": query,
            "focusNodeId": node_id or "reg-1",
            "summary": "test graph subgraph",
            "nodes": [
                {"id": "reg-1", "label": "Clause 1", "type": "regulation", "description": "Clause 1"},
                {"id": "comp-1", "label": "Compressor", "type": "component", "description": "Compressor"},
            ],
            "edges": [{"source": "reg-1", "target": "comp-1", "type": "CONSTRAINS", "description": ""}],
            "stats": {"nodeCount": 2, "edgeCount": 1},
        }


class FakeGuardrail:
    def __init__(self):
        self.has_external_verifier = False

    def verify_response(self, query, generated_answer, retrieved_contexts):
        return {
            "status": "PASS",
            "reasoning": "verified locally in test",
            "safe_answer": generated_answer,
        }


@pytest.fixture
def main_module(monkeypatch):
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("src."):
            sys.modules.pop(mod, None)

    import importlib
    main = importlib.import_module("src.main")
    
    # Patch ServiceContainer for direct service property access
    from src.api.dependencies.deps import services, get_vector_engine, get_guardrail
    services._vector_engine = FakeVectorStoreEngine()
    services._graph_store = FakeGraphStore()
    services._guardrail = FakeGuardrail()
    services.is_initialized = True
    
    # Override FastAPI Dependencies to return the EXACT same fakes
    main.app.dependency_overrides[get_vector_engine] = lambda: services._vector_engine
    main.app.dependency_overrides[get_guardrail] = lambda: services._guardrail

    
    # Patch original intent detector reference
    try:
        from src.rag import vector_engine
        vector_engine.detect_query_intent = lambda query: {"regulatory": 1.0}
    except ImportError:
        pass
        
    return main
