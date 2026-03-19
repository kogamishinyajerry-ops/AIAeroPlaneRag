import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import openai
except ImportError:
    openai = None

from dotenv import load_dotenv

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
    ensure_data_dirs,
    has_real_value,
)


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if vector_engine and vector_engine.collection:
        count = vector_engine.collection.count()
        if count == 0:
            logger.info("[STARTUP] ChromaDB is empty. Auto-indexing CCAR-33...")
            chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))
            chunks = chunker.chunk_markdown("CCAR-33.md")
            if chunks:
                vector_engine.index_chunks(chunks)
                logger.info("[STARTUP] Indexed %s chunks into ChromaDB.", len(chunks))
        else:
            logger.info("[STARTUP] ChromaDB already has %s chunks. Skipping indexing.", count)
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


ensure_data_dirs()
service_errors: Dict[str, str] = {}

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


glm_client = None
api_key = os.getenv("ZHIPU_API_KEY")
if openai and has_real_value(api_key):
    glm_client = openai.OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
    logger.info("GLM API client initialized for answer generation.")


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    use_guardrail: bool = True


class Citation(BaseModel):
    num: int
    source: str
    chapter: str
    section: str
    snippet: str
    highlight: str
    documentId: Optional[str] = None
    documentVersion: Optional[str] = None
    contentMode: Optional[str] = None
    sourcePath: Optional[str] = None


class GraphInsight(BaseModel):
    regulation: Optional[str] = None
    component: Optional[str] = None
    parameter: Optional[str] = None
    relationship: Optional[str] = None
    description: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    guardrail: Dict
    citations: List[Citation]
    graphInsights: List[GraphInsight]
    responseMode: str
    appVersion: str
    knowledgeBaseVersion: str
    promptVersion: str
    embeddingVersion: str
    graphVersion: str
    retrievalCount: int


def extract_keywords_from_query(query: str) -> List[str]:
    keywords = []
    components = [
        "压气机",
        "涡轮",
        "燃烧室",
        "轴",
        "叶片",
        "轴承",
        "涡轮盘",
        "压气机盘",
        "密封",
        "润滑",
        "风扇",
        "机匣",
        "compressor",
        "turbine",
        "combustor",
    ]
    tests = ["超转试验", "吞鸟试验", "吞冰试验", "持久试验", "超温试验", "包容性试验"]
    params = ["喘振裕度", "燃烧效率", "温度", "转速", "推力", "排放"]

    for term_list in [components, tests, params]:
        for term in term_list:
            if term in query or term.lower() in query.lower():
                keywords.append(term)
    return keywords


def generate_answer_with_glm(query: str, contexts: List[Dict], graph_insights: List[Dict]) -> str:
    if not glm_client:
        return _fallback_answer(contexts)

    context_text = "\n\n".join(
        [
            f"[来源: {c['metadata'].get('source', '?')} > {c['metadata'].get('chapter', '?')} > {c['metadata'].get('section', '?')}]\n{c['text']}"
            for c in contexts
        ]
    )

    graph_text = ""
    if graph_insights:
        graph_text = "\n\n图谱关联信息:\n" + "\n".join(
            [
                f"- {g.get('regulation', '?')} --[{g.get('relationship', '?')}]--> {g.get('component', '?')} (参数: {g.get('parameter', 'N/A')})"
                for g in graph_insights
            ]
        )

    system_prompt = """你是一名严谨的民航适航规范专家 AI 助理。你的回答必须基于且仅基于提供的检索上下文和图谱关联内容。

规则：
1. 必须使用 [1]、[2] 等角标标注关键结论来源。
2. 不得补充上下文中没有明确支持的结论。
3. 如果上下文不足，请明确说明证据不足。
4. 回答使用中文，语气专业、简洁、可追溯。"""

    user_prompt = f"""### 用户问题
{query}

### 检索上下文
{context_text}
{graph_text}

请严格基于以上内容回答，并在关键结论后标注来源角标。"""

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


def _fallback_answer(contexts: List[Dict]) -> str:
    if not contexts:
        return "当前知识库中没有检索到直接相关的条款，无法给出可靠回答。"

    lines = ["根据当前检索到的条款，可以确认以下信息："]
    for index, ctx in enumerate(contexts[:3], start=1):
        snippet = ctx["text"].split("\n", 1)[-1][:140].strip()
        lines.append(f"[{index}] {snippet}")
    return "\n".join(lines)


def build_citations(contexts: List[Dict]) -> List[Citation]:
    citations: List[Citation] = []
    for index, ctx in enumerate(contexts, start=1):
        text = ctx["text"]
        sentences = [s.strip() for s in text.replace("\n", " ").split("。") if len(s.strip()) > 10]
        highlight = f"{sentences[0]}。" if sentences else text[:80]
        metadata = ctx.get("metadata", {})
        citations.append(
            Citation(
                num=index,
                source=metadata.get("source", "CCAR-33.md"),
                chapter=metadata.get("chapter", "未知章节"),
                section=metadata.get("section", "未知条款"),
                snippet=text[:300],
                highlight=highlight[:100],
                documentId=metadata.get("document_id"),
                documentVersion=metadata.get("document_version", DOCUMENT_VERSION),
                contentMode=metadata.get("content_mode", "unknown"),
                sourcePath=metadata.get("source_path"),
            )
        )
    return citations


def infer_response_mode(citations: List[Citation]) -> str:
    if not citations:
        return APP_MODE
    modes = {citation.contentMode for citation in citations if citation.contentMode}
    if len(modes) == 1:
        return modes.pop() or APP_MODE
    if not modes:
        return APP_MODE
    return "mixed"


@app.get("/")
def root():
    return {"service": "AeroPower-RAG", "version": APP_VERSION, "status": "operational"}


@app.get("/api/v1/health")
def health_check():
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


@app.post("/api/v1/query", response_model=QueryResponse)
def execute_rag_query(req: QueryRequest):
    logger.info("[QUERY] %s", req.query)

    if vector_engine is None:
        raise HTTPException(status_code=503, detail="Vector engine is unavailable")

    retrieved_contexts = vector_engine.search(req.query, top_k=req.top_k)
    logger.info("[VECTOR] Retrieved %s chunks", len(retrieved_contexts))

    keywords = extract_keywords_from_query(req.query)
    graph_insights_raw: List[Dict] = []
    for keyword in keywords:
        graph_insights_raw.extend(graph_store.query_graph(keyword) if graph_store else [])

    seen = set()
    graph_insights_unique = []
    for item in graph_insights_raw:
        key = f"{item.get('regulation', '')}-{item.get('component', '')}-{item.get('relationship', '')}"
        if key not in seen:
            seen.add(key)
            graph_insights_unique.append(item)
    logger.info("[GRAPH] Found %s graph insights for keywords: %s", len(graph_insights_unique), keywords)

    if not retrieved_contexts and not graph_insights_unique:
        return QueryResponse(
            query=req.query,
            answer="当前知识库中未找到与问题直接相关的条款。请尝试调整关键词，或先确认文档是否已完成真实入库。",
            guardrail={
                "status": "NOT_FOUND",
                "reasoning": "未检索到可支撑回答的上下文，因此系统返回拒答。",
                "safe_answer": "当前知识库中未找到与问题直接相关的条款。",
            },
            citations=[],
            graphInsights=[],
            responseMode=APP_MODE,
            appVersion=APP_VERSION,
            knowledgeBaseVersion=DOCUMENT_VERSION,
            promptVersion=PROMPT_VERSION,
            embeddingVersion=EMBEDDING_VERSION,
            graphVersion=GRAPH_VERSION,
            retrievalCount=0,
        )

    draft_answer = generate_answer_with_glm(req.query, retrieved_contexts, graph_insights_unique)
    logger.info("[GENERATE] Draft answer length: %s", len(draft_answer))

    guardrail_result = {
        "status": "SKIPPED",
        "reasoning": "用户关闭了 Guardrail 校验。",
        "safe_answer": draft_answer,
    }
    final_answer = draft_answer

    if req.use_guardrail:
        if not guardrail:
            guardrail_result = {
                "status": "UNAVAILABLE",
                "reasoning": "Guardrail 服务不可用，系统返回保守草稿答案。",
                "safe_answer": _fallback_answer(retrieved_contexts),
            }
        else:
            guardrail_result = guardrail.verify_response(req.query, draft_answer, retrieved_contexts)
        final_answer = guardrail_result.get("safe_answer", draft_answer)
        logger.info("[GUARDRAIL] Status: %s", guardrail_result["status"])

    citations = build_citations(retrieved_contexts)
    graph_insights = [
        GraphInsight(
            regulation=item.get("regulation", ""),
            component=item.get("component", ""),
            parameter=item.get("parameter", ""),
            relationship=item.get("relationship", "CONSTRAINS"),
            description=item.get("description", ""),
        )
        for item in graph_insights_unique[:10]
    ]

    return QueryResponse(
        query=req.query,
        answer=final_answer,
        guardrail=guardrail_result,
        citations=citations,
        graphInsights=graph_insights,
        responseMode=infer_response_mode(citations),
        appVersion=APP_VERSION,
        knowledgeBaseVersion=DOCUMENT_VERSION,
        promptVersion=PROMPT_VERSION,
        embeddingVersion=EMBEDDING_VERSION,
        graphVersion=GRAPH_VERSION,
        retrievalCount=len(retrieved_contexts),
    )


@app.get("/api/v1/graph/nodes")
def get_graph_nodes():
    if not graph_store:
        return {"nodes": [], "edges": [], "mode": "unavailable"}

    if not graph_store.driver or not graph_store.has_graph_data:
        snapshot = graph_store.get_graph_snapshot()
        return {"nodes": snapshot["nodes"] or [], "edges": snapshot["edges"] or [], "mode": snapshot["mode"]}

    nodes = []
    edges = []
    try:
        with graph_store.driver.session() as session:
            node_result = session.run(
                """
                MATCH (n)
                RETURN n.id AS id, n.name AS name, n.type AS type, n.description AS description
                LIMIT 100
                """
            )
            for record in node_result:
                nodes.append(
                    {
                        "id": record["id"] or record["name"],
                        "label": record["name"] or record["id"],
                        "type": (record["type"] or "Unknown").lower(),
                        "description": record["description"] or "",
                    }
                )

            edge_result = session.run(
                """
                MATCH (a)-[r]->(b)
                RETURN a.id AS source_id, a.name AS source_name,
                       type(r) AS rel_type, r.description AS rel_desc,
                       b.id AS target_id, b.name AS target_name
                LIMIT 200
                """
            )
            for record in edge_result:
                edges.append(
                    {
                        "source": record["source_id"] or record["source_name"],
                        "target": record["target_id"] or record["target_name"],
                        "type": record["rel_type"],
                        "description": record["rel_desc"] or "",
                    }
                )
    except Exception as exc:
        logger.error("Graph query error: %s", exc)

    return {"nodes": nodes, "edges": edges}


@app.post("/api/v1/index")
def index_documents():
    if vector_engine is None:
        raise HTTPException(status_code=503, detail="Vector engine is unavailable")

    chunker = StructuralChunker(processed_dir=str(PROCESSED_DATA_DIR))
    chunks = chunker.chunk_markdown("CCAR-33.md")
    if not chunks:
        raise HTTPException(status_code=404, detail="CCAR-33.md not found")

    vector_engine.index_chunks(chunks)
    return {"status": "ok", "chunks_indexed": len(chunks), "knowledge_base_version": DOCUMENT_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
