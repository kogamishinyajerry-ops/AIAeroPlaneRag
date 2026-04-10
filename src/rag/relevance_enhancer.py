#!/usr/bin/env python3
"""
查询相关性提升模块

通过增强检索算法和重排序策略提升查询相关性
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryRelevanceEnhancer:
    """查询相关性增强器"""

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.query_history = []
        self.feedback_data = {}

        # 加载统计信息用于重排序
        self.term_statistics = self._build_term_statistics()
        self.section_statistics = self._build_section_statistics()

    def _build_term_statistics(self) -> Dict[str, Dict]:
        """构建术语统计"""

        stats = {}

        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem)

                # 统计术语出现频率
                self._count_terms_in_structure(data, doc_name, stats)
            except Exception as e:
                logger.warning(f"Error processing {structure_file}: {e}")

        return stats

    def _count_terms_in_structure(self, data: Dict, doc_name: str, stats: Dict):
        """统计结构中的术语"""

        def count_nodes(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                # 从标题和内容中提取术语
                title = node.get("title", "")
                summary = node.get("summary", "")
                content_parts = node.get("content_parts", [])

                text = title + " " + summary + " " + " ".join(content_parts)

                # 统计中文术语
                terms = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
                for term in terms:
                    if term not in stats:
                        stats[term] = {"count": 0, "documents": {}, "sections": []}

                    stats[term]["count"] += 1

                    if doc_name not in stats[term]["documents"]:
                        stats[term]["documents"][doc_name] = 0
                    stats[term]["documents"][doc_name] += 1

                    # 记录出现的条款
                    section_match = re.search(r'(?:第\\s*)?([\\d.]+)', title)
                    if section_match:
                        section = f"{doc_name}:{section_match.group(1)}"
                        if section not in stats[term]["sections"]:
                            stats[term]["sections"].append(section)

                # 递归
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    count_nodes(children)

        structure = data.get("structure", [])
        if isinstance(structure, list):
            count_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            count_nodes(structure["chapters"])

    def _build_section_statistics(self) -> Dict[str, Dict]:
        """构建条款统计"""

        stats = {}

        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem)

                # 统计条款信息
                self._analyze_sections(data, doc_name, stats)
            except Exception as e:
                logger.warning(f"Error analyzing {structure_file}: {e}")

        return stats

    def _analyze_sections(self, data: Dict, doc_name: str, stats: Dict):
        """分析条款"""

        def analyze_nodes(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                content_parts = node.get("content_parts", [])
                summary = node.get("summary", "")
                page = node.get("start_index", 0)

                # 提取条款号
                section_match = re.search(r'(?:第\\s*)?([\\d.]+)', title)
                if section_match:
                    section = f"{doc_name}:{section_match.group(1)}"

                    stats[section] = {
                        "document": doc_name,
                        "title": title,
                        "page": page,
                        "content_length": len(summary) + sum(len(p) for p in content_parts),
                        "has_requirements": self._has_requirements(summary + " ".join(content_parts)),
                        "keywords": self._extract_keywords(title + summary + " ".join(content_parts))
                    }

                # 递归
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    analyze_nodes(children)

        structure = data.get("structure", [])
        if isinstance(structure, list):
            analyze_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            analyze_nodes(structure["chapters"])

    def _has_requirements(self, text: str) -> bool:
        """检查是否包含要求"""
        return any(kw in text for kw in ["必须", "应当", "要求", "不得", "shall", "must"])

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []

        # 专业术语
        professional_terms = [
            "防火", "强度", "疲劳", "载荷", "振动", "噪音", "排放",
            "试验", "验证", "认证", "审定", "适航",
            "发动机", "机翼", "机身", "起落架", "襟翼", "副翼",
            "APU", "OEI", "ETOPS"
        ]

        for term in professional_terms:
            if term in text:
                keywords.append(term)

        return keywords

    def enhance_search_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """增强搜索结果的相关性"""

        if not results:
            return results

        # 1. 提取查询关键词
        query_terms = self._extract_query_terms(query)

        # 2. 计算每个结果的增强相关性得分
        enhanced_results = []
        for result in results:
            enhanced_result = result.copy()
            metadata = enhanced_result.get("metadata", {})

            # 原始得分
            original_score = metadata.get("score", 0)

            # 计算增强得分
            enhanced_score = self._calculate_enhanced_score(
                result, query, query_terms, results
            )

            metadata["enhanced_score"] = enhanced_score
            metadata["score_breakdown"] = self._get_score_breakdown(
                result, query, query_terms
            )

            # 按增强得分重排序
            enhanced_results.append((enhanced_score, enhanced_result))

        # 排序
        enhanced_results.sort(key=lambda x: x[0], reverse=True)

        # 返回重排序后的结果
        return [result for score, result in enhanced_results]

    def _extract_query_terms(self, query: str) -> Dict[str, List[str]]:
        """提取查询术语"""

        terms = {
            "ccar_refs": [],    # CCAR引用 (CCAR-33, CCAR-25)
            "section_nums": [], # 条款号 (33.1, 25.1)
            "chinese_terms": [], # 中文术语
            "english_terms": [] # 英文术语
        }

        # CCAR 引用
        ccar_matches = re.findall(r'CCAR[-\\s]*\\d+', query, re.IGNORECASE)
        terms["ccar_refs"] = [m.upper().replace(" ", "") for m in ccar_matches]

        # 条款号
        section_matches = re.findall(r'(?:§|第|section)[\\s]*([\\d.]+)', query, re.IGNORECASE)
        terms["section_nums"] = [m.group(1) for m in section_matches]

        # 中文术语
        chinese_terms = re.findall(r'[\\u4e00-\\u9fff]{2,4}', query)
        # 过滤常见词
        stopwords = {"什么", "哪些", "如何", "是否", "要求", "规定", "关于", "以及"}
        terms["chinese_terms"] = [t for t in chinese_terms if t not in stopwords]

        # 英文术语
        english_terms = re.findall(r'[a-zA-Z]{2,}', query)
        terms["english_terms"] = [t for t in english_terms if len(t) >= 2]

        return terms

    def _calculate_enhanced_score(
        self,
        result: Dict,
        query: str,
        query_terms: Dict,
        all_results: List[Dict]
    ) -> float:
        """计算增强相关性得分"""

        base_score = result.get("metadata", {}).get("score", 0)
        text = result.get("text", "")
        metadata = result.get("metadata", {})

        # 防御性检查
        if not query_terms or not isinstance(query_terms, dict):
            query_terms = {
                "ccar_refs": [],
                "section_nums": [],
                "chinese_terms": [],
                "english_terms": []
            }

        # 确保所有键都有列表值
        for key in ["ccar_refs", "section_nums", "chinese_terms", "english_terms"]:
            if key not in query_terms or query_terms[key] is None:
                query_terms[key] = []

        enhancement = 0

        # 1. 关键词匹配度 (30%)
        keyword_match_score = self._calculate_keyword_match(text, query_terms)
        enhancement += keyword_match_score * 30

        # 2. 位置权重 (20%)
        # 标题匹配权重更高
        title = metadata.get("title") or ""
        chinese_terms = query_terms.get("chinese_terms") or []
        english_terms = query_terms.get("english_terms") or []

        if chinese_terms and any(term in title for term in chinese_terms):
            enhancement += 20
        elif english_terms and any(term in title for term in english_terms):
            enhancement += 15

        # 3. 内容丰富度 (20%)
        content_length = len(text or "")
        if content_length > 200:
            enhancement += 20
        elif content_length > 100:
            enhancement += 10

        # 4. 结果多样性 (15%)
        # 惩罚重复结果
        doc_source = metadata.get("source", "")
        same_doc_count = sum(1 for r in all_results if r.get("metadata", {}).get("source") == doc_source)
        if same_doc_count > 1:
            enhancement -= 15 * (same_doc_count - 1) / len(all_results)

        # 5. 要求性匹配 (15%)
        if ("要求" in query) or (chinese_terms and "要求" in chinese_terms):
            if self._has_requirements(text or ""):
                enhancement += 15

        # 合并原始得分和增强
        enhanced_score = base_score * 0.5 + enhancement * 0.5

        return min(enhanced_score, 100)

    def _calculate_keyword_match(self, text: str, query_terms: Dict) -> float:
        """计算关键词匹配度"""

        text = text or ""
        match_count = 0
        total_terms = 0

        # 统计匹配的关键词
        matched_terms = set()

        if not query_terms or not isinstance(query_terms, dict):
            return 0.0

        for term_list in query_terms.values():
            if not term_list or not isinstance(term_list, list):
                continue
            for term in term_list:
                if not term or not isinstance(term, str):
                    continue
                total_terms += 1
                if term.lower() in text.lower():
                    matched_terms.add(term)

        # 计算匹配比例
        if total_terms > 0:
            return len(matched_terms) / total_terms

        return 0

    def _get_score_breakdown(self, result: Dict, query: str, query_terms: Dict) -> Dict:
        """获取得分分解"""

        metadata = result.get("metadata", {})
        text = result.get("text", "")
        title = metadata.get("title") or ""

        # 防御性检查
        if not query_terms or not isinstance(query_terms, dict):
            query_terms = {
                "ccar_refs": [],
                "section_nums": [],
                "chinese_terms": [],
                "english_terms": []
            }

        # 确保所有键都有列表值
        for key in ["ccar_refs", "section_nums", "chinese_terms", "english_terms"]:
            if key not in query_terms or query_terms[key] is None:
                query_terms[key] = []

        breakdown = {
            "keyword_match": 0.0,
            "title_match": 0.0,
            "content_richness": 0.0,
            "diversity": 0.0
        }

        # 关键词匹配
        breakdown["keyword_match"] = self._calculate_keyword_match(text, query_terms)

        # 标题匹配
        chinese_terms = query_terms.get("chinese_terms") or []
        english_terms = query_terms.get("english_terms") or []

        if chinese_terms and any(term in title for term in chinese_terms):
            breakdown["title_match"] = 1.0
        elif english_terms and any(term in title for term in english_terms):
            breakdown["title_match"] = 0.7

        # 内容丰富度
        content_length = len(text or "")
        breakdown["content_richness"] = min(content_length / 200, 1.0)

        # 多样性已在主函数中处理

        return breakdown

    def learn_from_feedback(self, query: str, results: List[Dict], feedback: Dict):
        """从反馈中学习"""

        query_signature = self._generate_query_signature(query)

        self.feedback_data[query_signature] = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results_count": len(results),
            "feedback": feedback,
            "used_for_learning": False
        }

        logger.info(f"Recorded feedback for query: {query[:50]}...")

    def _generate_query_signature(self, query: str) -> str:
        """生成查询签名（用于识别相似查询）"""

        # 标准化查询
        normalized = query.lower().strip()
        # 移除标点
        normalized = re.sub(r'[，。！？、,.?!]', '', normalized)
        # 移除空格
        normalized = normalized.replace(' ', '')

        return normalized


class ReRanker:
    """结果重排序器"""

    def __init__(self, knowledge_base_path: str):
        self.kb_path = Path(knowledge_base_path)
        self.enhancer = QueryRelevanceEnhancer(knowledge_base_path)

    def rerank(self, query: str, results: List[Dict], top_k: int = None) -> List[Dict]:
        """重新排序搜索结果"""

        if not results:
            return results

        # 使用增强器重新排序
        enhanced = self.enhancer.enhance_search_results(query, results)

        # 限制返回数量
        if top_k:
            enhanced = enhanced[:top_k]

        return enhanced

    def merge_and_rerank(self, result_sets: List[List[Dict]], query: str, top_k: int = 10) -> List[Dict]:
        """合并多个结果集并重排序"""

        # 收集所有结果
        all_results = []
        seen = set()

        for results in result_sets:
            for result in results:
                # 去重（基于标题或内容）
                identifier = result.get("metadata", {}).get("title", "")
                if identifier and identifier not in seen:
                    seen.add(identifier)
                    all_results.append(result)

        # 重排序
        reranked = self.enhancer.enhance_search_results(query, all_results)

        return reranked[:top_k]


__all__ = ['QueryRelevanceEnhancer', 'ReRanker']
