import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from src.api.models import QueryRequest, QueryResponse
from src.api.dependencies.deps import services
from src.settings import APP_VERSION, DOCUMENT_VERSION, PROMPT_VERSION, EMBEDDING_VERSION, GRAPH_VERSION, PROCESSED_DATA_DIR
from src.api.models import Citation
from src.rag.llm_generator import generate_answer_with_glm

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/v1/query/pageindex", response_model=QueryResponse)
def execute_pageindex_query(req: QueryRequest) -> QueryResponse:
    """
    使用 PageIndex 树结构进行推理式检索

    相比向量检索的优势：
    - 基于文档层级结构（章节-条款）推理
    - 检索路径可追溯
    - 无需向量切分，保留完整上下文

    新增功能：
    - 元数据增强
    - 相关性重排序
    - 幻觉防护
    """
    logger.info("[PAGEINDEX QUERY] %s", req.query)

    if services.pageindex_engine is None:
        raise HTTPException(
            status_code=503,
            detail="PageIndex engine is unavailable. Make sure CCAR-33-R2_structure.json exists."
        )

    # 使用 PageIndex 进行树结构搜索
    retrieved_contexts = services.pageindex_engine.search_by_keywords(req.query, top_k=req.top_k)
    logger.info("[PAGEINDEX] Retrieved %s nodes", len(retrieved_contexts))

    # 应用元数据增强
    if services.metadata_extractor:
        retrieved_contexts = services.metadata_extractor.enhance_batch_results(retrieved_contexts)
        logger.info("[PAGEINDEX METADATA] Enhanced metadata for %s contexts", len(retrieved_contexts))

    # 应用相关性增强和重排序
    if services.reranker:
        retrieved_contexts = services.reranker.rerank(req.query, retrieved_contexts, top_k=req.top_k)
        logger.info("[PAGEINDEX RERANK] Re-ranked %s contexts", len(retrieved_contexts))

    if not retrieved_contexts:
        return QueryResponse(
            query=req.query,
            answer="当前知识库中没有找到与问题直接相关的条款。请尝试缩小范围，或补充更具体的条款号或关键词。",
            guardrail={
                "status": "NOT_FOUND",
                "reasoning": "PageIndex 搜索未找到相关节点",
                "safe_answer": "当前知识库中没有找到与问题直接相关的条款。",
            },
            citations=[],
            graphInsights=[],
            graphSubgraph=None,
            responseMode="pageindex",
            appVersion=APP_VERSION,
            knowledgeBaseVersion=DOCUMENT_VERSION,
            promptVersion=PROMPT_VERSION,
            embeddingVersion=EMBEDDING_VERSION,
            graphVersion=GRAPH_VERSION,
            retrievalCount=0,
        )

    # 使用 LLM 生成答案
    draft_answer = generate_answer_with_glm(req.query, retrieved_contexts, [])

    # 应用幻觉防护检查
    hallucination_report = None
    if services.hallucination_guard:
        hallucination_report = services.hallucination_guard.generate_hallucination_report(
            draft_answer, retrieved_contexts
        )
        if hallucination_report.has_hallucination and hallucination_report.hallucination_score > 0.5:
            logger.warning("[PAGEINDEX HALLUCINATION] Detected potential hallucination (score: %.2f)",
                          hallucination_report.hallucination_score)

    guardrail_result = {
        "status": "SKIPPED",
        "reasoning": "PageIndex 搜索已返回结构化结果，跳过 services.guardrail 验证",
        "safe_answer": draft_answer,
    }

    # 将幻觉报告添加到 guardrail_result
    if hallucination_report:
        guardrail_result["hallucination_score"] = hallucination_report.hallucination_score
        guardrail_result["has_hallucination"] = hallucination_report.has_hallucination
        guardrail_result["hallucination_recommendations"] = hallucination_report.recommendations

    # 构建 citations（PageIndex 格式）
    citations = []
    for index, context in enumerate(retrieved_contexts, start=1):
        metadata = context.get("metadata", {})
        full_text = context.get("original_text") or context.get("text", "")
        snippet = full_text[:200] + "..." if len(full_text) > 200 else full_text

        # 从 PageIndex 元数据构建 citation
        citations.append(
            Citation(
                num=index,
                source=metadata.get("source", "CCAR-33-R2"),
                chapter=metadata.get("title", "").split()[0] if " " in metadata.get("title", "") else "未知章节",
                section=metadata.get("title", "未知条款"),
                snippet=snippet,
                highlight=metadata.get("title", ""),
                fullText=full_text,
                documentId="CCAR-33-R2",
                documentVersion=DOCUMENT_VERSION,
                contentMode="pageindex_structure",
                sourcePath=str(PROCESSED_DATA_DIR / "CCAR-33-R2_structure.json"),
            )
        )

    return QueryResponse(
        query=req.query,
        answer=draft_answer,
        guardrail=guardrail_result,
        citations=citations,
        graphInsights=[],
        graphSubgraph=None,
        responseMode="pageindex",
        appVersion=APP_VERSION,
        knowledgeBaseVersion=DOCUMENT_VERSION,
        promptVersion=PROMPT_VERSION,
        embeddingVersion=EMBEDDING_VERSION,
        graphVersion=GRAPH_VERSION,
        retrievalCount=len(retrieved_contexts),
    )



@router.get("/api/v1/pageindex/nodes")
def get_pageindex_nodes() -> dict[str, Any]:
    """获取 PageIndex 树结构中的所有节点"""
    if services.pageindex_engine is None:
        return {"nodes": [], "total": 0, "status": "unavailable"}

    all_sections = services.pageindex_engine.get_all_sections()
    return {
        "total": len(all_sections),
        "nodes": all_sections,
        "status": "ok"
    }



