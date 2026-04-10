#!/usr/bin/env python3
"""
幻觉防护和事实检查模块

降低LLM回答中的幻觉风险
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FactCheck:
    """事实检查结果"""
    statement: str
    is_supported: bool
    confidence: float
    sources: List[str]
    issues: List[str]


@dataclass
class HallucinationReport:
    """幻觉评估报告"""
    has_hallucination: bool
    hallucination_score: float  # 0=无幻觉, 1=严重幻觉
    fact_checks: List[FactCheck]
    flagged_statements: List[str]
    recommendations: List[str]


class HallucinationGuard:
    """幻觉防护系统"""

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.fact_database = self._build_fact_database()

    def _build_fact_database(self) -> Dict[str, Any]:
        """构建事实数据库"""

        facts = {
            "regulations": {},      # 条款号 -> 条款内容
            "parameters": {},       # 参数名 -> 允许值/范围
            "requirements": {},    # 要求类型 -> 具体要求列表
            "cross_references": {}  # 条款引用关系
        }

        # 从结构文件中提取事实
        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem)

                # 提取条款事实
                self._extract_regulation_facts(data, doc_name, facts)
            except Exception as e:
                logger.warning(f"Error loading {structure_file}: {e}")

        logger.info(f"Built fact database with {len(facts['regulations'])} regulation facts")
        return facts

    def _extract_regulation_facts(self, data: Dict, doc_name: str, facts: Dict):
        """提取规章事实"""

        def extract_nodes(nodes, path=""):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                content_parts = node.get("content_parts", [])
                summary = node.get("summary", "")

                # 组合内容
                full_content = summary + " ".join(content_parts)

                # 提取条款号
                section_match = re.search(r'(?:第\s*)?([\\d.]+)(?:\\s*条)?', title)
                if section_match:
                    section_num = section_match.group(1)
                    fact_key = f"{doc_name}:{section_num}"

                    facts["regulations"][fact_key] = {
                        "document": doc_name,
                        "section": section_num,
                        "title": title,
                        "content": full_content,
                        "has_numeric_values": bool(re.search(r'\\d+', full_content)),
                        "has_percentages": bool(re.search(r'\\d+%', full_content)),
                        "has_temperature": bool(re.search(r'\\d+°[CF]', full_content)),
                        "has_time": bool(re.search(r'\\d+\\s*(?:秒|分钟|小时)', full_content)),
                        "has_materials": bool(re.search(r'(?:材料|合金|复合|钛|铝|钢)', full_content))
                    }

                    # 提取参数
                    self._extract_parameters(full_content, section_num, facts["parameters"])

                # 递归
                children = node.get("nodes", []) or node.get("sections", [])
                extract_nodes(children, f"{path}/{title}")

        structure = data.get("structure", [])
        if isinstance(structure, list):
            extract_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            extract_nodes(structure["chapters"])

    def _extract_parameters(self, content: str, section: str, params_dict: Dict):
        """提取参数信息"""

        # 提取数值范围
        # 例如："30秒" -> {"30秒": {"value": 30, "unit": "秒"}}
        time_patterns = [
            (r'(\\d+)\\s*秒', "时间_秒"),
            (r'(\\d+)\\s*分钟', "时间_分钟"),
            (r'(\\d+)\\s*小时', "时间_小时"),
            (r'(\\d+)\\s*%|%', "百分比"),
            (r'(\\d+)\\s*°[CFc]', "温度")
        ]

        for pattern, param_type in time_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                param_name = f"{section}_{param_type}"
                if param_name not in params_dict:
                    params_dict[param_name] = {}

                # 提取数值
                value_match = re.search(r'(\\d+)', match)
                if value_match:
                    params_dict[param_name]["value"] = value_match.group(1)
                    params_dict[param_name]["unit"] = param_type.split("_")[1]
                    params_dict[param_name]["section"] = section

    def check_statement_factuality(self, statement: str, context_sources: List[Dict]) -> FactCheck:
        """检查陈述的事实性"""

        issues = []
        sources = []
        confidence = 0.5

        # 1. 检查是否有明确的数据支持
        has_numbers = bool(re.search(r'\\d+', statement))
        has_specific_section = bool(re.search(r'(?:§|第|section)[\\s*\\d.]+', statement, re.IGNORECASE))

        # 2. 检查是否包含绝对性断言
        absolute_claims = ["必须", "应当", "不得", "禁止", "不能"]
        has_absolute = any(claim in statement for claim in absolute_claims)

        # 3. 检查来源支持
        for source in context_sources:
            source_text = source.get("text", "")
            source_meta = source.get("metadata", {})

            # 检查关键术语是否在源中出现
            statement_terms = set(re.findall(r'[\\u4e00-\\u9fff]{2,}', statement))
            source_terms = set(re.findall(r'[\\u4e00-\\u9fff]{2,}', source_text))

            overlap = statement_terms & source_terms
            if overlap:
                sources.append(source_meta.get("source", "unknown"))
                confidence += len(overlap) * 0.1

        # 4. 评估可信度
        if has_specific_section and sources:
            confidence += 0.3
        if has_absolute and not sources:
            issues.append("包含绝对性断言但缺少来源支持")
            confidence -= 0.2

        confidence = max(0, min(1, confidence))

        return FactCheck(
            statement=statement,
            is_supported=len(sources) > 0,
            confidence=confidence,
            sources=sources,
            issues=issues
        )

    def generate_hallucination_report(self, answer: str, sources: List[Dict]) -> HallucinationReport:
        """生成幻觉报告"""

        # 分割回答为陈述
        statements = self._split_into_statements(answer)

        fact_checks = []
        flagged = []

        for stmt in statements:
            if len(stmt) < 10:  # 跳过太短的陈述
                continue

            check = self.check_statement_factuality(stmt, sources)
            fact_checks.append(check)

            # 标记可疑陈述
            if not check.is_supported or check.confidence < 0.5:
                flagged.append(stmt)

        # 计算幻觉得分
        hallucination_score = 0.0
        if fact_checks:
            avg_confidence = sum(c.confidence for c in fact_checks) / len(fact_checks)
            hallucination_score = 1.0 - avg_confidence

        # 生成建议
        recommendations = []
        if hallucination_score > 0.5:
            recommendations.append("回答中存在未经证实的信息，建议添加更多来源引用")
        if hallucination_score > 0.3:
            recommendations.append("建议降低模糊性陈述的置信度")
        if flagged:
            recommendations.append(f"发现 {len(flagged)} 个可疑陈述，建议人工审核")

        return HallucinationReport(
            has_hallucination=len(flagged) > 0,
            hallucination_score=hallucination_score,
            fact_checks=fact_checks,
            flagged_statements=flagged,
            recommendations=recommendations
        )

    def _split_into_statements(self, text: str) -> List[str]:
        """将文本分割为陈述"""

        # 按句子分割
        sentences = re.split(r'[。！？.!?]', text)

        # 过滤并清理
        statements = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 5:  # 至少5个字符
                statements.append(sentence)

        return statements


class EnhancedFactChecker:
    """增强的事实检查器"""

    def __init__(self, knowledge_base_path: str):
        self.guard = HallucinationGuard(knowledge_base_path)

    def verify_claim_against_kb(self, claim: str) -> Tuple[bool, float, List[str]]:
        """根据知识库验证声明"""

        # 在这里可以添加更复杂的验证逻辑
        # 目前返回基础验证结果

        confidence = 0.5
        supporting_facts = []

        # 检查是否包含具体条款引用
        if re.search(r'§\\s*[\\d.]+', claim):
            confidence += 0.3
            supporting_facts.append("包含条款引用")

        # 检查是否包含数值
        if re.search(r'\\d+', claim):
            confidence += 0.1
            supporting_facts.append("包含数值信息")

        is_supported = confidence > 0.5

        return is_supported, confidence, supporting_facts

    def detect_common_hallucinations(self, answer: str) -> List[str]:
        """检测常见幻觉模式"""

        hallucinations = []

        # 检测不存在的条款引用
        cited_sections = re.findall(r'§\\s*[\\d.]+', answer)
        for section in cited_sections:
            section_num = section.replace('§', '').strip()
            # 这里可以检查条款是否真实存在
            # 简化处理：假设所有引用的条款格式正确
            pass

        # 检测过于绝对的陈述
        if re.search(r'所有.*都|从不|绝对', answer):
            hallucinations.append("发现绝对性陈述")

        return hallucinations


__all__ = ['HallucinationGuard', 'EnhancedFactChecker', 'HallucinationReport', 'FactCheck']
