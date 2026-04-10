#!/usr/bin/env python3
"""
幻觉降低模块

专注于将幻觉风险从0.19降到0.1以下
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HallucinationReducer:
    """幻觉降低器"""

    # 不确定性标记
    UNCERTAINTY_PHRASES = [
        "根据现有资料",
        "在一般情况下",
        "通常情况下",
        "根据相关条款",
        "基于当前知识库",
        "可能需要",
        "应参考具体规章"
    ]

    # 需要验证的陈述模式
    RISKY_PATTERNS = [
        (r'(是|为)\s*([^\u3000-\u303f]{2,10})\s*(的|。|，)', "定义性陈述"),
        (r'(有|存在)\s*([^\u3000-\u303f]{2,10})\s*(的|。|，)', "存在性陈述"),
        (r'(必须|应当|禁止)\s*([^\u3000-\u303f]{2,15})', "规范性陈述"),
        (r'(\d+(?:\.\d+)?)\s*([%|度|分钟|小时|秒|次|个|项|条|节|章])', "数值陈述"),
    ]

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)

        # 加载验证规则
        self.verification_rules = self._load_verification_rules()

        # 加载等效条款
        self.equivalent_clauses = self._load_equivalent_clauses()

    def _load_verification_rules(self) -> Dict:
        """加载验证规则"""
        rules_file = self.kb_path / "verification" / "fact_check_rules.json"
        try:
            if rules_file.exists():
                with open(rules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载验证规则失败: {e}")
        return {"rules": []}

    def _load_equivalent_clauses(self) -> Dict:
        """加载等效条款"""
        links_file = self.kb_path / "knowledge_links" / "cross_document_links.json"
        try:
            if links_file.exists():
                with open(links_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    equivalent = data.get("equivalent_links", [])
                    mapping = {}
                    for link in equivalent:
                        if "clauses" in link:
                            clauses = link["clauses"]
                            for i, clause in enumerate(clauses):
                                others = [c for c in clauses if c != clause]
                                mapping[clause] = others
                    return mapping
        except Exception as e:
            logger.warning(f"加载等效条款失败: {e}")
        return {}

    def analyze_hallucination_risk(
        self,
        answer: str,
        contexts: List[Dict],
        query: str = ""
    ) -> Tuple[float, List[Dict]]:
        """
        分析幻觉风险

        返回: (风险分数, 风险项列表)
        """
        risk_items = []
        total_risk = 0.0

        # 1. 检查源外陈述
        source_outside = self._check_source_outside_statements(answer, contexts)
        if source_outside:
            risk_items.append({
                "type": "source_outside",
                "severity": "high",
                "count": len(source_outside),
                "examples": source_outside[:2]
            })
            total_risk += 0.3 * min(len(source_outside) / 5, 1.0)

        # 2. 检查未验证数值
        unverified_numbers = self._check_unverified_numbers(answer, contexts)
        if unverified_numbers:
            risk_items.append({
                "type": "unverified_numbers",
                "severity": "medium",
                "count": len(unverified_numbers),
                "values": unverified_numbers[:3]
            })
            total_risk += 0.15 * min(len(unverified_numbers) / 3, 1.0)

        # 3. 检查绝对性断言
        absolute_claims = self._check_absolute_claims(answer, contexts)
        if absolute_claims:
            risk_items.append({
                "type": "absolute_claims",
                "severity": "high",
                "count": len(absolute_claims),
                "examples": absolute_claims[:2]
            })
            total_risk += 0.25 * min(len(absolute_claims) / 3, 1.0)

        # 4. 检查未知术语
        unknown_terms = self._check_unknown_terms(answer)
        if unknown_terms:
            risk_items.append({
                "type": "unknown_terms",
                "severity": "low",
                "count": len(unknown_terms),
                "terms": unknown_terms[:3]
            })
            total_risk += 0.1 * min(len(unknown_terms) / 5, 1.0)

        # 5. 检查缺少引用
        missing_citations = self._check_missing_citations(answer, contexts)
        if missing_citations:
            risk_items.append({
                "type": "missing_citations",
                "severity": "medium",
                "count": missing_citations
            })
            total_risk += 0.2 if missing_citations else 0

        return min(total_risk, 1.0), risk_items

    def _check_source_outside_statements(
        self,
        answer: str,
        contexts: List[Dict]
    ) -> List[str]:
        """检查不在源中的陈述"""
        statements = re.split(r'[。！？.!?]', answer)
        unsupported = []

        for stmt in statements:
            stmt = stmt.strip()
            if len(stmt) < 5:
                continue

            # 检查是否在上下文中
            found = False
            for ctx in contexts:
                text = ctx.get("text", "")
                # 检查关键词匹配
                words = [w for w in stmt.split() if len(w) >= 2]
                if any(word in text for word in words):
                    found = True
                    break

            if not found:
                unsupported.append(stmt)

        return unsupported[:5]

    def _check_unverified_numbers(
        self,
        answer: str,
        contexts: List[Dict]
    ) -> List[str]:
        """检查未验证的数值"""
        # 提取数值
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*([%|度|分钟|小时|秒|次|个|项|条|节|章|mm|cm|m|kg|lb])', answer)

        unverified = []
        for num_str, unit in numbers:
            combined = f"{num_str}{unit}"
            found = False
            for ctx in contexts:
                if combined in ctx.get("text", "") or num_str in ctx.get("text", ""):
                    found = True
                    break

            if not found:
                unverified.append(combined)

        return unverified

    def _check_absolute_claims(
        self,
        answer: str,
        contexts: List[Dict]
    ) -> List[str]:
        """检查绝对性断言"""
        risky_claims = []

        # 检测"是...的"模式
        is_patterns = re.findall(r'是\s*([^\u3000-\u303f，。]{2,10})\s*的', answer)

        for claim in is_patterns:
            # 检查是否有支持
            has_support = any(
                claim in ctx.get("text", "") or claim in ctx.get("metadata", {}).get("title", "")
                for ctx in contexts
            )
            if not has_support:
                risky_claims.append(f"是{claim}的")

        return risky_claims[:5]

    def _check_unknown_terms(self, answer: str) -> List[str]:
        """检查未知术语"""
        # 提取可能的专业术语
        terms = re.findall(r'[\u4e00-\u9fff]{3,8}|[A-Z]{2,6}', answer)

        # 简单过滤 - 长串中文可能是专业术语
        unknown = [t for t in terms if len(t) >= 4]

        return unknown[:5]

    def _check_missing_citations(
        self,
        answer: str,
        contexts: List[Dict]
    ) -> bool:
        """检查是否缺少引用"""
        # 如果答案较长但没有引用标记
        if len(answer) > 100:
            has_citation = bool(re.search(r'§|第\s*\d+\s*条|参考文献|来源|CCAR|FAR|CS-', answer))
            return not has_citation
        return False

    def reduce_hallucination(
        self,
        answer: str,
        contexts: List[Dict],
        query: str = ""
    ) -> Tuple[str, Dict[str, Any]]:
        """
        降低幻觉风险

        返回: (优化后的答案, 修改信息)
        """
        modifications = {
            "added_uncertainty_markers": [],
            "added_citations": [],
            "softened_claims": [],
            "removed_unverified": []
        }

        enhanced_answer = answer

        # 1. 分析风险
        risk_score, risk_items = self.analyze_hallucination_risk(answer, contexts, query)

        # 如果风险已经很低，直接返回
        if risk_score < 0.1:
            return answer, {"risk_score": risk_score, "modifications": modifications}

        # 2. 添加不确定性标记
        enhanced_answer = self._add_uncertainty_markers(
            enhanced_answer, risk_items, modifications
        )

        # 3. 添加引用
        enhanced_answer = self._add_citations(
            enhanced_answer, contexts, modifications
        )

        # 4. 软化绝对性断言
        enhanced_answer = self._soften_absolute_claims(
            enhanced_answer, modifications
        )

        # 5. 移除无法验证的内容
        enhanced_answer = self._remove_unverified_content(
            enhanced_answer, risk_items, modifications
        )

        # 6. 清理格式
        enhanced_answer = self._clean_format(enhanced_answer)

        return enhanced_answer, {
            "original_risk": risk_score,
            "modifications": modifications
        }

    def _add_uncertainty_markers(
        self,
        answer: str,
        risk_items: List[Dict],
        modifications: Dict
    ) -> str:
        """添加不确定性标记"""
        modified = answer

        # 检查是否需要添加
        needs_marker = any(
            item["type"] in ["source_outside", "absolute_claims", "missing_citations"]
            for item in risk_items
        )

        if needs_marker and "根据" not in modified:
            # 在开头添加
            marker = self.UNCERTAINTY_PHRASES[0]
            modified = f"{marker}，{modified[:1].lower()}{modified[1:]}"
            modifications["added_uncertainty_markers"].append(marker)

        return modified

    def _add_citations(
        self,
        answer: str,
        contexts: List[Dict],
        modifications: Dict
    ) -> str:
        """添加引用"""
        if not contexts:
            return answer

        # 检查是否已有引用
        if "§" in answer or "参考文献" in answer:
            return answer

        # 从上下文中提取引用
        citations = []
        for ctx in contexts[:3]:
            metadata = ctx.get("metadata", {})
            source = metadata.get("source", "").replace(".md", "")
            section = metadata.get("section", "")
            if section:
                citations.append(f"{source}:{section}")

        if citations:
            citation_str = f" (参考文献: {', '.join(citations[:2])})"
            modified = answer.rstrip("。") + citation_str + "。"
            modifications["added_citations"] = citations
            return modified

        return answer

    def _soften_absolute_claims(
        self,
        answer: str,
        modifications: Dict
    ) -> str:
        """软化绝对性断言"""
        modified = answer

        # 替换模式
        softening_rules = [
            (r'是\s*([^\u3000-\u303f，。]{2,10})\s*的', r'通常是\1的'),
            (r'(必须|应当)\s*([^\u3000-\u303f，。]{2,15})', r'一般\2'),
        ]

        for pattern, replacement in softening_rules:
            matches = re.findall(pattern, modified)
            if matches:
                modified = re.sub(pattern, replacement, modified, count=1)
                modifications["softened_claims"].extend([str(m) for m in matches[:1]])

        return modified

    def _remove_unverified_content(
        self,
        answer: str,
        risk_items: List[Dict],
        modifications: Dict
    ) -> str:
        """移除无法验证的内容"""
        modified = answer

        # 移除明显未验证的数值陈述
        for item in risk_items:
            if item["type"] == "unverified_numbers":
                for value in item.get("values", []):
                    # 移除包含该数值的句子
                    modified = re.sub(r'[^。]*' + re.escape(value) + r'[^。]*。', '', modified)
                    modifications["removed_unverified"].append(value)

        return modified

    def _clean_format(self, answer: str) -> str:
        """清理格式"""
        # 清理多余空格和空行
        cleaned = re.sub(r'\s+', ' ', answer)
        cleaned = re.sub(r'\s+。', '。', cleaned)

        # 确保结尾有标点
        if cleaned and cleaned[-1] not in '。！？.!?':
            cleaned += '。'

        return cleaned.strip()


__all__ = ['HallucinationReducer']
