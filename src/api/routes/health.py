import logging
import os
from typing import Any, Dict
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
    vector_status = chroma_info["status"]
    vector_count = chroma_info.get("doc_count")
    if "error" in chroma_info:
        services.service_errors["vector_db_count"] = chroma_info["error"]

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # If OLLAMA_API_KEY is not "available" we know Ollama isn't configured, skip probe
    if os.getenv("OLLAMA_API_KEY", "") == "available":
        ollama_status = _probe_ollama(ollama_base_url)
    else:
        ollama_status = "not_configured"

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_status = "connected" if services.glm_client else "mock"

    return {
        # ── Four core status items (acceptance criteria) ──────────────────
        "vector": vector_status,
        "llm": llm_status,
        "ollama": ollama_status,
        "chroma": chroma_info["status"],
        # ── Extended fields ───────────────────────────────────────────────
        "app_mode": APP_MODE,
        "app_version": APP_VERSION,
        "knowledge_base_version": DOCUMENT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "embedding_version": EMBEDDING_VERSION,
        "graph_version": GRAPH_VERSION,
        "source_catalog_version": SOURCE_CATALOG_VERSION,
        "source_catalog_path": str(SOURCE_CATALOG_PATH),
        # Legacy aliases kept for backward-compat
        "vector_db": vector_status,
        "vector_db_count": vector_count,
        "vector_db_path": str(CHROMA_DB_DIR),
        "graph_db": "connected" if services.graph_store and services.graph_store.driver and services.graph_store.has_graph_data else "fallback",
        "graph_node_count": services.graph_store.node_count if services.graph_store else 0,
        "guardrail": "active" if services.guardrail and services.guardrail.has_external_verifier else "conservative",
        "metadata_extractor": "active" if services.metadata_extractor else "unavailable",
        "hallucination_guard": "active" if services.hallucination_guard else "unavailable",
        "relevance_enhancer": "active" if services.relevance_enhancer else "unavailable",
        "enhanced_kb": "active" if services.enhanced_kb else "unavailable",
        "knowledge_linker": "active" if services.knowledge_linker else "unavailable",
        "fact_verifier": "active" if services.fact_verifier else "unavailable",
        "usability_enhancer": "active" if services.usability_enhancer else "unavailable",
        "quality_scorer": "active" if services.quality_scorer else "unavailable",
        "processed_data_dir": str(PROCESSED_DATA_DIR),
        "errors": services.service_errors,
    }


# 辖区映射：UI显示名 → API实际值
JURISDICTION_MAP = {
    "CAAC": "CN",  # 中国民用航空局
    "FAA": "US",   # 美国联邦航空管理局
    "EASA": "EU",  # 欧洲航空安全局
}


