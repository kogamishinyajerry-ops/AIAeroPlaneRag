import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from src.api.dependencies.deps import services
from src.rag.vector_engine import collect_indexable_chunks
from src.settings import DOCUMENT_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/v1/index")
def index_documents() -> Dict[str, Any]:
    if services.vector_engine is None:
        raise HTTPException(status_code=503, detail="Vector engine is unavailable")

    chunks = collect_indexable_chunks()
    if not chunks:
        raise HTTPException(status_code=404, detail="No processed markdown documents were found")

    services.vector_engine._recreate_collection()
    services.vector_engine.index_chunks(chunks)
    return {
        "status": "ok",
        "chunks_indexed": len(chunks),
        "knowledge_base_version": DOCUMENT_VERSION,
    }


