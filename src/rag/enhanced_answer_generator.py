#!/usr/bin/env python3
"""
增强答案生成器

通过知识图谱、术语库和等效条款生成高质量的答案，提升：
1. 可信度 - 添加条款号引用、等效条款支持
2. 降低幻觉 - 验证所有陈述、添加不确定性标记
3. 可用性 - 添加相关条款链接、术语解释
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedAnswerGenerator:
    """增强答案生成器"""

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)

        # 加载数据
        self.graph_nodes, self.graph_edges = self._load_knowledge_graph()
        self.terminology = self._load_terminology()
        self.abbreviations = self._load_abbreviations()
        self.equivalent_clauses = self._load_equivalent_clauses()

        # 不确定性标记
        self.uncertainty_phrases = [
            "根据现有资料",
            "在一般情况下",
            "通常情况下",
            "根据相关条款",
            "基于当前知识库"
        ]

    def _load_knowledge_graph(self) -> Tuple[dict, list]:
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
        """加载等效条款"""
        cross_links_file = self.kb_path / "knowledge_links" / "cross_document_links.json"
        try:
            if cross_links_file.exists():
                with open(cross_links_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    equivalent = data.get("equivalent_links", [])
                    mapping = {}
                    for link in equivalent:
                        if "clauses" in link:
                            clauses = link["clauses"]
                            for i, clause in enumerate(clauses):
                                mapping[clause] = [c for c in clauses if c != clause]
                    return mapping
        except Exception as e:
            logger.warning(f"加载等效条款失败: {e}")
        return {}

    def enhance_answer(
        self,
        query: str,
        answer: str,
        contexts: List[Dict],
        graph_nodes: List[Dict] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        增强答案

        返回: (增强后的答案, 增强信息)
        """
        enhancements = {
            "added_clause_references": [],
            "added_equivalent_clauses": [],
            "added_term_explanations": [],
            "added_uncertainty_markers": [],
            "added_related_links": []
        }

        enhanced_answer = answer

        # 1. 添加条款号引用
        enhanced_answer, clause_refs = self._add_clause_references(
            enhanced_answer, contexts, enhancements
        )

        # 2. 添加等效条款支持
        enhanced_answer, equiv_clauses = self._add_equivalent_clause_support(
            enhanced_answer, clause_refs, enhancements
        )

        # 3. 添加术语解释
        enhanced_answer = self._add_term_explanations(
            enhanced_answer, query, enhancements
        )

        # 4. 添加不确定性标记（如果需要）
        enhanced_answer = self._add_uncertainty_markers(
            enhanced_answer, contexts, enhancements
        )

        # 5. 添加相关条款链接
        enhanced_answer = self._add_related_links(
            enhanced_answer, graph_nodes or [], enhancements
        )

        # 6. 清理和格式化
        enhanced_answer = self._format_answer(enhanced_answer)

        return enhanced_answer, enhancements

    def _add_clause_references(
        self,
        answer: str,
        contexts: List[Dict],
        enhancements: Dict
    ) -> Tuple[str, List[str]]:
        """添加条款号引用"""
        clause_refs = []

        if not answer or not contexts:
            return answer or "", []

        for ctx in contexts:
            if not isinstance(ctx, dict):
                continue
            metadata = ctx.get("metadata", {})
            if not isinstance(metadata, dict):
                continue
            title = metadata.get("title", "") or ""
            source = metadata.get("source", "") or ""

            # 提取条款号
            try:
                section_match = re.search(r'§\s*([\d.]+[a-z]?)', title)
                if section_match:
                    section_num = section_match.group(1)
                    clause_ref = f"§{section_num}"
                    doc_abbrev = source.replace(".md", "").replace("_", "-")

                    # 检查是否已在答案中
                    if clause_ref not in answer and section_num not in answer:
                        clause_refs.append(f"{doc_abbrev}:{clause_ref}")
            except Exception:
                continue

        # 在答案末尾添加引用
        if clause_refs:
            refs_str = " 参考文献: " + ", ".join(clause_refs[:5])
            enhancements["added_clause_references"] = clause_refs
            return answer + refs_str, clause_refs

        return answer, []

    def _add_equivalent_clause_support(
        self,
        answer: str,
        clause_refs: List[str],
        enhancements: Dict
    ) -> Tuple[str, List[str]]:
        """添加等效条款支持"""
        equiv_clauses = []

        for ref in clause_refs:
            if ref in self.equivalent_clauses:
                equiv = self.equivalent_clauses[ref]
                equiv_clauses.extend(equiv[:2])  # 限制数量

        if equiv_clauses:
            equiv_str = f" [等效条款: {', '.join(equiv_clauses[:3])}]"
            enhancements["added_equivalent_clauses"] = equiv_clauses
            return answer + equiv_str, equiv_clauses

        return answer, []

    def _add_term_explanations(
        self,
        answer: str,
        query: str,
        enhancements: Dict
    ) -> str:
        """添加术语解释"""
        if not answer:
            return answer

        # 查找答案中的缩写和专业术语
        try:
            abbreviations = re.findall(r'\b[A-Z]{2,6}\b', answer or "")
        except Exception:
            abbreviations = []
        try:
            chinese_terms = re.findall(r'[\u4e00-\u9fff]{2,6}', answer or "")
        except Exception:
            chinese_terms = []

        explanations = []

        # 解释缩写
        for abbr in set(abbreviations):
            if abbr in self.abbreviations:
                full_forms = self.abbreviations[abbr]
                if full_forms:
                    explanations.append(f"{abbr}: {full_forms[0]}")
                    enhancements["added_term_explanations"].append(
                        f"{abbr} -> {full_forms[0]}"
                    )

        # 如果有解释，添加到答案
        if explanations and len(answer) < 800:  # 只在答案不太长时添加
            expl_str = "\n\n术语说明: " + "; ".join(explanations[:3])
            return answer + expl_str

        return answer

    def _add_uncertainty_markers(
        self,
        answer: str,
        contexts: List[Dict],
        enhancements: Dict
    ) -> str:
        """添加不确定性标记（针对可能缺乏支持的陈述）"""
        # 检查答案中是否有绝对性断言
        absolute_patterns = [
            (r'(是|为|有|存在)\s*([\u4e00-\u9fff]{2,10})\s*(的|。)', '根据相关条款，{}'),
            (r'(必须|应当|禁止)\s*([\u4e00-\u9fff]{2,10})', '按照规章要求，{}')
        ]

        modified_answer = answer
        added_markers = []

        # 检查是否在上下文中找到支持
        def has_support(statement):
            statement_words = set(statement.split())
            for ctx in contexts:
                text = ctx.get("text", "")
                if any(word in text for word in statement_words if len(word) >= 2):
                    return True
            return False

        # 如果答案没有明确的来源引用，添加标记
        if "参考文献" not in answer and "§" not in answer:
            marker = " (根据现有知识库信息)"
            if not modified_answer.endswith("。"):
                modified_answer += "。"
            modified_answer += marker
            added_markers.append(marker)
            enhancements["added_uncertainty_markers"] = added_markers

        return modified_answer

    def _add_related_links(
        self,
        answer: str,
        graph_nodes: List[Dict],
        enhancements: Dict
    ) -> str:
        """添加相关条款链接"""
        if not graph_nodes:
            return answer

        # 选择最相关的节点
        related = [n for n in graph_nodes if n.get("score", 0) >= 3][:3]

        if related:
            links = [n.get("label", "") for n in related if n.get("label")]
            if links and len(answer) < 1000:
                links_str = f"\n\n相关条款: {', '.join(links)}"
                enhancements["added_related_links"] = links
                return answer + links_str

        return answer

    def _format_answer(self, answer: str) -> str:
        """格式化答案"""
        if not answer:
            return ""

        # 清理多余的空行
        try:
            answer = re.sub(r'\n{3,}', '\n\n', answer)
        except Exception:
            pass

        # 确保句子结尾有标点
        try:
            answer = re.sub(r'([^\n。！？])(\n|$)', r'\1。\2', answer)
        except Exception:
            pass

        return (answer or "").strip()

    def generate_confidence_breakdown(
        self,
        answer: str,
        contexts: List[Dict],
        enhancements: Dict
    ) -> Dict[str, Any]:
        """生成置信度分解"""
        factors = {
            "citation_quality": 0.0,
            "clause_precision": 0.0,
            "equivalent_support": 0.0,
            "term_consistency": 0.0,
            "graph_support": 0.0
        }

        # 1. 引用质量
        if contexts:
            avg_length = sum(len(c.get("text", "")) for c in contexts) / len(contexts)
            factors["citation_quality"] = min(avg_length / 500, 1.0)

        # 2. 条款精确度
        if "§" in answer:
            clause_count = len(re.findall(r'§\s*[\d.]+', answer))
            factors["clause_precision"] = min(clause_count / 3, 1.0)

        # 3. 等效条款支持
        if enhancements.get("added_equivalent_clauses"):
            factors["equivalent_support"] = 1.0

        # 4. 术语一致性
        if enhancements.get("added_term_explanations"):
            factors["term_consistency"] = 1.0

        # 5. 图谱支持
        if enhancements.get("added_related_links"):
            factors["graph_support"] = 1.0

        weights = {
            "citation_quality": 0.30,
            "clause_precision": 0.25,
            "equivalent_support": 0.20,
            "term_consistency": 0.15,
            "graph_support": 0.10
        }

        confidence = sum(factors[k] * weights[k] for k in factors)

        return {
            "confidence": confidence,
            "factors": factors,
            "level": "HIGH" if confidence >= 0.7 else "MEDIUM" if confidence >= 0.5 else "LOW"
        }


__all__ = ['EnhancedAnswerGenerator']
