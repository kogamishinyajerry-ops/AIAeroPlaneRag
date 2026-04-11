import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter
from src.settings import (
    APP_VERSION, EMBEDDING_VERSION, APP_MODE, DOCUMENT_VERSION, PROMPT_VERSION,
    GRAPH_VERSION, SOURCE_CATALOG_VERSION, SOURCE_CATALOG_PATH, CHROMA_DB_DIR, PROCESSED_DATA_DIR
)
from src.api.dependencies.deps import services

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
def root() -> Dict[str, str]:
    return {"service": "AeroPower-RAG", "version": APP_VERSION, "status": "operational"}


def _probe_ollama(base_url: str = "http://localhost:11434", timeout: float = 2.0) -> str:
    """Return 'available' if Ollama responds, 'unavailable' otherwise."""
    try:
        import requests as _req
        r = _req.get(f"{base_url}/api/tags", timeout=timeout)
        return "available" if r.status_code == 200 else "degraded"
    except Exception:
        return "unavailable"


def _count_indexable_chunks() -> int:
    """
    Count chunks available on disk (non-blocking).
    Scans all *_chunks.json files in PROCESSED_DATA_DIR (top-level and one level deep)
    plus the EASA chunks_full.json. Used as authoritative count when ChromaDB is
    disconnected, so /health always returns a meaningful integer.
    Returns 0 on any error.
    """
    try:
        import json
        total = 0
        seen: set = set()

        # Top-level *_chunks.json files (AC + FAR-33 etc.)
        for f in sorted(PROCESSED_DATA_DIR.glob("*_chunks.json")):
            key = str(f)
            if key in seen:
                continue
            seen.add(key)
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                total += len(data) if isinstance(data, list) else 0
            except Exception:
                pass

        # Subdirectory chunks (easa_cse/, etc.)
        for f in sorted(PROCESSED_DATA_DIR.glob("*/*.json")):
            key = str(f)
            if key in seen or "chunks" not in f.name:
                continue
            seen.add(key)
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                total += len(data) if isinstance(data, list) else 0
            except Exception:
                pass

        return total
    except Exception as exc:
        logger.warning("[health] _count_indexable_chunks error: %s", exc)
        return 0


# Status normalisation: internal labels → acceptance-criteria labels
_VECTOR_STATUS_MAP = {
    "connected": "connected",
    "mock": "disconnected",     # ChromaDB not configured → disconnected
    "failed": "disconnected",   # init failed → disconnected
    "degraded": "degraded",     # connected but returning errors
}

_LLM_STATUS_MAP = {
    True: "connected",
    False: "disconnected",
}


def _chroma_status(vector_engine) -> Dict[str, Any]:
    """Return chroma connectivity status and doc count."""
    if vector_engine is None:
        return {"status": "failed", "doc_count": None}
    if not vector_engine.collection:
        return {"status": "mock", "doc_count": None}
    try:
        count = vector_engine.collection.count()
        return {"status": "connected", "doc_count": count}
    except Exception as exc:
        return {"status": "degraded", "doc_count": None, "error": str(exc)}


@router.get("/api/v1/health")
def health_check() -> Dict[str, Any]:
    # ── Vector / Chroma ──────────────────────────────────────────────────────
    chroma_info = _chroma_status(services.vector_engine)
    raw_vector_status = chroma_info["status"]
    # Normalise to connected / disconnected / degraded
    vector_status = _VECTOR_STATUS_MAP.get(raw_vector_status, raw_vector_status)
    vector_count: Optional[int] = chroma_info.get("doc_count")

    if "error" in chroma_info:
        services.service_errors["vector_db"] = chroma_info["error"]

    # When ChromaDB is disconnected, report the on-disk indexable chunk count
    # so the field is always meaningful (acceptance criteria: show actual doc count)
    indexable_chunks_count: int = _count_indexable_chunks()
    if vector_count is None:
        vector_count = indexable_chunks_count  # best available estimate

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if os.getenv("OLLAMA_API_KEY", "") == "available":
        ollama_status = _probe_ollama(ollama_base_url)
    else:
        ollama_status = "not_configured"

    # ── LLM ──────────────────────────────────────────────────────────────────
    # connected = real API client wired; disconnected = mock/offline mode
    llm_has_client = bool(services.glm_client)
    llm_status = _LLM_STATUS_MAP[llm_has_client]

    # ── Graph DB ──────────────────────────────────────────────────────────────
    gs = services.graph_store
    graph_real = bool(gs and getattr(gs, "driver", None) and getattr(gs, "has_graph_data", False))
    graph_db_status = "connected" if graph_real else "disconnected"
    graph_node_count = getattr(gs, "node_count", 0) if gs else 0

    return {
        # ── Core status fields (acceptance criteria) ──────────────────────
        "vector_db": vector_status,          # connected / disconnected / degraded
        "vector_db_count": vector_count,     # actual indexed count OR on-disk count
        "llm": llm_status,                   # connected / disconnected
        "graph_db": graph_db_status,         # connected / disconnected
        # ── Embedding / Ollama ────────────────────────────────────────────
        "ollama": ollama_status,
        "embedding_mode": (
            "openai" if os.getenv("EMBEDDING_API_KEY") else
            "jina" if os.getenv("JINA_API_KEY") else
            "ollama" if os.getenv("OLLAMA_API_KEY") == "available" else
            "hash_offline"
        ),
        # ── Data stats ────────────────────────────────────────────────────
        "indexable_chunks_on_disk": indexable_chunks_count,
        "graph_node_count": graph_node_count,
        # ── Version info ──────────────────────────────────────────────────
        "app_mode": APP_MODE,
        "app_version": APP_VERSION,
        "knowledge_base_version": DOCUMENT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "embedding_version": EMBEDDING_VERSION,
        "graph_version": GRAPH_VERSION,
        "source_catalog_version": SOURCE_CATALOG_VERSION,
        "source_catalog_path": str(SOURCE_CATALOG_PATH),
        "vector_db_path": str(CHROMA_DB_DIR),
        "processed_data_dir": str(PROCESSED_DATA_DIR),
        # ── Sub-services ──────────────────────────────────────────────────
        "guardrail": "active" if services.guardrail and services.guardrail.has_external_verifier else "conservative",
        "metadata_extractor": "active" if services.metadata_extractor else "unavailable",
        "hallucination_guard": "active" if services.hallucination_guard else "unavailable",
        "relevance_enhancer": "active" if services.relevance_enhancer else "unavailable",
        "enhanced_kb": "active" if services.enhanced_kb else "unavailable",
        "knowledge_linker": "active" if services.knowledge_linker else "unavailable",
        "fact_verifier": "active" if services.fact_verifier else "unavailable",
        "usability_enhancer": "active" if services.usability_enhancer else "unavailable",
        "quality_scorer": "active" if services.quality_scorer else "unavailable",
        # ── Errors dict ───────────────────────────────────────────────────
        "errors": services.service_errors,
    }


# 辖区映射：UI显示名 → API实际值
JURISDICTION_MAP = {
    "CAAC": "CN",  # 中国民用航空局
    "FAA": "US",   # 美国联邦航空管理局
    "EASA": "EU",  # 欧洲航空安全局
}


