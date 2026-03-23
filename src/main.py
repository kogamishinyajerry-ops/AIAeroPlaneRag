from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import openai
except ImportError:
    openai = None

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from dotenv import load_dotenv

from knowledge_base.source_catalog import KnowledgeSourceCatalog
from ontology.graph_store import OntologyGraphStore
from rag.guardrail import FactCheckingGuardrail
from rag.semantic_chunker import StructuralChunker
from rag.vector_engine import VectorStoreEngine
from settings import (
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


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    use_guardrail: bool = True
    include_graph_subgraph: bool = False


class Citation(BaseModel):
    num: int
    source: str
    chapter: str
    section: str
    snippet: str
    highlight: str
    fullText: str | None = None
    documentId: str | None = None
    documentVersion: str | None = None
    contentMode: str | None = None
    sourcePath: str | None = None


class GraphInsight(BaseModel):
    regulation: str | None = None
    component: str | None = None
    parameter: str | None = None
    relationship: str | None = None
    description: str | None = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    guardrail: dict[str, Any]
    citations: list[Citation]
    graphInsights: list[GraphInsight]
    graphSubgraph: dict[str, Any] | None = None
    responseMode: str
    appVersion: str
    knowledgeBaseVersion: str
    promptVersion: str
    embeddingVersion: str
    graphVersion: str
    retrievalCount: int


def extract_keywords_from_query(query: str) -> list[str]:
    stopwords = {
        "什么",
        "哪些",
        "如何",
        "是否",
        "要求",
        "规定",
        "条款",
        "关于",
        "以及",
        "the",
        "what",
        "which",
        "does",
        "requirement",
    }
    keywords = []
    for token in _tokenize_text(query):
        if len(token) < 2:
            continue
        if token.lower() in stopwords:
            continue
        keywords.append(token)
    return list(dict.fromkeys(keywords[:6]))


def _tokenize_text(text: str) -> list[str]:
    tokens = []
    buffer = []

    def flush() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in (text or "").lower():
        if "\u4e00" <= char <= "\u9fff":
            flush()
            tokens.append(char)
        elif char.isalnum() or char == "_":
            buffer.append(char)
        else:
            flush()

    flush()
    return [token for token in tokens if token.strip()]


def _build_context_block(contexts: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            f"[Source: {item['metadata'].get('source', '?')} > {item['metadata'].get('chapter', '?')} > {item['metadata'].get('section', '?')}]\n{item['text']}"
            for item in contexts
        ]
    )


def _fallback_answer(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "当前知识库中没有检索到与问题直接相关的条款证据，暂时无法给出可靠回答。"

    lines = ["根据当前检索证据，可以确认以下信息："]
    for index, context in enumerate(contexts[:3], start=1):
        snippet = (context.get("original_text") or context["text"].split("\n", 1)[-1])[:160].strip()
        lines.append(f"[{index}] {snippet}")
    return "\n".join(lines)


def build_citations(contexts: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    for index, context in enumerate(contexts, start=1):
        metadata = context.get("metadata", {})
        full_text = (context.get("original_text") or context.get("text", "")).strip()
        if not full_text:
            full_text = context.get("text", "")
        snippet = full_text[:200] + "..." if len(full_text) > 200 else full_text
        highlight = full_text.splitlines()[0][:100] if full_text else ""

        citations.append(
            Citation(
                num=index,
                source=metadata.get("source", "Unknown source"),
                chapter=metadata.get("chapter", "未知章节"),
                section=metadata.get("section", "未知条款"),
                snippet=snippet,
                highlight=highlight,
                fullText=full_text,
                documentId=metadata.get("document_id"),
                documentVersion=metadata.get("document_version", DOCUMENT_VERSION),
                contentMode=metadata.get("content_mode", "unknown"),
                sourcePath=metadata.get("source_path"),
            )
        )
    return citations


def infer_response_mode(citations: list[Citation]) -> str:
    if not citations:
        return APP_MODE
    modes = {citation.contentMode for citation in citations if citation.contentMode}
    return modes.pop() if len(modes) == 1 else ("mixed" if modes else APP_MODE)


def collect_indexable_chunks() -> list[dict[str, Any]]:
    chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))
    chunks: list[dict[str, Any]] = []
    for markdown_file in sorted(PROCESSED_DATA_DIR.glob("*.md")):
        if markdown_file.name.endswith("_analysis_report.md"):
            continue
        chunks.extend(chunker.chunk_markdown(markdown_file.name))
    return chunks


glm_client = None
vector_engine = None
graph_store = None
guardrail = None
source_catalog = None
service_errors: dict[str, str] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if vector_engine and vector_engine.collection and vector_engine.collection.count() == 0:
        logger.info("[STARTUP] ChromaDB is empty. Auto-indexing processed markdown sources...")
        chunks = collect_indexable_chunks()
        if chunks:
            vector_engine.index_chunks(chunks)
            logger.info("[STARTUP] Indexed %s chunks into ChromaDB.", len(chunks))
    yield


app = FastAPI(
    title="AeroPower-RAG API",
    description="Traceable aviation regulation Q&A service",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def initialize_services() -> None:
    global glm_client, vector_engine, graph_store, guardrail, source_catalog

    ensure_data_dirs()
    service_errors.clear()

    try:
        vector_engine = VectorStoreEngine(db_dir=str(CHROMA_DB_DIR))
    except Exception as exc:
        vector_engine = None
        service_errors["vector_db"] = str(exc)
        logger.exception("Vector engine initialization failed.")

    try:
        graph_store = OntologyGraphStore()
    except Exception as exc:
        graph_store = None
        service_errors["graph_db"] = str(exc)
        logger.exception("Graph store initialization failed.")

    try:
        guardrail = FactCheckingGuardrail()
    except Exception as exc:
        guardrail = None
        service_errors["guardrail"] = str(exc)
        logger.exception("Guardrail initialization failed.")

    try:
        source_catalog = KnowledgeSourceCatalog.load()
    except Exception as exc:
        source_catalog = KnowledgeSourceCatalog()
        service_errors["source_catalog"] = str(exc)
        logger.exception("Source catalog initialization failed.")

    api_key = os.getenv("ZHIPU_API_KEY")
    if openai and has_real_value(api_key):
        glm_client = openai.OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
        logger.info("GLM API client initialized for answer generation.")


initialize_services()


def generate_answer_with_glm(query: str, contexts: list[dict[str, Any]], graph_insights: list[dict[str, Any]]) -> str:
    if not glm_client:
        return _fallback_answer(contexts)

    graph_text = ""
    if graph_insights:
        graph_text = "\n\nGraph evidence:\n" + "\n".join(
            [
                f"- {item.get('regulation', '?')} --[{item.get('relationship', '?')}]--> {item.get('component', '?')}"
                for item in graph_insights[:6]
            ]
        )

    system_prompt = (
        "You are a strict aviation regulation assistant. "
        "Answer in Chinese using only the provided contexts. "
        "Cite key claims with [1], [2] style references. "
        "If evidence is insufficient, say so explicitly."
    )
    user_prompt = (
        f"User question:\n{query}\n\n"
        f"Retrieved contexts:\n{_build_context_block(contexts)}"
        f"{graph_text}\n\n"
        "Please provide a concise answer in Chinese."
    )

    try:
        response = glm_client.chat.completions.create(
            model="glm-4-flash",
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("GLM generation failed: %s", exc)
        return _fallback_answer(contexts)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "AeroPower-RAG", "version": APP_VERSION, "status": "operational"}


@app.get("/api/v1/health")
def health_check() -> dict[str, Any]:
    vector_status = "connected"
    vector_count = None
    if vector_engine is None:
        vector_status = "failed"
    elif not vector_engine.collection:
        vector_status = "mock"
    else:
        try:
            vector_count = vector_engine.collection.count()
        except Exception as exc:
            vector_status = "degraded"
            service_errors["vector_db_count"] = str(exc)

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
        "graph_db": "connected" if graph_store and graph_store.driver and graph_store.has_graph_data else "fallback",
        "graph_node_count": graph_store.node_count if graph_store else 0,
        "llm": "connected" if glm_client else "mock",
        "guardrail": "active" if guardrail and guardrail.has_external_verifier else "conservative",
        "processed_data_dir": str(PROCESSED_DATA_DIR),
        "errors": service_errors,
    }


@app.get("/api/v1/sources")
def get_sources(layer: str | None = None, jurisdiction: str | None = None) -> dict[str, Any]:
    if not source_catalog:
        return {"version": SOURCE_CATALOG_VERSION, "total": 0, "groups": [], "sources": []}

    filtered = source_catalog.filter(layer=layer, jurisdiction=jurisdiction)
    return {
        "version": source_catalog.version,
        "total": len(filtered),
        "groups": source_catalog.grouped(),
        "sources": [item.model_dump() for item in filtered],
    }


@app.get("/api/v1/graph/subgraph")
def get_graph_subgraph(
    query: str = "",
    node_id: str | None = None,
    max_nodes: int = 18,
    include_parameters: bool = False,
) -> dict[str, Any]:
    if not graph_store:
        return {"mode": "unavailable", "nodes": [], "edges": [], "summary": "Graph store is unavailable."}

    return graph_store.get_subgraph(
        query=query,
        node_id=node_id,
        limit=max_nodes,
        include_parameters=include_parameters,
    )


@app.get("/api/v1/graph/nodes")
def get_graph_nodes() -> dict[str, Any]:
    if not graph_store:
        return {"nodes": [], "edges": [], "mode": "unavailable"}

    snapshot = graph_store.get_graph_snapshot()
    return {
        "nodes": snapshot.get("nodes") or [],
        "edges": snapshot.get("edges") or [],
        "mode": snapshot.get("mode", "fallback"),
        "summary": snapshot.get("summary"),
        "stats": snapshot.get("stats", {}),
    }


@app.post("/api/v1/query", response_model=QueryResponse)
def execute_rag_query(req: QueryRequest) -> QueryResponse:
    logger.info("[QUERY] %s", req.query)

    if vector_engine is None:
        raise HTTPException(status_code=503, detail="Vector engine is unavailable")

    retrieved_contexts = vector_engine.search(req.query, top_k=req.top_k)
    logger.info("[VECTOR] Retrieved %s chunks", len(retrieved_contexts))

    graph_insights_raw: list[dict[str, Any]] = []
    if graph_store:
        for keyword in extract_keywords_from_query(req.query):
            graph_insights_raw.extend(graph_store.query_graph(keyword))

    seen = set()
    graph_insights_unique = []
    for item in graph_insights_raw:
        key = (item.get("regulation", ""), item.get("component", ""), item.get("relationship", ""))
        if key in seen:
            continue
        seen.add(key)
        graph_insights_unique.append(item)

    if not retrieved_contexts and not graph_insights_unique:
        empty_graph = graph_store.get_subgraph(query=req.query, limit=12) if graph_store and req.include_graph_subgraph else None
        return QueryResponse(
            query=req.query,
            answer="当前知识库中没有找到与问题直接相关的条款。请尝试缩小范围，或补充更具体的部件、条款号与设计场景。",
            guardrail={
                "status": "NOT_FOUND",
                "reasoning": "没有检索到可支撑回答的条款证据，因此系统返回保守拒答。",
                "safe_answer": "当前知识库中没有找到与问题直接相关的条款。",
            },
            citations=[],
            graphInsights=[],
            graphSubgraph=empty_graph,
            responseMode=APP_MODE,
            appVersion=APP_VERSION,
            knowledgeBaseVersion=DOCUMENT_VERSION,
            promptVersion=PROMPT_VERSION,
            embeddingVersion=EMBEDDING_VERSION,
            graphVersion=GRAPH_VERSION,
            retrievalCount=0,
        )

    draft_answer = generate_answer_with_glm(req.query, retrieved_contexts, graph_insights_unique)
    guardrail_result = {
        "status": "SKIPPED",
        "reasoning": "Guardrail verification was skipped by the caller.",
        "safe_answer": draft_answer,
    }
    final_answer = draft_answer

    if req.use_guardrail:
        if not guardrail:
            guardrail_result = {
                "status": "UNAVAILABLE",
                "reasoning": "Guardrail verifier is unavailable, so the system returned a conservative evidence summary.",
                "safe_answer": _fallback_answer(retrieved_contexts),
            }
        else:
            guardrail_result = guardrail.verify_response(req.query, draft_answer, retrieved_contexts)
        final_answer = guardrail_result.get("safe_answer", draft_answer)

    citations = build_citations(retrieved_contexts)
    graph_subgraph = graph_store.get_subgraph(query=req.query, limit=16) if graph_store and req.include_graph_subgraph else None

    return QueryResponse(
        query=req.query,
        answer=final_answer,
        guardrail=guardrail_result,
        citations=citations,
        graphInsights=[
            GraphInsight(
                regulation=item.get("regulation", ""),
                component=item.get("component", ""),
                parameter=item.get("parameter", ""),
                relationship=item.get("relationship", "CONSTRAINS"),
                description=item.get("description", ""),
            )
            for item in graph_insights_unique[:8]
        ],
        graphSubgraph=graph_subgraph,
        responseMode=infer_response_mode(citations),
        appVersion=APP_VERSION,
        knowledgeBaseVersion=DOCUMENT_VERSION,
        promptVersion=PROMPT_VERSION,
        embeddingVersion=EMBEDDING_VERSION,
        graphVersion=GRAPH_VERSION,
        retrievalCount=len(retrieved_contexts),
    )


@app.post("/api/v1/index")
def index_documents() -> dict[str, Any]:
    if vector_engine is None:
        raise HTTPException(status_code=503, detail="Vector engine is unavailable")

    chunks = collect_indexable_chunks()
    if not chunks:
        raise HTTPException(status_code=404, detail="No processed markdown documents were found")

    vector_engine.index_chunks(chunks)
    return {
        "status": "ok",
        "chunks_indexed": len(chunks),
        "knowledge_base_version": DOCUMENT_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
