import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter
from src.api.dependencies.deps import services
from src.settings import SOURCE_CATALOG_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

JURISDICTION_MAP = {"CAAC": "CN", "FAA": "US", "EASA": "EU"}

@router.get("/api/v1/sources")
def get_sources(layer: Optional[str] = None, jurisdiction: Optional[str] = None) -> Dict[str, Any]:
    if not services.source_catalog:
        return {"version": SOURCE_CATALOG_VERSION, "total": 0, "groups": [], "sources": []}

    # 转换辖区名（如果是UI发送的CAAC/FAA/EASA，转为CN/US/EU）
    api_jurisdiction = JURISDICTION_MAP.get(jurisdiction, jurisdiction)
    filtered = services.source_catalog.filter(layer=layer, jurisdiction=api_jurisdiction)
    return {
        "version": services.source_catalog.version,
        "total": len(filtered),
        "groups": services.source_catalog.grouped(),
        "sources": [item.model_dump() for item in filtered],
    }
