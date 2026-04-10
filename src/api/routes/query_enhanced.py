import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from src.api.models import QueryRequest, QueryResponse
from src.api.dependencies.deps import services
from src.settings import APP_VERSION, DOCUMENT_VERSION, PROMPT_VERSION, EMBEDDING_VERSION, GRAPH_VERSION
from src.api.models import Citation

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/api/v1/query/enhanced")
def execute_enhanced_query(req: QueryRequest) -> QueryResponse:
    """
    使用增强型多规章知识库进行查询

    特性:
    - 专业术语标准化和同义词扩展
    - 跨规章关联推荐
    - 条款全文内容
    - 改进的相关性评分
    - 元数据增强
    - 相关性重排序
    - 幻觉防护
    """
    logger.info("[ENHANCED QUERY] %s", req.query)

    if services.enhanced_kb is None:
        raise HTTPException(
            status_code=503,
            detail="Enhanced knowledge base is unavailable"
        )

    # 使用增强知识库搜索
    search_results = services.enhanced_kb.search(
        req.query,
        top_k=req.top_k,
        include_references=True
    )

    # 应用相关性增强和重排序
    if services.reranker and search_results:
        # 将搜索结果转换为上下文格式
        result_contexts = []
        for result in search_results:
            result_contexts.append({
                "text": result.summary or result.text or result.title,
                "metadata": {
                    "source": result.metadata.get("source", "Unknown"),
                    "title": result.title,
                    "score": result.relevance_score
                }
            })
        # 重排序
        reranked = services.reranker.rerank(req.query, result_contexts, top_k=req.top_k)
        # 根据重排序结果调整search_results的顺序
        reranked_sources = [r["metadata"]["source"] for r in reranked]
        reordered_results = []
        for source in reranked_sources:
            for result in search_results:
                if result.metadata.get("source") == source and result not in reordered_results:
                    reordered_results.append(result)
                    break
        search_results = reordered_results
        logger.info("[ENHANCED RERANK] Re-ranked %s results", len(search_results))

    if not search_results:
        return QueryResponse(
            query=req.query,
            answer="当前知识库中没有找到与问题直接相关的条款。请尝试调整查询关键词或使用更具体的条款号。",
            guardrail={
                "status": "NOT_FOUND",
                "reasoning": "增强知识库搜索未找到相关结果",
                "safe_answer": "当前知识库中没有找到与问题直接相关的条款。",
            },
            citations=[],
            graphInsights=[],
            graphSubgraph=None,
            responseMode="enhanced_multi_ccar",
            appVersion=APP_VERSION,
            knowledgeBaseVersion=DOCUMENT_VERSION,
            promptVersion=PROMPT_VERSION,
            embeddingVersion=EMBEDDING_VERSION,
            graphVersion=GRAPH_VERSION,
            retrievalCount=0,
        )

    # 构建上下文用于 LLM 生成答案
    contexts = []
    for result in search_results:
        contexts.append({
            "text": result.summary or result.text or result.title,
            "original_text": result.text,
            "metadata": {
                "source": result.metadata.get("source", "Unknown"),
                "source_link": result.metadata.get("source_link", ""),
                "section_number": result.metadata.get("section_number", ""),
                "chapter": "",
                "section": result.title,
                "title": result.title,
                "page": result.metadata.get("page", 0),
                "score": result.relevance_score
            }
        })

    # 使用 LLM 生成答案
    draft_answer = generate_answer_with_glm(req.query, contexts, [])

    # 应用幻觉防护检查
    hallucination_report = None
    if services.hallucination_guard:
        hallucination_report = services.hallucination_guard.generate_hallucination_report(
            draft_answer, contexts
        )
        if hallucination_report.has_hallucination and hallucination_report.hallucination_score > 0.5:
            logger.warning("[ENHANCED HALLUCINATION] Detected potential hallucination (score: %.2f)",
                          hallucination_report.hallucination_score)

    # 构建跨规章关联的 graph insights
    graph_insights = []
    for result in search_results:
        for ref in result.cross_references:
            graph_insights.append({
                "regulation": ref.get("doc_name", ""),
                "component": ref.get("title", ""),
                "relationship": ref.get("relevance_term", "相关"),
                "description": f"来自 {ref.get('doc_name')} 的关联条款"
            })

    # 构建 citations
    citations = []
    for index, (context, result) in enumerate(zip(contexts, search_results), start=1):
        full_text = result.text or context.get("original_text", "")
        snippet = full_text[:200] + "..." if len(full_text) > 200 else full_text

        # Get source link from metadata
        source_link = context.get("metadata", {}).get("source_link", "")

        citations.append(
            Citation(
                num=index,
                source=context["metadata"].get("source", "Unknown"),
                chapter=context["metadata"].get("chapter", "未知章节"),
                section=context["metadata"].get("section", "未知条款"),
                snippet=snippet,
                highlight=result.title,
                fullText=full_text,
                sourcePath=source_link,  # 使用 sourcePath 存储源链接
                documentVersion=DOCUMENT_VERSION,
                contentMode="enhanced_multi_ccar"
            )
        )

    return QueryResponse(
        query=req.query,
        answer=draft_answer,
        guardrail={
            "status": "PASSED",
            "reasoning": "增强知识库搜索返回结果，已使用专业术语优化",
            "safe_answer": draft_answer,
            "hallucination_score": hallucination_report.hallucination_score if hallucination_report else None,
            "has_hallucination": hallucination_report.has_hallucination if hallucination_report else False,
            "hallucination_recommendations": hallucination_report.recommendations if hallucination_report else [],
        },
        citations=citations,
        graphInsights=[GraphInsight(**item) for item in graph_insights[:8]],
        graphSubgraph=None,
        responseMode="enhanced_multi_ccar",
        appVersion=APP_VERSION,
        knowledgeBaseVersion=DOCUMENT_VERSION,
        promptVersion=PROMPT_VERSION,
        embeddingVersion=EMBEDDING_VERSION,
        graphVersion=GRAPH_VERSION,
        retrievalCount=len(search_results),
    )



