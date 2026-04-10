#!/usr/bin/env python3
"""
安全答案构建器

专注于构建低幻觉风险的答案，确保所有内容都有源支持
"""

import logging
import re
from typing import Dict, List, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SafeAnswerBuilder:
    """安全答案构建器 - 最小化幻觉风险"""

    # 模板
    ANSWER_TEMPLATES = [
        "根据{source}第{section}条规定，{summary}",
        "按照{source}的要求，{summary}",
        "根据{source}的相关规定，{summary}",
    ]

    UNCERTAINTY_MARKERS = [
        "根据现有资料",
        "基于规章要求",
        "按照相关规定",
        "根据知识库信息"
    ]

    def __init__(self):
        self.max_extract_length = 500  # 从上下文提取的最大长度

    def build_safe_answer(
        self,
        query: str,
        contexts: List[Dict],
        query_type: str = "general"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        构建安全答案

        策略：
        1. 主要内容直接从上下文提取
        2. 添加不确定性标记
        3. 只包含在源中验证过的内容
        4. 添加精确引用
        """
        if not contexts:
            return "抱歉，未找到相关条款信息。", {"safe": False, "reason": "no_contexts"}

        metadata = {
            "safe": True,
            "source_count": len(contexts),
            "extraction_used": [],
            "added_uncertainty": False
        }

        # 1. 从最佳上下文提取内容
        primary_ctx = contexts[0]
        extracted_content = self._extract_safe_content(primary_ctx, query)

        # 2. 构建答案核心
        source = self._format_source(primary_ctx)
        section = self._format_section(primary_ctx)

        # 使用提取的内容构建答案
        answer_core = extracted_content[:self.max_extract_length]

        # 3. 添加不确定性标记
        answer = f"{self.UNCERTAINTY_MARKERS[0]}，{answer_core}"
        metadata["added_uncertainty"] = True

        # 4. 添加精确引用
        citation = self._build_citation(primary_ctx)
        if citation:
            answer += f" {citation}"
            metadata["citation"] = citation

        # 5. 如果有多个相关上下文，添加更多参考
        if len(contexts) > 1:
            additional = self._add_additional_references(contexts[1:3])
            if additional:
                answer += additional

        # 6. 清理和格式化
        answer = self._clean_answer(answer)

        metadata["extraction_used"].append(primary_ctx.get("metadata", {}).get("source", "unknown"))

        return answer, metadata

    def _extract_safe_content(self, ctx: Dict, query: str) -> str:
        """安全提取内容"""
        text = ctx.get("text", "")
        original_text = ctx.get("original_text", "") or text
        metadata = ctx.get("metadata", {})

        # 优先使用 summary 或 title
        summary = metadata.get("summary", "")
        title = metadata.get("title", "")

        # 构建内容
        parts = []

        if title:
            parts.append(title)

        if summary and len(summary) > 10:
            parts.append(summary)
        else:
            # 使用文本的前部分
            if original_text:
                sentences = re.split(r'[。！？.!?]', original_text)
                if sentences:
                    # 取前2-3个句子
                    parts.extend(sentences[:min(3, len(sentences))])

        content = "。".join(p for p in parts if p)

        # 限制长度
        if len(content) > self.max_extract_length:
            content = content[:self.max_extract_length] + "..."

        return content.strip()

    def _format_source(self, ctx: Dict) -> str:
        """格式化来源"""
        metadata = ctx.get("metadata", {})
        source = metadata.get("source", "").replace(".md", "").replace("_", "-")
        return source

    def _format_section(self, ctx: Dict) -> str:
        """格式化条款号"""
        metadata = ctx.get("metadata", {})
        section = metadata.get("section", "")
        return section

    def _build_citation(self, ctx: Dict) -> str:
        """构建引用"""
        metadata = ctx.get("metadata", {})
        source = self._format_source(ctx)
        section = self._format_section(ctx)

        if section:
            return f"(参考文献: {source}:{section})"
        elif source:
            return f"(参考文献: {source})"
        return ""

    def _add_additional_references(self, contexts: List[Dict]) -> str:
        """添加额外引用"""
        citations = []
        for ctx in contexts:
            citation = self._build_citation(ctx)
            if citation:
                citations.append(citation)

        if citations:
            return f" 相关条款: {', '.join(citations[:2])}"
        return ""

    def _clean_answer(self, answer: str) -> str:
        """清理答案"""
        # 移除多余的空格和空行
        answer = re.sub(r'\s+', ' ', answer)

        # 确保句子结尾有标点
        if not answer[-1] in '。！？.!?':
            answer += '。'

        return answer.strip()

    def calculate_safety_score(
        self,
        answer: str,
        contexts: List[Dict]
    ) -> Tuple[float, List[str]]:
        """
        计算答案的安全分数

        返回: (安全分数, 风险项列表)
        """
        safety_score = 1.0
        risk_items = []

        # 1. 检查内容是否主要来自上下文
        statements = re.split(r'[。！？.!?]', answer)
        verified_count = 0
        total_count = 0

        for stmt in statements:
            stmt = stmt.strip()
            if len(stmt) < 5:
                continue
            total_count += 1

            # 检查是否在上下文中
            found = False
            for ctx in contexts:
                text = ctx.get("text", "")
                # 检查关键词匹配
                words = [w for w in stmt.split() if len(w) >= 2]
                if any(word in text for word in words):
                    found = True
                    break

            if found:
                verified_count += 1
            else:
                risk_items.append(f"未验证陈述: {stmt[:30]}...")

        if total_count > 0:
            verification_ratio = verified_count / total_count
            safety_score = verification_ratio

        # 2. 检查是否有不确定性标记
        has_uncertainty = any(marker in answer for marker in self.UNCERTAINTY_MARKERS)
        if not has_uncertainty:
            safety_score *= 0.9
            risk_items.append("缺少不确定性标记")

        # 3. 检查是否有引用
        has_citation = bool(re.search(r'参考文献|§|第\s*\d+\s*条', answer))
        if not has_citation:
            safety_score *= 0.85
            risk_items.append("缺少引用")

        return safety_score, risk_items


__all__ = ['SafeAnswerBuilder']
