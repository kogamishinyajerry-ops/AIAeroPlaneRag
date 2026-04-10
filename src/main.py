from __future__ import annotations

import json
import logging
import os
import random
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.models import QueryRequest, Citation, GraphInsight, QueryResponse
from src.rag.query_expansion import extract_keywords_from_query, expand_query_with_synonyms, expand_query_with_terminology, _tokenize_text
from src.ontology.kg_query import load_knowledge_graph, query_knowledge_graph_nodes, get_node_neighbors, find_semantic_relations, load_terminology, load_abbreviations
from src.rag.llm_generator import _build_context_block, _fallback_answer, _generate_thinking_process, _extract_reasoning_steps, _format_content, generate_answer_with_glm
from src.rag.citation_builder import build_citations
from src.rag.confidence import verify_answer_confidence
from src.core.metrics import PerformanceMetrics










# 导入新的模块化组件
from src.core.config import CORS_ORIGINS
from src.api.routes.query import router as query_router
from src.api.routes.graph import router as graph_router
from src.api.routes.optimizer import router as optimizer_router
from src.api.routes.auth import router as auth_router

try:
    import openai
except ImportError:
    openai = None

from dotenv import load_dotenv

from src.knowledge_base.source_catalog import KnowledgeSourceCatalog
from src.multi_agent.metadata_enhancer_agent import EnhancedMetadataExtractor
from src.multi_agent.knowledge_linker_agent import KnowledgeLinkerAgent
from src.multi_agent.fact_verification_agent import FactVerificationAgent
from src.multi_agent.usability_enhancer_agent import UsabilityEnhancerAgent
from src.multi_agent.knowledge_graph_agent import KnowledgeGraphAgent
from src.multi_agent.enhanced_terminology_agent import EnhancedTerminologyAgent
from src.ontology.graph_store import OntologyGraphStore
from src.scoring.quality_enhancer import QualityScoringEngine
from src.rag.enhanced_answer_generator import EnhancedAnswerGenerator
from src.rag.guardrail import FactCheckingGuardrail
from src.rag.hallucination_guard import HallucinationGuard
from src.rag.hallucination_reducer import HallucinationReducer
from src.rag.safe_answer_builder import SafeAnswerBuilder
from src.rag.enhanced_safe_builder import EnhancedSafeAnswerBuilder
from src.rag.pageindex_engine import PageIndexEngine
from src.rag.relevance_enhancer import QueryRelevanceEnhancer, ReRanker
from src.rag.semantic_chunker import StructuralChunker
from src.rag.vector_engine import VectorStoreEngine

# Enhanced knowledge base
try:
    from src.rag.enhanced_knowledge_base import EnhancedMultiCCARKB
    ENHANCED_KB_AVAILABLE = True
except ImportError:
    ENHANCED_KB_AVAILABLE = False
    EnhancedMultiCCARKB = None
from src.settings import (
    APP_MODE,
    APP_VERSION,
    CHROMA_DB_DIR,
    DOCUMENT_VERSION,
    EMBEDDING_VERSION,
    GRAPH_VERSION,
    PROMPT_VERSION,
    PROCESSED_DATA_DIR,
    SOURCE_CATALOG_PATH,
    SOURCE_CATALOG_VERSION,
    ensure_data_dirs,
    has_real_value,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_related_clauses(query: str, contexts: List[Dict]) -> List[Dict[str, str]]:
    """查找相关条款"""
    if not knowledge_linker:
        return []

    try:
        related = []

        # 从cross_document_links获取关联
        links_file = PROCESSED_DATA_DIR / "knowledge_links" / "cross_document_links.json"
        if links_file.exists():
            with open(links_file, 'r', encoding='utf-8') as f:
                links_data = json.load(f)

            # 查找等效条款
            for link in links_data.get("equivalent_links", []):
                if link.get("clauses"):
                    for clause in link["clauses"]:
                        if any(ctx.get("metadata", {}).get("source", "") in clause for ctx in contexts):
                            related.append({
                                "clause": clause,
                                "type": "等效条款",
                                "document": clause.split(":")[0] if ":" in clause else ""
                            })

            # 限制数量
            if len(related) >= 5:
                related = related[:5]

        return related

    except Exception as e:
        logger.warning(f"Finding related clauses failed: {e}")
        return []


def get_visualization_data(query: str) -> Optional[Dict[str, Any]]:
    """获取可视化数据"""
    try:
        viz_file = PROCESSED_DATA_DIR / "visualizations" / "hierarchy.json"
        if viz_file.exists():
            with open(viz_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Getting visualization data failed: {e}")
    return None


# 知识图谱查询功能
def infer_response_mode(citations: List[Citation]) -> str:
    if not citations:
        return APP_MODE
    modes = {citation.contentMode for citation in citations if citation.contentMode}
    return modes.pop() if len(modes) == 1 else ("mixed" if modes else APP_MODE)


def collect_indexable_chunks() -> List[Dict[str, Any]]:
    chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))
    chunks: List[Dict[str, Any]] = []
    for markdown_file in sorted(PROCESSED_DATA_DIR.glob("*.md")):
        if markdown_file.name.endswith("_analysis_report.md"):
            continue
        chunks.extend(chunker.chunk_markdown(markdown_file.name))

    # Load EASA CS-E JSON chunks
    easa_chunks_path = PROCESSED_DATA_DIR / "easa_cse" / "chunks_full.json"
    if easa_chunks_path.exists():
        import json
        with open(easa_chunks_path, 'r', encoding='utf-8') as f:
            easa_data = json.load(f)
        for item in easa_data:
            chunk = {
                'text': item.get('text', ''),
                'metadata': item.get('metadata', {}),
            }
            chunks.append(chunk)
        logger.info(f"Loaded {len(easa_data)} EASA chunks from JSON")

    return chunks


# Performance metrics storage
@asynccontextmanager
async def lifespan(_: FastAPI):
    from src.api.dependencies.deps import services
    services.initialize()
    if services.vector_engine and services.vector_engine.collection and services.vector_engine.collection.count() == 0:
        logger.info("[STARTUP] ChromaDB is empty. Auto-indexing processed markdown sources...")
        from src.rag.vector_engine import collect_indexable_chunks
        chunks = collect_indexable_chunks()
        if chunks:
            services.vector_engine.index_chunks(chunks)
            logger.info("[STARTUP] Indexed %s chunks into ChromaDB.")

    try:
        from src.background.optimizer import continuous_optimizer
        import asyncio
        asyncio.create_task(
            continuous_optimizer.run_continuous(interval_seconds=30),
            name="continuous_optimizer"
        )
        logger.info("[STARTUP] Continuous optimizer background task started")
    except ImportError:
        pass

    yield


app = FastAPI(
    title="AeroPower-RAG API",
    description="Traceable aviation regulation Q&A service",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 注册模块化路由
app.include_router(query_router)
app.include_router(graph_router)
app.include_router(optimizer_router)
app.include_router(auth_router)

# Mount static files for UI
static_dir = Path(__file__).parent / "static"
ui_dir = Path(__file__).parent.parent / "ui"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount ui directory as /ui
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir), html=True), name="ui")
else:
    # Fallback endpoint if ui directory doesn't exist
    @app.get("/ui")
    async def serve_ui():
        """Serve the main UI from static directory"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "UI file not found"}



from src.api.routes.health import router as health_router
from src.api.routes.sources import router as sources_router
from src.api.routes.index import router as index_router
from src.api.routes.query_pageindex import router as query_pageindex_router
from src.api.routes.query_enhanced import router as query_enhanced_router
from src.api.routes.stats import router as stats_router
from src.api.routes.citation import router as citation_router

app.include_router(health_router)
app.include_router(sources_router)
app.include_router(index_router)
app.include_router(query_pageindex_router)
app.include_router(query_enhanced_router)
app.include_router(stats_router)
app.include_router(citation_router)

