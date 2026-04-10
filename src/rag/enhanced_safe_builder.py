#!/usr/bin/env python3
"""
增强安全答案构建器 v2

专注于提升可信度和可用性
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedSafeAnswerBuilder:
    """增强安全答案构建器"""

    # 专业术语模板
    TERM_TEMPLATES = {
        '喘振裕度': 'surge margin',
        '防火墙': 'firewall',
        '转子': 'rotor',
        '压气机': 'compressor',
        '涡轮': 'turbine',
        'APU': 'Auxiliary Power Unit',
    }

    # 条款类型说明
    CLAUSE_TYPE_EXPLANATIONS = {
        '设计要求': '规定了部件设计必须满足的技术标准',
        '试验要求': '规定了必须进行的试验验证',
        '性能标准': '规定了系统必须达到的性能指标',
        '安全要求': '规定了保障安全必须采取的措施',
    }

    def __init__(self, knowledge_base_path: str = None):
        self.kb_path = Path(knowledge_base_path) if knowledge_base_path else None
        self.domain_context = self._load_domain_context()

    def _load_domain_context(self) -> Dict:
        """加载领域上下文"""
        context = {
            '发动机领域': {
                '关键部件': ['压气机', '涡轮', '燃烧室', '转子', 'APU'],
                '关键参数': ['喘振裕度', '温度限制', '转速', '推力'],
                '安全要求': ['防火', '防爆', '转子完整性', '寿命限制']
            },
            '结构领域': {
                '关键部件': ['机身', '机翼', '起落架', '襟翼'],
                '关键参数': ['载荷', '应力', '疲劳寿命'],
                '安全要求': ['强度', '刚度', '损伤容限']
            },
            '系统领域': {
                '关键部件': ['液压系统', '燃油系统', '电气系统', '空调系统'],
                '关键参数': ['压力', '流量', '容量'],
                '安全要求': ['冗余', '隔离', '应急操作']
            }
        }
        return context

    def build_enhanced_answer(
        self,
        query: str,
        contexts: List[Dict],
        query_type: str = "general"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        构建增强答案

        提升：
        1. 更详细的条款引用
        2. 术语解释
        3. 相关条款链接
        4. 领域上下文
        """
        if not contexts:
            return "抱歉，未找到相关条款信息。", {"safe": False, "reason": "no_contexts"}

        metadata = {
            "safe": True,
            "enhancements": [],
            "domain": None
        }

        # 1. 确定查询领域
        domain = self._identify_domain(query)
        metadata["domain"] = domain

        # 2. 从多个上下文提取信息
        primary_ctx = contexts[0]
        secondary_ctxs = contexts[1:3] if len(contexts) > 1 else []

        # 3. 构建详细答案
        answer_parts = []

        # 开头：来源引用
        citation = self._build_detailed_citation(primary_ctx)
        answer_parts.append(citation)

        # 核心内容：从主上下文提取
        core_content = self._extract_core_content(primary_ctx, query)
        answer_parts.append(core_content)

        # 添加术语解释
        terms_found = self._find_and_explain_terms(core_content, domain)
        if terms_found:
            term_explanations = "术语说明：" + "；".join(terms_found[:3])
            answer_parts.append(term_explanations)
            metadata["enhancements"].append(f"添加了{len(terms_found)}个术语解释")

        # 添加相关条款
        if secondary_ctxs:
            related = self._build_related_clauses(secondary_ctxs)
            if related:
                answer_parts.append(related)
                metadata["enhancements"].append(f"添加了{len(secondary_ctxs)}个相关条款")

        # 添加领域上下文
        if domain:
            domain_info = self._add_domain_context(query, domain)
            if domain_info:
                answer_parts.append(domain_info)
                metadata["enhancements"].append("添加了领域上下文")

        # 组合答案
        answer = " ".join(answer_parts)

        # 清理格式
        answer = self._clean_format(answer)

        return answer, metadata

    def _identify_domain(self, query: str) -> str:
        """识别查询领域"""
        query_lower = query.lower()

        domain_keywords = {
            '发动机领域': ['发动机', '压气机', '涡轮', 'apu', '转子', '喘振', '燃烧室', '推力'],
            '结构领域': ['机身', '机翼', '起落架', '襟翼', '副翼', '尾翼', '结构', '载荷'],
            '系统领域': ['液压', '燃油', '电气', '空调', '系统', '控制', '仪表']
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return domain

        return None

    def _build_detailed_citation(self, ctx: Dict) -> str:
        """构建详细引用"""
        metadata = ctx.get("metadata", {})
        source = metadata.get("source", "").replace(".md", "").replace("_", "-")
        section = metadata.get("section", "")
        title = metadata.get("title", "")

        if section and title:
            return f"根据{source}第{section}条「{title}」规定："
        elif title:
            return f"根据{source}「{title}」规定："
        else:
            return f"根据{source}相关规定："

    def _extract_core_content(self, ctx: Dict, query: str) -> str:
        """提取核心内容"""
        text = ctx.get("text", "")
        original_text = ctx.get("original_text", "") or text
        metadata = ctx.get("metadata", {})

        # 优先使用summary
        summary = metadata.get("summary", "")
        title = metadata.get("title", "")

        content_parts = []

        # 如果有summary，使用它
        if summary and len(summary) > 20:
            content_parts.append(summary)

        # 提取关键条款内容
        sentences = re.split(r'[。；;]', original_text)
        for sentence in sentences[:5]:
            sentence = sentence.strip()
            if len(sentence) > 15:
                # 检查是否包含关键词
                keywords = ['必须', '应当', '不得', '要求', '规定', '标准']
                if any(kw in sentence for kw in keywords):
                    content_parts.append(sentence)

        # 如果没有提取到内容，使用前几句话
        if not content_parts:
            content_parts = sentences[:3]

        content = "；".join(p for p in content_parts if p)

        # 限制长度
        if len(content) > 400:
            content = content[:400] + "..."

        return content

    def _find_and_explain_terms(self, content: str, domain: str) -> List[str]:
        """查找并解释术语"""
        explanations = []

        # 查找匹配的术语
        for term, english in self.TERM_TEMPLATES.items():
            if term in content:
                explanations.append(f"{term}（{english}）")

        # 如果有领域上下文，添加领域术语
        if domain and domain in self.domain_context:
            domain_info = self.domain_context[domain]
            for term in domain_info.get('关键部件', []):
                if term in content and term not in [e.split('（')[0] for e in explanations]:
                    explanations.append(f"{term}（关键部件）")

        return explanations[:3]

    def _build_related_clauses(self, contexts: List[Dict]) -> str:
        """构建相关条款"""
        related = []

        for ctx in contexts[:3]:
            metadata = ctx.get("metadata", {})
            source = metadata.get("source", "").replace(".md", "").replace("_", "-")
            section = metadata.get("section", "")
            title = metadata.get("title", "")

            if section and title:
                related.append(f"{source}第{section}条")
            elif title:
                related.append(f"{source}「{title}」")

        if related:
            return f"相关条款：{', '.join(related)}"
        return ""

    def _add_domain_context(self, query: str, domain: str) -> str:
        """添加领域上下文"""
        if not domain or domain not in self.domain_context:
            return ""

        domain_info = self.domain_context[domain]

        # 根据查询类型选择相关上下文
        context_parts = []

        if any(kw in query for kw in ['要求', '规定', '标准']):
            requirements = domain_info.get('安全要求', [])
            if requirements:
                context_parts.append(f"该领域关键安全要求包括：{', '.join(requirements[:3])}")

        return " ".join(context_parts) if context_parts else ""

    def _clean_format(self, answer: str) -> str:
        """清理格式"""
        # 移除多余的空格
        answer = re.sub(r'\s+', ' ', answer)

        # 确保句子之间有适当的分隔
        answer = answer.replace('； ', '；').replace('。 ', '。')

        # 确保结尾有标点
        if not answer[-1] in '。！？.!?':
            answer += '。'

        return answer.strip()


__all__ = ['EnhancedSafeAnswerBuilder']
