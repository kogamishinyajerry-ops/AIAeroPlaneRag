from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


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

    def search(self, query: str, top_k: int = 3):
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
    root = Path(__file__).resolve().parents[1]
    src_dir = root / "src"
    rag_dir = src_dir / "rag"
    ontology_dir = src_dir / "ontology"

    for module_name in [
        "main",
        "settings",
        "rag",
        "rag.vector_engine",
        "rag.guardrail",
        "ontology",
        "ontology.graph_store",
    ]:
        sys.modules.pop(module_name, None)

    rag_package = ModuleType("rag")
    rag_package.__path__ = [str(rag_dir)]
    ontology_package = ModuleType("ontology")
    ontology_package.__path__ = [str(ontology_dir)]
    sys.modules["rag"] = rag_package
    sys.modules["ontology"] = ontology_package

    vector_engine_module = ModuleType("rag.vector_engine")
    vector_engine_module.VectorStoreEngine = FakeVectorStoreEngine
    guardrail_module = ModuleType("rag.guardrail")
    guardrail_module.FactCheckingGuardrail = FakeGuardrail
    graph_store_module = ModuleType("ontology.graph_store")
    graph_store_module.OntologyGraphStore = FakeGraphStore
    sys.modules["rag.vector_engine"] = vector_engine_module
    sys.modules["rag.guardrail"] = guardrail_module
    sys.modules["ontology.graph_store"] = graph_store_module

    monkeypatch.syspath_prepend(str(src_dir))
    return importlib.import_module("main")
