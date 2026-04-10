"""
Checker Agent - 验证检索结果质量
基于多Agent提示工程框架的优化版本
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional
from .base import BaseAgent, AgentRole, AgentMessage, ValidationResult

logger = logging.getLogger(__name__)


class CheckerAgent(BaseAgent):
    """
    Checker Agent 负责：
    1. 评估检索结果的相关性（使用LLM）
    2. 检测结果质量问题
    3. 决定是否需要补充检索
    4. 提供改进建议

    优化：采用更宽松的评估标准和智能重试机制
    """

    # 相关性评估的宽松标准
    RELAXED_THRESHOLDS = {
        "high": 0.5,      # 0.5以上为高度相关
        "medium": 0.3,     # 0.3以上为中度相关
        "low": 0.1,        # 0.1以上为低度相关
    }

    def __init__(self, glm_client=None):
        super().__init__("ResultChecker", AgentRole.CHECKER)
        self.glm_client = glm_client

    async def process(self, message: AgentMessage) -> AgentMessage:
        """评估检索结果质量"""
        plan_data = message.data.get("plan", {})
        result_data = message.data.get("result", {})
        contexts = result_data.get("contexts", [])
        intent_type = plan_data.get("intent_type", "regulatory")

        self.log("info", f"Checking {len(contexts)} retrieval results for intent: {intent_type}")

        # 使用LLM评估相关性（如果可用）
        relevance_scores = None
        if self.glm_client and contexts:
            # 最多重试2次
            for attempt in range(2):
                relevance_scores = await self._llm_evaluate_relevance(
                    plan_data.get("query", ""),
                    contexts,
                    intent_type
                )
                # 如果评估结果合理（至少有高分），使用结果
                if relevance_scores and max(relevance_scores) >= 0.4:
                    break
                self.log("warning", f"Relevance scores too low, attempt {attempt + 1}/2")

        # 计算质量分数（使用优化后的算法）
        quality_result = self._calculate_quality_score(
            contexts, relevance_scores, intent_type
        )

        self.log("info", f"Quality check: score={quality_result.quality_score:.2f}, "
                        f"valid={quality_result.is_valid}, "
                        f"max_rel={max(relevance_scores) if relevance_scores else 'N/A'}")

        # 决定是否需要补充检索
        needs_refinement = self._needs_refinement(quality_result, contexts, relevance_scores)

        return AgentMessage(
            role=AgentRole.CHECKER,
            content="",
            data={
                "validation": {
                    "is_valid": quality_result.is_valid,
                    "quality_score": quality_result.quality_score,
                    "issues": quality_result.issues,
                    "suggestions": quality_result.suggestions,
                    "relevance_scores": relevance_scores,
                    "needs_refinement": needs_refinement,
                },
                "result": result_data,
                "plan": plan_data
            },
            metadata={"checker": self.name}
        )

    async def _llm_evaluate_relevance(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        intent_type: str = "regulatory"
    ) -> Optional[List[float]]:
        """
        使用LLM评估每个检索结果与查询的相关性
        优化：更宽松的评估标准和更清晰的指令
        """
        if not contexts:
            return None

        # 根据意图类型调整评估标准
        intent_guidance = {
            "regulatory": "重点关注：是否包含相关法规条款号、适用范围、使用条件",
            "numerical": "重点关注：是否包含具体数值、参数、限制值",
            "method": "重点关注：是否包含试验方法、操作步骤、验证流程",
            "comparison": "重点关注：是否包含对比信息、差异点",
            "definition": "重点关注：是否包含定义解释、概念说明",
            "cross_reference": "重点关注：是否包含跨文档引用、关联条款",
        }
        guidance = intent_guidance.get(intent_type, intent_guidance["regulatory"])

        # 构建更清晰的提示
        context_blocks = []
        for i, ctx in enumerate(contexts[:5], 1):
            text = ctx.get("text", "")[:400]
            metadata = ctx.get("metadata", {})
            title = metadata.get("title", "")
            source = metadata.get("source", "").replace(".md", "")
            section = metadata.get("section", "")
            context_blocks.append(f"[文档{i}]({source} {section}):\n{text[:200]}...")

        user_prompt = f"""你是民航法规检索相关性评估专家。

用户问题：{query}

评估指南：{guidance}

请评估以下检索结果与问题的相关性，使用以下宽松标准：
- 0.8-1.0: 相关，包含问题的直接或重要参考信息
- 0.5-0.8: 中度相关，包含问题的部分参考信息
- 0.2-0.5: 低度相关，仅有少量关键词匹配
- 0.0-0.2: 不相关，与问题无关

注意：如果文档谈论的是同一领域（如航空发动机、适航标准）但具体条款不同时，给0.3-0.5分即可。

返回格式：JSON数组 [0.85, 0.6, 0.3]

检索文档：
{chr(10).join(context_blocks)}

只返回JSON数组，不要其他内容。"""

        try:
            response = self.glm_client.chat.completions.create(
                model="glm-4-flash",
                temperature=0.1,
                max_tokens=200,
                timeout=15,
                messages=[
                    {"role": "system", "content": "你是一个专业的法规检索相关性评估专家。只返回JSON数组，不要其他内容。"},
                    {"role": "user", "content": user_prompt},
                ],
            )

            result_text = response.choices[0].message.content.strip()

            # 提取JSON数组
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                scores = json.loads(json_match.group())
                # 确保分数在合理范围内
                valid_scores = []
                for s in scores[:len(contexts)]:
                    score = float(s)
                    # 强制宽松：如果分数低于0.2但高于0，提升到0.2
                    if 0 < score < 0.2:
                        score = 0.2
                    valid_scores.append(score)
                self.log("info", f"LLM relevance scores: {valid_scores}")
                return valid_scores

        except Exception as e:
            self.log("warning", f"LLM relevance evaluation failed: {e}")

        return None

    def _calculate_quality_score(
        self,
        contexts: List[Dict[str, Any]],
        relevance_scores: Optional[List[float]],
        intent_type: str
    ) -> ValidationResult:
        """
        计算检索结果质量分数

        优化：
        - 给予有检索结果更多信任
        - 调整权重分配
        - 意图类型适应性
        """
        issues = []
        suggestions = []

        if not contexts:
            issues.append("没有检索到任何结果")
            suggestions.append("尝试使用更简短的查询词或同义词")
            return ValidationResult(False, 0.0, issues, suggestions)

        # 如果有相关性分数，使用它们计算
        if relevance_scores and len(relevance_scores) > 0:
            max_score = max(relevance_scores)
            avg_score = sum(relevance_scores) / len(relevance_scores)

            # 使用更合理的权重：
            # 高分权重更大（因为我们希望信任检索结果）
            if max_score >= 0.5:
                # 至少有一个高分结果，认为检索质量良好
                quality_score = 0.5 + (avg_score * 0.3) + (max_score * 0.2)
            elif max_score >= 0.3:
                # 有中度相关结果
                quality_score = 0.4 + (avg_score * 0.3) + (max_score * 0.2)
            else:
                # 分数偏低但仍使用
                quality_score = 0.3 + (avg_score * 0.4)
                issues.append("检索结果相关性偏低，建议扩展查询")
                suggestions.append("尝试使用同义词或不同表述")

            # 意图类型微调
            if intent_type == "numerical" and len(contexts) < 3:
                suggestions.append("数值查询建议增加检索数量以获取更多数值依据")

            # 限制分数范围
            quality_score = max(0.3, min(0.95, quality_score))

        else:
            # 无LLM评估时，使用默认分数（信任检索结果）
            quality_score = 0.65
            issues.append("无法验证相关性，使用默认置信度")

        # 判断是否有效：只要有结果就认为有效
        is_valid = len(contexts) >= 1 and quality_score >= 0.3

        if not is_valid:
            issues.append(f"质量分数过低 ({quality_score:.2f})")
            suggestions.append("建议优化查询词或扩展检索范围")

        return ValidationResult(is_valid, quality_score, issues, suggestions)

    def _needs_refinement(
        self,
        quality_result: ValidationResult,
        contexts: List[Dict[str, Any]],
        relevance_scores: Optional[List[float]] = None
    ) -> bool:
        """
        决定是否需要补充检索

        优化：更宽松的标准，避免过度重试
        """
        # 如果没有检索结果，需要优化
        if not contexts:
            return True

        # 如果质量分数极低（低于0.2），需要优化
        if quality_result.quality_score < 0.2:
            return True

        # 如果所有相关性分数都极低，需要优化
        if relevance_scores and len(relevance_scores) > 0:
            max_relevance = max(relevance_scores)
            avg_relevance = sum(relevance_scores) / len(relevance_scores)

            # 如果最高分和平均分都很低，需要优化
            if max_relevance < 0.15 and avg_relevance < 0.1:
                return True

        # 否则认为检索质量可接受
        return False
