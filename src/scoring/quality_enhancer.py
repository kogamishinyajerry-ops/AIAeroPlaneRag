#!/usr/bin/env python3
"""
质量评分增强模块

专注于提升三个核心指标：
1. 可信度 (Confidence) - 从54.1到70+
2. 幻觉风险 (Hallucination Risk) - 从0.24到0.1以下
3. 可用性 (Usability) - 从48.3到70+
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict, Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityScoringEngine:
    """
    质量评分引擎

    计算和优化三个核心指标
    """

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)

        # 加载知识图谱
        self.graph_nodes, self.graph_edges = self._load_knowledge_graph()

        # 加载术语库
        self.terminology = self._load_terminology()
        self.abbreviations = self._load_abbreviations()

        # 加载等效条款映射
        self.equivalent_clauses = self._load_equivalent_clauses()

        # 加载验证规则
        self.verification_rules = self._load_verification_rules()

    def _load_knowledge_graph(self) -> tuple[dict, list]:
        """加载知识图谱"""
        graph_file = self.kb_path / "knowledge_graph" / "graph.json"
        try:
            if graph_file.exists():
                with open(graph_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("nodes", {}), data.get("edges", [])
        except Exception as e:
            logger.warning(f"加载知识图谱失败: {e}")
        return {}, []

    def _load_terminology(self) -> dict:
        """加载术语库"""
        term_file = self.kb_path / "terminology" / "comprehensive_terms.json"
        try:
            if term_file.exists():
                with open(term_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("terms", {})
        except Exception as e:
            logger.warning(f"加载术语库失败: {e}")
        return {}

    def _load_abbreviations(self) -> dict:
        """加载缩写映射"""
        abbr_file = self.kb_path / "terminology" / "abbreviations.json"
        try:
            if abbr_file.exists():
                with open(abbr_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载缩写映射失败: {e}")
        return {}

    def _load_equivalent_clauses(self) -> dict:
        """加载等效条款映射"""
        cross_links_file = self.kb_path / "knowledge_links" / "cross_document_links.json"
        try:
            if cross_links_file.exists():
                with open(cross_links_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    equivalent = data.get("equivalent_links", [])
                    # 构建快速查找映射
                    mapping = defaultdict(list)
                    for link in equivalent:
                        if "clauses" in link:
                            clauses = link["clauses"]
                            for i, clause in enumerate(clauses):
                                for other in clauses[i+1:]:
                                    mapping[clause].append(other)
                    return dict(mapping)
        except Exception as e:
            logger.warning(f"加载等效条款失败: {e}")
        return {}

    def _load_verification_rules(self) -> dict:
        """加载验证规则"""
        rules_file = self.kb_path / "verification" / "fact_check_rules.json"
        try:
            if rules_file.exists():
                with open(rules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载验证规则失败: {e}")
        return {}

    def calculate_confidence_score(
        self,
        answer: str,
        contexts: List[Dict],
        query: str = ""
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算可信度分数

        因素：
        1. 引用覆盖率 (30%) - 答案中有多少内容有引用支持
        2. 条款号精确度 (20%) - 是否有具体的条款号
        3. 等效条款支持 (15%) - 是否有跨规章等效条款支持
        4. 知识图谱关联 (15%) - 是否有图谱关联支持
        5. 术语一致性 (10%) - 术语使用是否一致
        6. 数值验证 (10%) - 数值是否在源中找到
        """
        factors = {
            "citation_coverage": 0.0,
            "clause_precision": 0.0,
            "equivalent_support": 0.0,
            "graph_support": 0.0,
            "terminology_consistency": 0.0,
            "numerical_verification": 0.0
        }

        # 1. 引用覆盖率
        if contexts:
            # 计算答案中有引用支持的内容比例
            total_chars = len(answer)
            supported_chars = 0

            for ctx in contexts:
                text = ctx.get("text", "")
                # 查找答案中与上下文匹配的内容
                for sentence in answer.split("。"):
                    if any(word in text for word in sentence.split() if len(word) >= 2):
                        supported_chars += len(sentence)
                        break

            factors["citation_coverage"] = min(supported_chars / total_chars if total_chars > 0 else 0, 1.0)

        # 2. 条款号精确度
        clause_patterns = re.findall(r'§\s*[\d.]+|第\s*[\d.]+\s*条|[\d.]+\s*条', answer)
        if contexts:
            # 检查条款号是否在上下文中
            verified_clauses = 0
            for clause in clause_patterns:
                for ctx in contexts:
                    if clause in ctx.get("text", "") or clause in ctx.get("metadata", {}).get("title", ""):
                        verified_clauses += 1
                        break
            factors["clause_precision"] = verified_clauses / len(clause_patterns) if clause_patterns else 0.5

        # 3. 等效条款支持
        if self.equivalent_clauses and clause_patterns:
            equivalent_count = 0
            for clause in clause_patterns:
                if clause in self.equivalent_clauses:
                    equivalent_count += 1
            factors["equivalent_support"] = min(equivalent_count / len(clause_patterns) if clause_patterns else 0, 1.0)

        # 4. 知识图谱关联
        if self.graph_nodes and query:
            # 查找与查询相关的图谱节点
            related_nodes = self._find_related_graph_nodes(query)
            if related_nodes:
                factors["graph_support"] = min(len(related_nodes) / 5, 1.0)  # 最多5个节点得满分

        # 5. 术语一致性
        if self.terminology:
            # 检查答案中的术语是否在术语库中
            terms_in_answer = re.findall(r'[\u4e00-\u9fff]{2,6}|[A-Z]{2,6}', answer)
            consistent_terms = 0
            for term in terms_in_answer:
                term_lower = term.lower()
                if any(term_lower in t.get("text", "").lower() for t in self.terminology.values()):
                    consistent_terms += 1
            factors["terminology_consistency"] = consistent_terms / len(terms_in_answer) if terms_in_answer else 0.5

        # 6. 数值验证
        numbers = re.findall(r'\d+(?:\.\d+)?', answer)
        if numbers and contexts:
            verified_numbers = 0
            for num in numbers:
                for ctx in contexts:
                    if num in ctx.get("text", ""):
                        verified_numbers += 1
                        break
            factors["numerical_verification"] = verified_numbers / len(numbers) if numbers else 0.5

        # 计算加权总分
        weights = {
            "citation_coverage": 0.30,
            "clause_precision": 0.20,
            "equivalent_support": 0.15,
            "graph_support": 0.15,
            "terminology_consistency": 0.10,
            "numerical_verification": 0.10
        }

        confidence = sum(factors[k] * weights[k] for k in factors)

        return confidence, {
            "confidence": confidence,
            "factors": factors,
            "level": self._get_confidence_level(confidence)
        }

    def _get_confidence_level(self, score: float) -> str:
        """获取置信度等级"""
        if score >= 0.8:
            return "HIGH"
        elif score >= 0.6:
            return "MEDIUM"
        elif score >= 0.4:
            return "LOW"
        else:
            return "VERY_LOW"

    def calculate_hallucination_risk(
        self,
        answer: str,
        contexts: List[Dict],
        query: str = ""
    ) -> Tuple[float, List[str]]:
        """
        计算幻觉风险分数

        因素：
        1. 源外陈述 (40%) - 答案中不在源中的陈述
        2. 绝对性断言 (20%) - 没有"必须/应当"支持的"是/有"陈述
        3. 未知术语 (15%) - 答案中不在术语库中的专业术语
        4. 数值不匹配 (15%) - 答案中的数值与源不一致
        5. 不确定性标记 (10%) - 缺少不确定性标记的推测性陈述
        """
        risk_score = 0.0
        flagged_statements = []

        # 1. 检查源外陈述
        statements = re.split(r'[。！？.!?]', answer)
        unsupported = []

        for stmt in statements:
            stmt = stmt.strip()
            if len(stmt) < 5:
                continue

            # 检查是否在上下文中
            found = False
            for ctx in contexts:
                if any(word in ctx.get("text", "") for word in stmt.split() if len(word) >= 2):
                    found = True
                    break

            if not found:
                unsupported.append(stmt)

        if statements:
            source_outside_ratio = len(unsupported) / len([s for s in statements if len(s.strip()) >= 5])
            risk_score += source_outside_ratio * 0.4
            flagged_statements.extend(unsupported[:3])

        # 2. 检查绝对性断言
        absolute_patterns = [
            r'是.*的(?!必须|应当|要求)',
            r'有.*的(?!必须|应当|要求)',
            r'为.*的(?!必须|应当|要求)'
        ]

        for pattern in absolute_patterns:
            matches = re.findall(pattern, answer)
            if matches:
                # 检查是否有条款支持
                for match in matches:
                    has_support = any("必须" in c.get("text", "") or "应当" in c.get("text", "")
                                    for c in contexts)
                    if not has_support:
                        risk_score += 0.05
                        if len(flagged_statements) < 5:
                            flagged_statements.append(f"绝对性断言: {match}")

        # 3. 检查未知术语
        if self.terminology:
            terms_in_answer = re.findall(r'[\u4e00-\u9fff]{2,6}|[A-Z]{2,6}', answer)
            unknown_terms = []
            for term in terms_in_answer:
                term_lower = term.lower()
                if not any(term_lower in t.get("text", "").lower() for t in self.terminology.values()):
                    if term not in unknown_terms:
                        unknown_terms.append(term)

            if terms_in_answer:
                unknown_ratio = len(unknown_terms) / len(terms_in_answer)
                risk_score += unknown_ratio * 0.15
                if unknown_terms and len(flagged_statements) < 5:
                    flagged_statements.append(f"未知术语: {', '.join(unknown_terms[:3])}")

        # 4. 检查数值不匹配
        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*(?:%|分钟|小时|度)', answer)
        mismatched = []
        for num_str in numbers:
            found = False
            for ctx in contexts:
                if num_str in ctx.get("text", ""):
                    found = True
                    break
            if not found:
                mismatched.append(num_str)

        if numbers:
            mismatch_ratio = len(mismatched) / len(numbers)
            risk_score += mismatch_ratio * 0.15
            if mismatched and len(flagged_statements) < 5:
                flagged_statements.append(f"未验证数值: {', '.join(mismatched[:3])}")

        # 5. 检查不确定性标记
        uncertain_keywords = ["可能", "或许", "大约", "估计", "推测", "maybe", "possibly"]
        has_uncertain = any(kw in answer.lower() for kw in uncertain_keywords)

        # 如果有推测性陈述但没有不确定性标记
        speculative_patterns = ["应该", "可能", "估计"]
        has_speculative = any(p in answer for p in speculative_patterns)

        if has_speculative and not has_uncertain:
            risk_score += 0.1
            if len(flagged_statements) < 5:
                flagged_statements.append("缺少不确定性标记")

        return min(risk_score, 1.0), flagged_statements

    def calculate_usability_score(
        self,
        contexts: List[Dict],
        graph_data: Optional[Dict] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算可用性分数

        因素：
        1. 元数据完整性 (30%) - 引用是否包含完整元数据
        2. 引用片段长度 (25%) - 引用片段是否足够长（500+字符）
        3. 可视化支持 (20%) - 是否有图表、层级等可视化数据
        4. 相关条款链接 (15%) - 是否提供相关条款链接
        5. 术语解释 (10%) - 是否提供术语解释
        """
        factors = {
            "metadata_completeness": 0.0,
            "citation_length": 0.0,
            "visualization_support": 0.0,
            "related_links": 0.0,
            "terminology_help": 0.0
        }

        if not contexts:
            return 0.0, {"factors": factors, "score": 0.0}

        # 1. 元数据完整性
        required_fields = ["source", "section", "title"]
        complete_count = 0
        total_fields = 0

        for ctx in contexts:
            metadata = ctx.get("metadata", {})
            for field in required_fields:
                total_fields += 1
                if metadata.get(field):
                    complete_count += 1

        factors["metadata_completeness"] = complete_count / total_fields if total_fields > 0 else 0

        # 2. 引用片段长度
        total_length = sum(len(ctx.get("text", "")) for ctx in contexts)
        avg_length = total_length / len(contexts) if contexts else 0
        # 目标500字符，超过500得满分
        factors["citation_length"] = min(avg_length / 500, 1.0)

        # 3. 可视化支持
        if graph_data:
            if graph_data.get("nodes") or graph_data.get("edges"):
                factors["visualization_support"] = 1.0
        # 检查可视化文件
        viz_files = [
            self.kb_path / "visualizations" / "hierarchy.json",
            self.kb_path / "knowledge_graph" / "graph.json"
        ]
        if any(f.exists() for f in viz_files):
            factors["visualization_support"] = max(factors["visualization_support"], 0.5)

        # 4. 相关条款链接
        if self.equivalent_clauses:
            factors["related_links"] = 1.0
        # 检查知识链接
        links_file = self.kb_path / "knowledge_links" / "cross_document_links.json"
        if links_file.exists():
            factors["related_links"] = max(factors["related_links"], 0.5)

        # 5. 术语解释
        if self.terminology or self.abbreviations:
            factors["terminology_help"] = 1.0

        # 计算加权总分
        weights = {
            "metadata_completeness": 0.30,
            "citation_length": 0.25,
            "visualization_support": 0.20,
            "related_links": 0.15,
            "terminology_help": 0.10
        }

        usability = sum(factors[k] * weights[k] for k in factors)

        return usability, {
            "usability": usability,
            "factors": factors,
            "level": self._get_usability_level(usability)
        }

    def _get_usability_level(self, score: float) -> str:
        """获取可用性等级"""
        if score >= 0.8:
            return "EXCELLENT"
        elif score >= 0.6:
            return "GOOD"
        elif score >= 0.4:
            return "FAIR"
        else:
            return "POOR"

    def _find_related_graph_nodes(self, query: str, limit: int = 10) -> List[Dict]:
        """查找与查询相关的图谱节点"""
        if not self.graph_nodes:
            return []

        query_lower = query.lower()
        keywords = set(query_lower.split())

        results = []
        for node_id, node in self.graph_nodes.items():
            score = 0
            label = node.get("label", "").lower()
            node_type = node.get("type", "")

            # 完全匹配
            if query_lower in label:
                score += 10

            # 关键词匹配
            for keyword in keywords:
                if len(keyword) >= 2 and keyword in label:
                    score += 3

            # 类型加分
            if node_type in ["section", "requirement", "component"]:
                score += 1

            if score > 0:
                results.append({
                    "id": node_id,
                    "label": node.get("label", ""),
                    "type": node_type,
                    "score": score
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def enhance_query_response(
        self,
        query: str,
        answer: str,
        contexts: List[Dict]
    ) -> Dict[str, Any]:
        """
        增强查询响应

        计算所有三个指标并提供改进建议
        """
        # 1. 计算可信度
        confidence, confidence_detail = self.calculate_confidence_score(answer, contexts, query)

        # 2. 计算幻觉风险
        hallucination_score, flagged = self.calculate_hallucination_risk(answer, contexts, query)

        # 3. 计算可用性
        usability, usability_detail = self.calculate_usability_score(contexts)

        # 4. 生成改进建议
        recommendations = self._generate_recommendations(
            confidence_detail,
            hallucination_score,
            usability_detail
        )

        return {
            "confidence": confidence_detail,
            "hallucination": {
                "score": hallucination_score,
                "flagged_statements": flagged
            },
            "usability": usability_detail,
            "recommendations": recommendations,
            "overall_quality": self._calculate_overall_quality(confidence, hallucination_score, usability)
        }

    def _generate_recommendations(
        self,
        confidence: Dict,
        hallucination_score: float,
        usability: Dict
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 可信度建议
        if confidence["confidence"] < 0.7:
            factors = confidence["factors"]
            if factors["citation_coverage"] < 0.5:
                recommendations.append("增加引用覆盖率 - 提供更多源文档支持")
            if factors["clause_precision"] < 0.5:
                recommendations.append("添加精确条款号 - 引用具体的条款编号")
            if factors["equivalent_support"] < 0.3:
                recommendations.append("添加等效条款 - 提供跨规章等效条款支持")

        # 幻觉风险建议
        if hallucination_score > 0.2:
            recommendations.append("降低幻觉风险 - 验证所有陈述的来源")
            recommendations.append("添加不确定性标记 - 对推测性陈述使用谨慎用语")

        # 可用性建议
        if usability["usability"] < 0.6:
            factors = usability["factors"]
            if factors["citation_length"] < 0.5:
                recommendations.append("扩展引用片段 - 提供更完整的上下文（500+字符）")
            if factors["visualization_support"] < 0.5:
                recommendations.append("添加可视化 - 提供图表和层级结构")

        return recommendations

    def _calculate_overall_quality(
        self,
        confidence: float,
        hallucination: float,
        usability: float
    ) -> Dict[str, Any]:
        """计算总体质量"""
        # 幻觉风险越低越好，所以用 (1 - hallucination)
        quality = (confidence * 0.4 + (1 - hallucination) * 0.3 + usability * 0.3) * 100

        return {
            "score": quality,
            "grade": self._get_quality_grade(quality),
            "confidence_score": confidence * 100,
            "hallucination_score": hallucination * 100,
            "usability_score": usability * 100
        }

    def _get_quality_grade(self, score: float) -> str:
        """获取质量等级"""
        if score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"


__all__ = ['QualityScoringEngine']
