"""
Planner Agent - 意图分析和检索策略规划
"""
import logging
from typing import Dict, Any, List
from .base import BaseAgent, AgentRole, AgentMessage, RetrievalPlan

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """
    Planner Agent 负责：
    1. 分析用户查询的意图
    2. 检测查询类型（法规/方法/数值/比较/定义/交叉引用）
    3. 制定检索策略
    4. 决定是否需要图谱增强
    """

    def __init__(self):
        super().__init__("QueryPlanner", AgentRole.PLANNER)

    async def process(self, message: AgentMessage) -> AgentMessage:
        """分析查询并生成检索计划"""
        query = message.content
        request_options = message.data.get("request", {})
        self.log("info", f"Analyzing query: {query[:50]}...")

        # 检测意图
        intent_type, intent_confidence = self._detect_intent(query)

        # 制定检索策略
        plan = self._create_retrieval_plan(query, intent_type, intent_confidence, request_options)

        self.log("info", f"Generated plan: strategy={plan.retrieval_strategy}, "
                        f"intent={intent_type} ({intent_confidence:.2f})")

        return AgentMessage(
            role=AgentRole.PLANNER,
            content="",
            data={
                "plan": {
                    "query": plan.query,
                    "intent_type": plan.intent_type,
                    "intent_confidence": plan.intent_confidence,
                    "retrieval_strategy": plan.retrieval_strategy,
                    "top_k": plan.top_k,
                    "use_graph": plan.use_graph,
                    "use_expansion": plan.use_expansion,
                    "follow_up_queries": plan.follow_up_queries,
                    "response_mode": plan.response_mode,
                    "answer_style": plan.answer_style,
                }
            },
            metadata={"planner": self.name}
        )

    def _detect_intent(self, query: str) -> tuple[str, float]:
        """检测查询意图"""
        from src.rag.vector_engine import detect_query_intent

        intent_scores = detect_query_intent(query)
        if not intent_scores:
            return "regulatory", 0.5

        # 获取最高置信度的意图
        primary_intent = max(intent_scores.items(), key=lambda x: x[1])
        return primary_intent[0], primary_intent[1]

    def _create_retrieval_plan(
        self,
        query: str,
        intent_type: str,
        intent_confidence: float,
        request_options: Dict[str, Any] | None = None,
    ) -> RetrievalPlan:
        """根据意图类型创建检索计划"""
        request_options = request_options or {}
        strategy = "simple"
        top_k = 3
        use_graph = True
        use_expansion = False
        follow_up_queries = []
        response_mode = "standard"
        answer_style = "standard"

        # 根据意图类型调整策略
        if intent_type == "numerical":
            # 数值查询：需要更精确的检索
            strategy = "expanded"
            top_k = 5
            use_expansion = True
        elif intent_type == "comparison":
            # 比较查询：需要多来源检索
            strategy = "multi_source"
            top_k = 4
            use_graph = True
            # 添加比较对象的相关查询
            follow_up_queries = self._generate_comparison_queries(query)
        elif intent_type == "method":
            # 方法查询：需要详细检索
            strategy = "expanded"
            top_k = 5
            use_expansion = True
        elif intent_type == "cross_reference":
            # 交叉引用：需要图谱支持
            strategy = "graph_first"
            use_graph = True

        # 如果意图置信度低，使用扩展检索
        if intent_confidence < 0.5:
            strategy = "expanded"
            use_expansion = True
            follow_up_queries.append(query)  # 保留原查询

        requested_top_k = request_options.get("top_k")
        if isinstance(requested_top_k, int):
            top_k = max(1, min(requested_top_k, 10))

        requested_include_graph = request_options.get("include_graph")
        if isinstance(requested_include_graph, bool):
            use_graph = requested_include_graph

        requested_mode = self._normalize_response_mode(request_options.get("response_mode"))
        if requested_mode in {"simple", "expanded", "multi_source", "graph_first"}:
            strategy = requested_mode
            response_mode = requested_mode.replace("_", "-")
            if requested_mode == "graph_first":
                use_graph = True
        elif requested_mode in {"concise", "detailed", "standard"}:
            response_mode = requested_mode
            answer_style = requested_mode
            if requested_mode == "detailed":
                top_k = max(top_k, 5)

        return RetrievalPlan(
            query=query,
            intent_type=intent_type,
            intent_confidence=intent_confidence,
            retrieval_strategy=strategy,
            top_k=top_k,
            use_graph=use_graph,
            use_expansion=use_expansion,
            follow_up_queries=follow_up_queries,
            response_mode=response_mode,
            answer_style=answer_style,
        )

    def _generate_comparison_queries(self, query: str) -> List[str]:
        """为比较查询生成补充查询"""
        queries = []

        # 提取比较对象
        comparison_keywords = ["vs", "versus", "与", "和", "对比", "差异", "区别"]
        for keyword in comparison_keywords:
            if keyword in query.lower():
                parts = query.lower().split(keyword)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    queries.append(right)
                    queries.append(left)
                break

        return queries[:2]  # 最多2个补充查询

    def _normalize_response_mode(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = value.strip().lower().replace("-", "_")
        aliases = {
            "graph": "graph_first",
            "graphfirst": "graph_first",
            "multi": "multi_source",
            "multisource": "multi_source",
            "brief": "concise",
            "full": "detailed",
        }
        return aliases.get(normalized, normalized)
