"""
Answer Agent - 格式化最终答案
"""
import logging
from typing import Dict, Any, List
from .base import BaseAgent, AgentRole, AgentMessage

logger = logging.getLogger(__name__)

# 懒加载source_catalog
_catalog = None

def get_source_catalog():
    global _catalog
    if _catalog is None:
        try:
            from src.knowledge_base.source_catalog import KnowledgeSourceCatalog

            _catalog = KnowledgeSourceCatalog.load()
            logger.info(f"[AnswerAgent] Loaded source catalog with {len(_catalog.sources)} sources")
        except Exception as e:
            logger.warning(f"[AnswerAgent] Failed to load source catalog: {e}")
            _catalog = None
    return _catalog

def get_doc_url(source_name: str) -> str:
    """从source文件名获取官方文档URL"""
    if not source_name:
        return ""

    import re

    catalog = get_source_catalog()
    if not catalog:
        return ""

    # source_name可能是 "CCAR-33.md" 或 "CCAR-33-R2_chapters/E-设计与构造涡轮发动机.md"
    # 使用正则表达式提取文档基础ID（去除_chapters/...和.md后缀）
    doc_id_match = re.match(r"([^_]+)", source_name.replace(".md", ""))
    if not doc_id_match:
        return ""
    doc_id = doc_id_match.group(1).strip()

    # 尝试直接查找
    source = catalog.get_by_id(doc_id)
    if source:
        logger.info(f"[get_doc_url] Matched source '{doc_id}' -> {source.official_url}")
        return source.official_url or source.document_url or ""

    # 模糊匹配：提取doc_id中的关键部分（去掉常见前缀）
    # 例如: CCAR-33-R2 -> ccar-33-r2 -> ccar-33, 33-r2, 33
    doc_id_lower = doc_id.lower()
    # 去掉常见前缀
    for prefix in ["caac-", "faa-", "easa-"]:
        if doc_id_lower.startswith(prefix):
            doc_id_lower = doc_id_lower[len(prefix):]

    # 现在用简化后的ID去匹配catalog中ID的某一部分
    source_name_lower = source_name.lower()
    for s in catalog.sources:
        sid_lower = s.id.lower()
        # 去掉前缀后匹配
        sid_short = sid_lower
        for prefix in ["caac-", "faa-", "easa-"]:
            if sid_short.startswith(prefix):
                sid_short = sid_short[len(prefix):]
        # 检查简化后的ID是否匹配
        if (doc_id_lower in sid_short or sid_short in doc_id_lower or
            doc_id_lower.replace("-r2", "").replace("-amd6", "") in sid_short.replace("-r2", "").replace("-amd6", "")):
            logger.info(f"[get_doc_url] Fuzzy matched '{doc_id}' with '{s.id}' -> {s.official_url}")
            return s.official_url or s.document_url or ""

    logger.info(f"[get_doc_url] No match found for doc_id='{doc_id}', source_name='{source_name}'")
    return ""


class AnswerAgent(BaseAgent):
    """
    Answer Agent 负责：
    1. 根据验证结果格式化最终答案
    2. 生成结构化的回答
    3. 添加引用和来源信息
    """

    def __init__(self):
        super().__init__("AnswerFormatter", AgentRole.ANSWER)

    async def process(self, message: AgentMessage) -> AgentMessage:
        """格式化最终答案"""
        plan_data = message.data.get("plan", {})
        result_data = message.data.get("result", {})
        validation_data = message.data.get("validation", {})

        query = plan_data.get("query", "")
        contexts = result_data.get("contexts", [])
        graph_data = result_data.get("graph_data")
        relevance_scores = validation_data.get("relevance_scores")
        quality_score = validation_data.get("quality_score", 0.5)
        is_valid = validation_data.get("is_valid", False)
        intent_type = plan_data.get("intent_type", "regulatory")
        answer_style = plan_data.get("answer_style", "standard")
        response_mode = plan_data.get("response_mode", "standard")

        self.log("info", f"Formatting answer for query: {query[:50]}...")
        self.log("info", f"Validation data keys: {list(validation_data.keys())}, relevance_scores: {relevance_scores}")

        # 构建结构化答案
        answer_text = self._build_structured_answer(
            query, contexts, relevance_scores, intent_type, quality_score, graph_data, answer_style
        )

        # 构建引用列表（附上相关性分数）
        citations = self._build_citations(contexts, relevance_scores)

        # 构建图谱洞察（如果有）
        graph_insights = self._extract_graph_insights(graph_data, contexts) if graph_data else []

        return AgentMessage(
            role=AgentRole.ANSWER,
            content=answer_text,
            data={
                "answer": answer_text,
                "citations": citations,
                "graph_insights": graph_insights,
                "quality_score": quality_score,
                "is_valid": is_valid,
                "intent_type": intent_type,
                "retrieval_count": len(contexts),
                "relevance_scores": relevance_scores,
                "response_mode": response_mode,
            },
            metadata={"agent": self.name}
        )

    def _build_structured_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        relevance_scores: List[float],
        intent_type: str,
        quality_score: float,
        graph_data: Dict[str, Any] | None,
        answer_style: str,
    ) -> str:
        """构建结构化答案"""
        if not contexts:
            return "抱歉，暂未找到与您问题相关的法规内容。请尝试调整查询词或扩大搜索范围。"

        # 检查最高相关性
        max_relevance = 0.0
        if relevance_scores and len(relevance_scores) == len(contexts):
            max_relevance = max(relevance_scores)
            # 根据相关性排序（同时保留分数）
            scored = list(zip(contexts, relevance_scores))
            scored.sort(key=lambda x: x[1], reverse=True)
            contexts = [c[0] for c in scored]
            relevance_scores = [c[1] for c in scored]

        # 如果相关性极低，尝试使用fallback知识
        if max_relevance < 0.2:
            fallback_answer = self._generate_fallback_answer(query, contexts)
            if fallback_answer:
                return fallback_answer

        answer_parts = []

        # 1. 直接回答
        top_context = contexts[0]
        top_text = top_context.get("text", "")
        top_metadata = top_context.get("metadata", {})
        direct_answer = self._extract_direct_answer(top_text, intent_type)

        answer_parts.append("【直接回答】")
        if direct_answer:
            answer_parts.append(f"{direct_answer}。")
        else:
            # 默认：从文本中提取第一句完整的话
            sentences = [s.strip() for s in top_text.split("。") if len(s.strip()) > 20]
            if sentences:
                answer_parts.append(f"{sentences[0]}。")

        # 2. 条款依据（逐条显示，每条标注相关性）
        citation_limit = 2 if answer_style == "concise" else 5
        answer_parts.append("\n【条款依据】")
        for i, ctx in enumerate(contexts[:citation_limit], 1):
            metadata = ctx.get("metadata", {})
            source = metadata.get("source", "").replace(".md", "")
            section = metadata.get("section", "") or metadata.get("chapter", "")
            text = ctx.get("text", "")[:300].strip()

            # 相关性标签和分数
            relevance_info = ""
            if relevance_scores and i <= len(relevance_scores):
                score = relevance_scores[i-1]
                pct = int(score * 100)
                if score >= 0.8:
                    relevance_info = f"✔️高度相关 ({pct}%)"
                elif score >= 0.5:
                    relevance_info = f"⚠️中度相关 ({pct}%)"
                else:
                    relevance_info = f"○低相关 ({pct}%)"
            else:
                relevance_info = "（相关性待评估）"

            # 条款标题行
            answer_parts.append(f"\n[{i}] {source} {section}")
            answer_parts.append(f"    相关性: {relevance_info}")
            # 条款内容（分段显示）
            sentences = text.split("。")
            for sent in sentences[:3]:
                sent = sent.strip()
                if len(sent) > 10:
                    answer_parts.append(f"    {sent}。")

        # 3. 适用说明
        answer_parts.append("\n【适用说明】")
        top_source = top_metadata.get("source", "").replace(".md", "")
        if top_source:
            answer_parts.append(f"以上条款来源于 {top_source}，适用于相关航空发动机型号审定。")

        if graph_data and answer_style == "detailed":
            summary = graph_data.get("summary")
            node_count = len(graph_data.get("nodes", []))
            edge_count = len(graph_data.get("edges", []))
            if summary or node_count or edge_count:
                answer_parts.append("\n【图谱补充】")
                if summary:
                    answer_parts.append(str(summary))
                answer_parts.append(f"图谱上下文包含 {node_count} 个节点、{edge_count} 条关系。")

        # 4. 质量评估
        if answer_style != "concise":
            answer_parts.append("\n【质量评估】")
            if quality_score >= 0.7:
                answer_parts.append(f"检索结果与问题高度相关（匹配度 {quality_score*100:.0f}%），答案可信度高。")
            elif quality_score >= 0.4:
                answer_parts.append(f"检索结果与问题中度相关（匹配度 {quality_score*100:.0f}%），请结合多条证据综合判断。")
            else:
                answer_parts.append(f"检索结果相关性较低（匹配度 {quality_score*100:.0f}%），建议调整查询词或咨询专业人士。")

        return "\n".join(answer_parts)

    def _generate_fallback_answer(
        self,
        query: str,
        contexts: List[Dict[str, Any]]
    ) -> str:
        """
        当检索结果相关性很低时，尝试从已有文档中提取有用信息
        这是一个智能fallback，不是直接生成答案
        """
        if not contexts:
            return ""

        # 分析查询关键词
        import re
        query_keywords = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', query.lower()))
        query_keywords = {k for k in query_keywords if len(k) >= 2}

        # 从每个文档中提取可能相关的片段
        relevant_snippets = []
        for ctx in contexts[:3]:
            text = ctx.get("text", "")
            metadata = ctx.get("metadata", {})
            source = metadata.get("source", "").replace(".md", "")

            # 找包含查询关键词的句子
            sentences = text.split("。")
            for sentence in sentences:
                # 检查句子中是否包含任何查询关键词
                sentence_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', sentence.lower()))
                overlap = query_keywords & sentence_words
                if len(overlap) >= 1 and len(sentence) > 20:
                    relevant_snippets.append({
                        "source": source,
                        "sentence": sentence.strip(),
                        "overlap_count": len(overlap)
                    })

        if relevant_snippets:
            # 按关键词重叠数排序
            relevant_snippets.sort(key=lambda x: x["overlap_count"], reverse=True)

            # 构建答案
            answer_parts = []
            answer_parts.append("【相关但不精确的结果】")
            answer_parts.append("")
            answer_parts.append("未找到完全匹配的内容，以下是部分相关的法规片段：")
            answer_parts.append("")

            for i, snippet in enumerate(relevant_snippets[:3], 1):
                answer_parts.append(f"- {snippet['source']}")
                answer_parts.append(f"  \"{snippet['sentence'][:150]}...\"")
                answer_parts.append("")

            answer_parts.append("【建议】")
            answer_parts.append("• 尝试使用更精确的术语")
            answer_parts.append("• 查阅具体的航空发动机设计手册")
            answer_parts.append("• 如需准确数值，请咨询专业人士")

            return "\n".join(answer_parts)

        return ""

    def _extract_direct_answer(self, text: str, intent_type: str) -> str:
        """从文本中提取直接回答"""
        # 对于数值查询，寻找数值信息
        if intent_type == "numerical":
            import re
            # 寻找百分比、数值范围等
            numbers = re.findall(r'\d+(?:\.\d+)?%?', text)
            if numbers:
                return f"相关数值要求为 {', '.join(numbers[:5])}"

        # 默认：提取第一段完整的话
        sentences = text.split("。")
        for sentence in sentences:
            if len(sentence) > 15 and len(sentence) < 200:
                return sentence.strip()

        return text[:200] if len(text) > 200 else text

    def _build_citations(self, contexts: List[Dict[str, Any]], relevance_scores: List[float] = None) -> List[Dict]:
        """构建引用列表"""
        from src.settings import DOCUMENT_VERSION

        self.log("info", f"_build_citations called with {len(contexts)} contexts, relevance_scores={relevance_scores}")

        citations = []
        for i, ctx in enumerate(contexts, 1):
            metadata = ctx.get("metadata", {})
            source_name = metadata.get("source", "")
            official_url = get_doc_url(source_name)

            # 获取相关性分数
            rel_score = None
            if relevance_scores and i <= len(relevance_scores):
                rel_score = relevance_scores[i - 1]

            citations.append({
                "num": i,
                "source": source_name,
                "chapter": metadata.get("chapter", ""),
                "section": metadata.get("section", ""),
                "snippet": ctx.get("text", "")[:300],
                "highlight": ctx.get("text", "")[:200],
                "fullText": ctx.get("text", ""),
                "documentId": metadata.get("chunk_id", ""),
                "documentVersion": DOCUMENT_VERSION,
                "contentMode": "structured",
                "sourcePath": metadata.get("source", ""),
                "officialUrl": official_url,
                "relevanceScore": rel_score,
            })
        self.log("info", f"_build_citations returning {len(citations)} citations, first has relevanceScore={citations[0].get('relevanceScore') if citations else 'N/A'}")
        return citations

    def _extract_graph_insights(
        self,
        graph_data: Dict[str, Any],
        contexts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从图谱数据中提取洞察"""
        insights = []
        if not graph_data:
            return insights

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # 简单统计
        node_types = {}
        for node in nodes[:10]:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        if node_types:
            insights.append({
                "type": "node_distribution",
                "data": node_types
            })

        # 如果有边数据，提取关联关系
        if edges:
            sample_edges = edges[:5]
            relations = [e.get("type", "related") for e in sample_edges]
            insights.append({
                "type": "sample_relations",
                "data": list(set(relations))
            })

        return insights
