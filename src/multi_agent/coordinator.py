"""
Multi-Agent Coordinator - 协调多个Agent的工作流程
"""
import logging
from typing import Optional
from .base import AgentRole, AgentMessage
from .planner import PlannerAgent
from .tool import ToolAgent
from .checker import CheckerAgent
from .answer import AnswerAgent

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """
    多Agent协调器
    管理工作流程：Planner → Tool → Checker → Answer
    支持重试机制
    """

    MAX_RETRIES = 2

    def __init__(self, vector_engine, glm_client=None, graph_store=None):
        self.planner = PlannerAgent()
        self.tool = ToolAgent(vector_engine, graph_store)
        self.checker = CheckerAgent(glm_client)
        self.answer = AnswerAgent()

    async def process_query(self, query: str, request_options: Optional[dict] = None) -> dict:
        """
        处理用户查询的完整流程

        Returns:
            dict: 包含answer, citations, graph_insights等
        """
        request_options = request_options or {}
        logger.info(f"[Coordinator] Processing query: {query[:50]}...")

        # 步骤1: Planner分析查询并制定检索计划
        planner_message = AgentMessage(
            role=AgentRole.PLANNER,
            content=query,
            data={"request": request_options},
            metadata={}
        )
        planner_result = await self.planner.process(planner_message)

        plan_data = planner_result.data.get("plan", {})
        logger.info(f"[Coordinator] Plan: {plan_data.get('retrieval_strategy')}, "
                   f"top_k={plan_data.get('top_k')}")

        # 步骤2: Tool执行检索
        tool_message = AgentMessage(
            role=AgentRole.TOOL,
            content="",
            data={"plan": plan_data},
            metadata={}
        )
        tool_result = await self.tool.process(tool_message)

        result_data = tool_result.data.get("result", {})

        # 步骤3: Checker验证结果质量
        checker_message = AgentMessage(
            role=AgentRole.CHECKER,
            content="",
            data={"plan": plan_data, "result": result_data},
            metadata={}
        )
        checker_result = await self.checker.process(checker_message)

        validation_data = checker_result.data.get("validation", {})
        needs_refinement = validation_data.get("needs_refinement", False)

        # 如果需要优化，重试一次
        if needs_refinement:
            logger.info("[Coordinator] Quality check failed, refining search...")
            refined_result = await self._refine_search(plan_data, result_data)
            if refined_result:
                result_data = refined_result
                # 重新验证
                checker_message = AgentMessage(
                    role=AgentRole.TOOL,
                    content="",
                    data={"plan": plan_data, "result": result_data},
                    metadata={}
                )
                checker_result = await self.checker.process(checker_message)
                validation_data = checker_result.data.get("validation", {})

        # 步骤4: Answer格式化最终答案
        answer_message = AgentMessage(
            role=AgentRole.ANSWER,
            content="",
            data={
                "plan": plan_data,
                "result": result_data,
                "validation": validation_data
            },
            metadata={}
        )
        answer_result = await self.answer.process(answer_message)

        # 提取结果
        answer_data = answer_result.data
        validation = answer_result.data.get("validation", {})

        citations = answer_data.get("citations", [])
        logger.info(f"[Coordinator] AnswerAgent returned {len(citations)} citations, first relevanceScore={citations[0].get('relevanceScore') if citations else 'N/A'}")

        return {
            "answer": answer_data.get("answer", ""),
            "citations": citations,
            "graph_insights": answer_data.get("graph_insights", []),
            "quality_score": answer_data.get("quality_score", 0.5),
            "is_valid": answer_data.get("is_valid", False),
            "intent_type": answer_data.get("intent_type", "regulatory"),
            "retrieval_count": answer_data.get("retrieval_count", 0),
            "relevance_scores": validation.get("relevance_scores"),
            "quality_issues": validation.get("issues", []),
            "quality_suggestions": validation.get("suggestions", []),
            "response_mode": answer_data.get("response_mode") or plan_data.get("response_mode", "multi-agent"),
        }

    async def _refine_search(
        self,
        plan_data: dict,
        current_result: dict
    ) -> Optional[dict]:
        """优化检索：使用扩展查询"""
        try:
            # 增加top_k
            refined_plan = plan_data.copy()
            refined_plan["top_k"] = min(plan_data.get("top_k", 3) + 2, 10)
            refined_plan["use_expansion"] = True

            # 重新执行检索
            tool_message = AgentMessage(
                role=AgentRole.TOOL,
                content="",
                data={"plan": refined_plan},
                metadata={}
            )
            tool_result = await self.tool.process(tool_message)
            return tool_result.data.get("result")

        except Exception as e:
            logger.error(f"[Coordinator] Refinement failed: {e}")
            return None
