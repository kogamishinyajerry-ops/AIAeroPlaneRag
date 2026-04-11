"""
Query Routes - 查询相关API端点
"""
from typing import Optional, List, Dict, Any
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies.auth import require_auth
from src.api.dependencies.deps import (
    get_vector_engine,
    services,
)
from src.rag.vector_engine import VectorStoreEngine, detect_query_intent
from src.multi_agent.coordinator import AgentCoordinator
from src.rag.confidence import score_confidence
from src.settings import (
    APP_VERSION, DOCUMENT_VERSION, EMBEDDING_VERSION,
    GRAPH_VERSION, SOURCE_CATALOG_VERSION, SOURCE_CATALOG_PATH,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Query"])


# === 请求/响应模型 ===

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)
    include_graph: bool = Field(default=True)
    response_mode: Optional[str] = Field(default=None)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "压气机喘振裕度要求",
                    "top_k": 3,
                    "include_graph": True,
                }
            ]
        }
    }


class Citation(BaseModel):
    num: int
    source: str
    chapter: str = ""
    section: str = ""
    snippet: str
    highlight: str
    fullText: str
    documentId: str
    documentVersion: str
    contentMode: str
    sourcePath: str
    officialUrl: Optional[str] = None
    relevanceScore: Optional[float] = None


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
    guardrail: Dict[str, Any]
    responseMode: str
    confidence: Optional[float] = None
    thinkingProcess: Optional[str] = None
    reasoningSteps: Optional[List[str]] = None
    uncertaintyMarkers: Optional[List[str]] = None
    graphInsights: Optional[List[Dict[str, Any]]] = None
    retrievalCount: int
    processingTimeMs: Optional[int] = None
    intentDetection: Optional[Dict[str, float]] = None
    embeddingVersion: str = EMBEDDING_VERSION
    promptVersion: str = "rag-prompt-v2"
    responseVersion: str = "v2"
    # 7-dimension confidence breakdown (P2: 置信度评分 7 维度量化)
    confidenceBreakdown: Optional[Dict[str, Any]] = None


# === 辅助函数 ===

def _fallback_answer(contexts: List[Dict[str, Any]]) -> str:
    """无LLM时的后备回答"""
    if not contexts:
        return "抱歉，暂未找到相关内容。"

    snippets = []
    for i, ctx in enumerate(contexts[:3], 1):
        text = ctx.get("text", "")[:300]
        source = ctx.get("metadata", {}).get("source", "未知来源")
        snippets.append(f"[{i}] {source}: {text}...")

    return "根据检索到的资料:\n" + "\n\n".join(snippets)


def _build_retrieval_answer(
    query: str,
    contexts: List[Dict[str, Any]],
    relevance_scores: list = None,
) -> str:
    """
    从检索结果构建结构化回答 - 不依赖LLM生成

    Args:
        query: 用户查询
        contexts: 检索到的文档上下文
        relevance_scores: LLM评估的相关性分数（可选）
    """
    if not contexts:
        return "抱歉，暂未找到与您问题相关的法规内容。请尝试调整查询词或扩大搜索范围。"

    # 根据相关性排序（如果有）
    if relevance_scores and len(relevance_scores) == len(contexts):
        scored_contexts = list(zip(contexts, relevance_scores))
        scored_contexts.sort(key=lambda x: x[1], reverse=True)
        contexts = [c[0] for c in scored_contexts]

    # 提取意图
    intent = detect_query_intent(query)
    primary_intent = max(intent.items(), key=lambda x: x[1])[0] if intent else "regulatory"

    # 构建回答
    answer_parts = []

    # 1. 直接回答（基于最相关的检索结果）
    top_context = contexts[0]
    top_text = top_context.get("text", "")
    top_metadata = top_context.get("metadata", {})
    top_source = top_metadata.get("source", "").replace(".md", "")

    # 截取关键段落作为直接回答
    sentences = top_text.split("。")
    direct_answer = ""
    for sentence in sentences[:3]:
        if len(sentence) > 20:
            direct_answer = sentence.strip()
            break

    answer_parts.append(f"【直接回答】\n{direct_answer}。")

    # 2. 条款依据
    answer_parts.append("【条款依据】")
    for i, ctx in enumerate(contexts[:3], 1):
        metadata = ctx.get("metadata", {})
        source = metadata.get("source", "").replace(".md", "")
        section = metadata.get("section", "") or metadata.get("chapter", "")
        text = ctx.get("text", "")[:200].strip()

        relevance_label = ""
        if relevance_scores and i <= len(relevance_scores):
            score = relevance_scores[i-1]
            if score >= 0.8:
                relevance_label = "✔️高度相关"
            elif score >= 0.5:
                relevance_label = "⚠️中度相关"
            else:
                relevance_label = "○低相关"

        answer_parts.append(f"- [{i}] {source} {section} {relevance_label}\n  {text}...")

    # 3. 适用说明
    answer_parts.append("【适用说明】")
    if top_source:
        answer_parts.append(f"以上条款来源于 {top_source}，适用于相关航空发动机型号审定。")

    # 4. 相关性说明
    if relevance_scores:
        avg_score = sum(relevance_scores) / len(relevance_scores)
        if avg_score >= 0.7:
            answer_parts.append(f"【质量评估】检索结果与问题高度相关（匹配度 {avg_score*100:.0f}%），答案可信度高。")
        elif avg_score >= 0.4:
            answer_parts.append(f"【质量评估】检索结果与问题中度相关（匹配度 {avg_score*100:.0f}%），请结合多条证据综合判断。")
        else:
            answer_parts.append(f"【质量评估】检索结果相关性较低（匹配度 {avg_score*100:.0f}%），建议调整查询词或咨询专业人士。")

    return "\n\n".join(answer_parts)


async def _validate_retrieval_relevance(
    query: str,
    contexts: List[Dict[str, Any]],
    glm_client,
) -> tuple[Optional[Dict[str, float]], Optional[str], Optional[List[str]]]:
    """
    使用LLM验证检索结果与查询的相关性 - 不生成答案，只评估相关性

    Returns:
        (relevance_scores, thinking_process, reasoning_steps)
        relevance_scores: 每个检索结果的相关性分数 {0.0-1.0}
    """
    if not contexts:
        return None, None, None

    # 构建上下文
    context_blocks = []
    for i, ctx in enumerate(contexts[:5], 1):
        text = ctx.get("text", "")[:500]  # 限制长度
        metadata = ctx.get("metadata", {})
        title = metadata.get("title", "")
        source = metadata.get("source", "").replace(".md", "")
        context_blocks.append(f"[文档{i}]: {source} - {title}\n{text}")

    user_prompt = f"""用户问题：{query}

请评估以下检索到的文档与用户问题的相关性。

检索文档：
{chr(10).join(context_blocks)}

## 评估要求
请逐一评估每个文档与问题的相关性，给出0.0-1.0的分数：
- 1.0: 完全相关，直接回答了问题
- 0.7-0.9: 高度相关，包含重要参考信息
- 0.4-0.6: 中度相关，有一定参考价值
- 0.1-0.3: 低度相关，仅有少量关联
- 0.0: 不相关，与问题无关

请用以下JSON格式返回：
{{"relevance_scores": [0.85, 0.6, 0.3], "reasoning": "简要说明评估理由"}}"""

    try:
        model = "glm-4-flash"

        response = glm_client.chat.completions.create(
            model=model,
            temperature=0.1,
            max_tokens=500,
            timeout=15,
            messages=[
                {"role": "system", "content": "你是一个专业的法规检索相关性评估专家。只返回JSON，不要有其他内容。"},
                {"role": "user", "content": user_prompt},
            ],
        )

        result_text = response.choices[0].message.content.strip()

        # 解析JSON响应
        import json
        import re

        # 尝试提取JSON
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            relevance_scores = result.get("relevance_scores", [])
            reasoning = result.get("reasoning", "")
            logger.info("[LLM] Relevance validation complete: %s", relevance_scores)
            return relevance_scores, reasoning, None

        return None, None, None

    except json.JSONDecodeError as exc:
        logger.warning("[LLM] Failed to parse relevance JSON: %s", str(exc))
        return None, None, None
    except Exception as exc:
        logger.error("[LLM] Relevance validation error: %s", str(exc))
        return None, None, None


# === 端点 ===

@router.post("/query", response_model=QueryResponse)
async def execute_rag_query(
    req: QueryRequest,
    api_key: str = Depends(require_auth),
    vector_engine: VectorStoreEngine = Depends(get_vector_engine),
) -> QueryResponse:
    """
    主查询端点 - 使用多Agent架构处理查询

    流程: Planner(意图分析) → Tool(检索) → Checker(验证) → Answer(格式化)
    """
    import time

    start_time = time.time()
    request_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # 创建Agent协调器
        glm_client = services.glm_client
        coordinator = AgentCoordinator(
            vector_engine=vector_engine,
            glm_client=glm_client,
            graph_store=services.graph_store if req.include_graph else None
        )

        # 使用多Agent流程处理查询
        result = await coordinator.process_query(
            req.query,
            request_options={
                "top_k": req.top_k,
                "include_graph": req.include_graph,
                "response_mode": req.response_mode,
            },
        )

        # 获取引用（已包含相关性分数和官方链接）
        citations = result.get("citations", [])
        logger.info(f"[Query] Coordinator returned {len(citations)} citations, first relevanceScore={citations[0].get('relevanceScore') if citations else 'N/A'}")

        # 确定响应模式
        response_mode = result.get("response_mode")
        if not response_mode:
            response_mode = "multi-agent"
            if result.get("relevance_scores"):
                response_mode = "agent-validated"

        processing_time = int((time.time() - start_time) * 1000)

        # ── 7-dimension confidence scoring (P2: 置信度评分 7 维度量化) ──────
        answer_text = result.get("answer", "")
        # Convert citations to the context format expected by score_confidence()
        confidence_contexts = [
            {
                "text": c.get("snippet", "") + " " + c.get("fullText", ""),
                "metadata": {
                    "source": c.get("source", ""),
                    "authority": (
                        "CAAC" if "CCAR" in c.get("source", "") else
                        "FAA"  if "FAR"  in c.get("source", "") else
                        "EASA" if "CS-E" in c.get("source", "") or "EASA" in c.get("source", "") else
                        "OTHER"
                    ),
                    "section": c.get("section", ""),
                }
            }
            for c in (citations if isinstance(citations, list) else [])
        ]
        confidence_result = score_confidence(answer_text, confidence_contexts, req.query)
        confidence_summary = confidence_result["summary"]
        confidence_breakdown = {
            "summary": confidence_result["summary"],
            "query_type": confidence_result["query_type"],
            "explanation": confidence_result["explanation"],
            "uncertainty_markers": confidence_result["uncertainty_markers"],
            "dimensions": {
                k: {
                    "label":    v["label"],
                    "score":    v["score"],
                    "weight":   v["weight"],
                    "weighted": v["weighted"],
                    "detail":   v["detail"],
                }
                for k, v in confidence_result["dimensions"].items()
            },
        }

        logger.info(
            "[Query] request_id=%s query_len=%d retrieval_count=%d response_mode=%s "
            "processing_time_ms=%d confidence=%.2f",
            request_id, len(req.query), result.get("retrieval_count", 0),
            response_mode, processing_time, confidence_summary,
        )

        return QueryResponse(
            query=req.query,
            answer=answer_text,
            citations=citations,
            guardrail={
                "status": "VERIFIED" if result.get("is_valid") else "PARTIAL",
                "reasoning": f"多Agent验证：质量分数 {result.get('quality_score', 0):.2f}",
                "safe_answer": answer_text,
                "hallucination_score": 0.2 if result.get("quality_score", 0) > 0.7 else 0.5,
                "has_hallucination": False,
            },
            responseMode=response_mode,
            confidence=confidence_summary,
            thinkingProcess="\n".join(result.get("quality_suggestions", [])) if result.get("quality_suggestions") else None,
            reasoningSteps=None,
            uncertaintyMarkers=confidence_result["uncertainty_markers"],
            retrievalCount=result.get("retrieval_count", 0),
            processingTimeMs=processing_time,
            intentDetection={result.get("intent_type", "regulatory"): 1.0},
            graphInsights=result.get("graph_insights", []),
            confidenceBreakdown=confidence_breakdown,
        )

    except HTTPException:
        raise
    except Exception as exc:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error(
            "[Query] request_id=%s error_type=%s error_message=%s processing_time_ms=%d",
            request_id, type(exc).__name__, str(exc), processing_time, exc_info=True
        )
        status_code = 503 if isinstance(exc, (ImportError, ModuleNotFoundError, ConnectionError, RuntimeError)) else 500
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": "查询处理遇到问题，请稍后重试。",
                "code": "query_processing_failed",
                "details": {
                    "error_type": type(exc).__name__,
                    "processing_time_ms": processing_time,
                },
            },
        )
