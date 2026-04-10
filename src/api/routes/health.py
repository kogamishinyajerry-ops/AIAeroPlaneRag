import logging
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



@router.get("/api/v1/health")
def health_check() -> Dict[str, Any]:
    vector_status = "connected"
    vector_count = None
    if services.vector_engine is None:
        vector_status = "failed"
    elif not services.vector_engine.collection:
        vector_status = "mock"
    else:
        try:
            vector_count = services.vector_engine.collection.count()
        except Exception as exc:
            vector_status = "degraded"
            services.service_errors["vector_db_count"] = str(exc)

    return {
        "app_mode": APP_MODE,
        "app_version": APP_VERSION,
        "knowledge_base_version": DOCUMENT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "embedding_version": EMBEDDING_VERSION,
        "graph_version": GRAPH_VERSION,
        "source_catalog_version": SOURCE_CATALOG_VERSION,
        "source_catalog_path": str(SOURCE_CATALOG_PATH),
        "vector_db": vector_status,
        "vector_db_count": vector_count,
        "vector_db_path": str(CHROMA_DB_DIR),
        "graph_db": "connected" if services.graph_store and services.graph_store.driver and services.graph_store.has_graph_data else "fallback",
        "graph_node_count": services.graph_store.node_count if services.graph_store else 0,
        "llm": "connected" if services.glm_client else "mock",
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


