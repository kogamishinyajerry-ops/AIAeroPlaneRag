import logging
from typing import Any, Dict
from fastapi import APIRouter
from src.api.dependencies.deps import services
from src.core.metrics import metrics_collector
from src.settings import APP_VERSION

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/v1/enhanced/stats")
def get_enhanced_kb_stats() -> dict[str, Any]:
    """获取增强知识库统计信息和性能指标"""
    # Get KB stats
    kb_stats = {}
    if services.enhanced_kb is not None:
        stats = services.enhanced_kb.get_document_stats()
        total_sections = sum(s.get("total_sections", 0) for s in stats.values())
        total_nodes = sum(s.get("total_nodes", 0) for s in stats.values())
        kb_stats = {
            "status": "ok",
            "documents": len(stats),
            "total_sections": total_sections,
            "total_nodes": total_nodes,
            "sections_with_content": len(services.enhanced_kb.section_content_map),
            "details": stats
        }
    else:
        kb_stats = {"status": "unavailable", "error": "Enhanced KB not initialized"}

    # Get performance metrics
    perf_stats = metrics_collector.get_stats()

    return {
        **kb_stats,
        "performance": perf_stats
    }



@router.get("/api/v1/dashboard/stats")
def get_dashboard_stats() -> dict[str, Any]:
    """
    获取仪表盘专用性能统计

    返回:
    - 查询响应时间 P50/P95/P99
    - 置信度分布（高/中/低占比）
    - 来源覆盖统计（CAAC/FAA/EASA占比）
    - Top查询词频
    """
    stats = metrics_collector.get_stats()

    # Override source_coverage with actual ChromaDB indexed chunk counts
    if services.vector_engine is not None and services.vector_engine.collection is not None:
        try:
            all_data = services.vector_engine.collection.get(limit=1000)
            from collections import Counter
            authority_counts = Counter()
            for meta in all_data.get("metadatas", []):
                auth = meta.get("authority", "OTHER")
                authority_counts[auth] += 1
            stats["source_coverage"] = {
                "CAAC": authority_counts.get("CAAC", 0),
                "FAA": authority_counts.get("FAA", 0),
                "EASA": authority_counts.get("EASA", 0),
                "OTHER": authority_counts.get("OTHER", 0),
            }
        except Exception:
            pass  # Keep query-time stats if ChromaDB read fails

    return {
        "status": "ok",
        **stats,
        "app_version": APP_VERSION,
        "timestamp": __import__("time").time()
    }



