#!/usr/bin/env python3
"""
EnhancedCrossMappingAgent - 增强跨机构映射Agent

深度分析CCAR/FAA/EASA之间的对应关系:
1. 精确条款级映射
2. 差异分析
3. 等效性验证
4. 双向映射建立
5. 映射质量评估
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent.agent_base import BaseAgent, AgentTask

logger = logging.getLogger(__name__)


class EnhancedCrossMappingAgent(BaseAgent):
    """
    增强跨机构映射 Agent

    建立深度映射:
    - CCAR-25-R4 ↔ FAR-25 ↔ CS-25 (运输类飞机)
    - CCAR-33-R2 ↔ FAR-33 ↔ CS-E (发动机)
    - CCAR-29-R2 ↔ FAR-29 (旋翼机)
    - CCAR-23 ↔ FAR-23 (正常类飞机)
    """

    # 规章组配置
    REGULATION_GROUPS = {
        "25": {
            "name": "大型运输类飞机",
            "documents": ["CCAR-25-R4", "FAR-25", "CS-25"],
            "total_sections_estimated": 400
        },
        "33": {
            "name": "航空发动机",
            "documents": ["CCAR-33-R2", "FAR-33", "CS-E"],
            "total_sections_estimated": 70
        },
        "29": {
            "name": "运输类旋翼机",
            "documents": ["CCAR-29-R2", "FAR-29"],
            "total_sections_estimated": 500
        },
        "23": {
            "name": "正常类飞机",
            "documents": ["CCAR-23", "FAR-23"],
            "total_sections_estimated": 1200
        }
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("EnhancedCrossMappingAgent", knowledge_base_path)
        self.processed_dir = Path(knowledge_base_path)
        self.mappings = {}
        self.mapping_quality = {}
        self.bidirectional_mappings = defaultdict(dict)

    def get_capabilities(self) -> List[str]:
        return [
            "build_comprehensive_mappings",
            "analyze_differences",
            "verify_equivalence",
            "build_bidirectional_mappings",
            "assess_mapping_quality",
            "find_coverage_gaps",
            "export_enhanced_mappings",
            "generate_mapping_summary_report",
            "find_terminology_differences",
            "recommend_reading_order"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "build_comprehensive_mappings":
            return await self._build_comprehensive_mappings(task.params)
        elif action == "analyze_differences":
            return await self._analyze_differences(task.params)
        elif action == "verify_equivalence":
            return await self._verify_equivalence(task.params)
        elif action == "build_bidirectional_mappings":
            return await self._build_bidirectional_mappings(task.params)
        elif action == "assess_mapping_quality":
            return await self._assess_mapping_quality(task.params)
        elif action == "find_coverage_gaps":
            return await self._find_coverage_gaps(task.params)
        elif action == "export_enhanced_mappings":
            return await self._export_enhanced_mappings(task.params)
        elif action == "generate_mapping_summary_report":
            return await self._generate_mapping_summary_report(task.params)
        elif action == "find_terminology_differences":
            return await self._find_terminology_differences(task.params)
        elif action == "recommend_reading_order":
            return await self._recommend_reading_order(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _build_comprehensive_mappings(self, params: Dict) -> Dict:
        """构建全面跨机构映射"""
        all_mappings = {}
        total_mappings = 0
        coverage_stats = {}

        # 加载所有文档
        documents = {}
        for structure_file in self.processed_dir.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                doc_name = data.get("doc_name", structure_file.stem)
                documents[doc_name] = data
            except Exception as e:
                logger.warning(f"Error loading {structure_file}: {e}")

        logger.info(f"Loaded {len(documents)} documents for mapping")

        # 为每个规章组构建映射
        for group_num, group_info in self.REGULATION_GROUPS.items():
            group_docs = {k: v for k, v in documents.items()
                           if any(d in k for d in group_info["documents"])}

            if len(group_docs) < 2:
                logger.warning(f"Group {group_num}: only {len(group_docs)} docs available")
                coverage_stats[group_num] = {
                    "available": list(group_docs.keys()),
                    "missing": [d for d in group_info["documents"] if d not in group_docs]
                }
                continue

            # 提取每个文档的所有条款
            docs_sections = {}
            for doc_name, doc_data in group_docs.items():
                sections = self._extract_all_sections(doc_data, doc_name)
                docs_sections[doc_name] = sections
                logger.info(f"{doc_name}: {len(sections)} sections")

            # 基于条款号建立精确映射
            group_mappings = self._build_precise_mappings(docs_sections, group_num)
            all_mappings[group_num] = group_mappings
            total_mappings += len(group_mappings)

            # 计算覆盖率
            all_section_numbers = set()
            for sections in docs_sections.values():
                all_section_numbers.update(s.get("number", "") for s in sections)

            mapped_sections = set()
            for mapping in group_mappings:
                mapped_sections.add(mapping["section_number"])

            coverage_stats[group_num] = {
                "available": list(group_docs.keys()),
                "total_sections": len(all_section_numbers),
                "mapped_sections": len(mapped_sections),
                "coverage_rate": len(mapped_sections) / len(all_section_numbers) if all_section_numbers else 0
            }

        self.mappings = all_mappings
        self._build_bidirectional_maps()

        return {
            "improvements": [
                f"建立 {total_mappings} 个精确跨机构条款映射",
                f"覆盖 {self._count_unique_sections()} 个唯一条款号"
            ],
            "total_mappings": total_mappings,
            "coverage_stats": coverage_stats,
            "mapping_details": all_mappings
        }

    def _extract_all_sections(self, doc_data: Dict, doc_name: str) -> List[Dict]:
        """提取文档中的所有条款，包括完整信息"""
        sections = []
        doc_name = doc_data.get("doc_name", "")

        def extract_from_section_list(section_list):
            """从 sections 列表中提取（用于 FAR/CS 格式）"""
            nonlocal sections
            for section in section_list:
                if not isinstance(section, dict):
                    continue

                # 检查是否有 number 字段（FAR/CS 格式）
                if "number" in section:
                    section_num = section["number"]
                    title = section.get("title", "")
                    content_parts = []

                    if section.get("summary"):
                        content_parts.append(section["summary"])
                    if section.get("content_parts"):
                        content_parts.extend(section["content_parts"])

                    section_info = {
                        "document": doc_name,
                        "section": section_num,
                        "title": title,
                        "full_content": " ".join(content_parts),
                        "subsections": [],
                        "has_requirements": any(kw in " ".join(content_parts) for kw in
                                                   ["must", "shall", "should", "required", "必须", "应当", "要求", "不得"]),
                        "page": section.get("page", 0)
                    }
                    sections.append(section_info)

        def extract_from_nodes(nodes):
            """从 nodes 列表中提取（用于 CCAR 格式）"""
            nonlocal sections
            logger.info(f"extract_from_nodes called with {len(nodes)} nodes")
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")

                # 提取条款号 - 支持多种格式
                # 匹配 "第33.1条"、"§33.1"、"33.1" 等格式
                section_num = None

                # 尝试匹配 "第XX.X条" 格式
                match = re.search(r'第\s*([\d.]+)\s*条', title)
                if match:
                    section_num = match.group(1)
                    logger.info(f"Matched section from '第X条': {section_num}")
                else:
                    # 尝试匹配 "§XX.X" 格式
                    match = re.search(r'§\s*([\d.]+)', title)
                    if match:
                        section_num = match.group(1)
                    else:
                        # 尝试匹配纯数字格式 "XX.X" 或 "XX.X.X"
                        match = re.search(r'(\d+(?:\.\d+)+)', title)
                        if match:
                            section_num = match.group(1)

                if section_num:
                    # 构建完整内容
                    content_parts = []
                    if node.get("summary"):
                        content_parts.append(node["summary"])
                    if node.get("content_parts"):
                        content_parts.extend(node["content_parts"])

                    # 获取子条款
                    subsections = []
                    children = node.get("nodes", []) or node.get("sections", [])
                    for child in children:
                        if isinstance(child, dict):
                            child_title = child.get("title", "")
                            if re.search(rf'{section_num}\.\d+', child_title):
                                subsections.append(child_title)

                    section_info = {
                        "document": doc_name,
                        "section": section_num,
                        "title": title,
                        "full_content": " ".join(content_parts),
                        "subsections": subsections,
                        "has_requirements": any(kw in " ".join(content_parts) for kw in
                                                   ["必须", "应当", "要求", "不得", "should"]),
                        "page": node.get("page", node.get("start_index", 0))
                    }
                    sections.append(section_info)

                # 递归
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    extract_from_nodes(children)

        structure = doc_data.get("structure", {})
        logger.info(f"_extract_all_sections for {doc_name}: structure type={type(structure)}")

        # 处理 FAR/CS 格式（chapters -> sections）
        if isinstance(structure, dict) and "chapters" in structure:
            for chapter in structure["chapters"]:
                if isinstance(chapter, dict):
                    if "sections" in chapter:
                        extract_from_section_list(chapter["sections"])
                    # 也处理 nodes（有些格式混合使用）
                    if "nodes" in chapter:
                        extract_from_nodes(chapter["nodes"])

        # 处理 CCAR 格式（直接 structure 是数组）
        elif isinstance(structure, list):
            logger.info(f"Branch: structure is list, len={len(structure)}")
            extract_from_nodes(structure)
            logger.info(f"After extract_from_nodes: sections={len(sections)}")
        # 处理 CCAR 格式（structure 包含 nodes）
        elif isinstance(structure, dict) and "nodes" in structure:
            logger.info("Branch: structure is dict with nodes")
            extract_from_nodes(structure["nodes"])
            logger.info(f"After extract_from_nodes: sections={len(sections)}")

        # 如果 structure 是空但 doc_data 直接包含结构数组
        elif not structure and isinstance(doc_data, dict):
            # 检查是否直接在顶层有结构数组
            for key in ["structure", "sections", "chapters"]:
                if key in doc_data and isinstance(doc_data[key], list):
                    extract_from_nodes(doc_data[key])
                    break

        return sections

    def _build_precise_mappings(self, docs_sections: Dict, group_num: str) -> List[Dict]:
        """基于条款号建立精确映射"""
        # 按条款号分组
        by_number = defaultdict(list)

        for doc_name, sections in docs_sections.items():
            for section in sections:
                num = section["section"]
                by_number[num].append({
                    "document": doc_name,
                    "section": num,
                    "title": section["title"],
                    "full_content": section["full_content"],
                    "has_requirements": section.get("has_requirements", False)
                })

        # 创建映射（只包含多文档的条款）
        mappings = []
        for num, docs_sections in by_number.items():
            if len(docs_sections) >= 2:
                # 分析内容相似度
                equivalence_score = self._calculate_equivalence_score(docs_sections)

                mappings.append({
                    "section_number": num,
                    "documents": [s["document"] for s in docs_sections],
                    "titles": [s["title"] for s in docs_sections],
                    "equivalence_score": equivalence_score,
                    "all_have_requirements": all(s.get("has_requirements", False) for s in docs_sections),
                    "sections": docs_sections
                })

        # 按等效性分数排序
        mappings.sort(key=lambda m: m["equivalence_score"], reverse=True)

        return mappings

    def _calculate_equivalence_score(self, sections: List[Dict]) -> float:
        """计算条款间的等效性分数"""
        if len(sections) < 2:
            return 0.0

        score = 0.0
        base_content = sections[0].get("full_content", "")

        # 1. 基础分：多文档都有这个条款号
        score += 10.0

        # 2. 内容长度相似度
        content_lengths = [len(s.get("full_content", "")) for s in sections]
        avg_length = sum(content_lengths) / len(content_lengths)
        if avg_length > 0:
            variance = sum((l - avg_length) ** 2 for l in content_lengths) / len(content_lengths)
            # 低方差表示内容长度相近
            score += max(0, 10 - variance / 100)

        # 3. 关键词重叠
        words_in_all = None
        first_words = set(self._extract_keywords(base_content))
        words_in_all = first_words.copy()

        for section in sections[1:]:
            content = section.get("full_content", "")
            words = set(self._extract_keywords(content))
            words_in_all.intersection_update(words)

        if words_in_all:
            score += len(words_in_all) * 2

        # 4. 都有要求陈述
        if all(s.get("has_requirements", False) for s in sections):
            score += 5.0

        return min(score, 100.0)

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        # 简单关键词提取，实际应用中可以使用更复杂的NLP
        import re
        # 移除标点符号
        content_clean = re.sub(r'[\\s,。.()、（）\\[\\]{}\\-]', ' ', content)
        words = [w for w in content_clean.split() if len(w) > 2]
        return words

    def _build_bidirectional_maps(self) -> None:
        """构建双向映射"""
        for group_num, mappings in self.mappings.items():
            for mapping in mappings:
                section_num = mapping["section_number"]

                for section_info in mapping["sections"]:
                    doc_name = section_info["document"]

                    # 创建正向映射
                    if doc_name not in self.bidirectional_mappings[group_num]:
                        self.bidirectional_mappings[group_num][doc_name] = {}

                    self.bidirectional_mappings[group_num][doc_name][section_num] = {
                        "equivalent_docs": [s["document"] for s in mapping["sections"] if s["document"] != doc_name],
                        "equivalence_score": mapping["equivalence_score"]
                    }

    def _count_unique_sections(self) -> int:
        """统计唯一条款号数量"""
        unique_sections = set()
        for group_mappings in self.mappings.values():
            for mapping in group_mappings:
                unique_sections.add(mapping["section_number"])
        return len(unique_sections)

    async def _analyze_differences(self, params: Dict) -> Dict:
        """分析跨机构条款差异"""
        differences = []

        for group_num, mappings in self.mappings.items():
            for mapping in mappings[:20]:  # 限制数量
                sections = mapping["sections"]
                if len(sections) >= 2:
                    # 对比各机构版本的条款
                    diff_analysis = {
                        "section_number": mapping["section_number"],
                        "documents": [],
                        "content_differences": [],
                        "requirement_differences": []
                    }

                    for section_info in sections:
                        doc_name = section_info["document"]
                        title = section_info["title"]
                        content = section_info["full_content"]

                        # 提取具体要求
                        requirements = self._extract_requirements(content)

                        diff_analysis["documents"].append(doc_name)
                        diff_analysis["content_differences"].append({
                            "document": doc_name,
                            "title": title[:80],
                            "content_length": len(content)
                        })
                        diff_analysis["requirement_differences"].append({
                            "document": doc_name,
                            "requirements": requirements[:3]
                        })

                    # 分析差异
                    if len(diff_analysis["documents"]) >= 2:
                        differences.append(diff_analysis)

        return {
            "improvements": [f"分析 {len(differences)} 组条款差异"],
            "differences": differences
        }

    def _extract_requirements(self, content: str) -> List[str]:
        """提取条款中的具体要求"""
        requirements = []

        # 按句子分割
        sentences = re.split(r'[。.\n]', content)

        for sentence in sentences:
            sentence = sentence.strip()
            # 检查是否包含要求性语言
            if any(kw in sentence for kw in ["必须", "应当", "应该", "要求", "不得", "需"]):
                if len(sentence) > 5:
                    requirements.append(sentence[:100])

        return requirements

    async def _assess_mapping_quality(self, params: Dict) -> Dict:
        """评估映射质量"""
        quality_metrics = {}

        for group_num, mappings in self.mappings.items():
            total_score = 0
            count = 0

            for mapping in mappings:
                score = mapping["equivalence_score"]
                weight = 1.0

                # 高质量映射的特征
                if mapping["all_have_requirements"]:
                    weight += 0.5

                weighted_score = score * weight
                total_score += weighted_score
                count += 1

            avg_score = total_score / count if count > 0 else 0

            quality_metrics[group_num] = {
                "avg_equivalence_score": avg_score,
                "mapping_count": count,
                "quality_rating": self._get_quality_rating(avg_score)
            }

        return {
            "improvements": [f"评估 {len(quality_metrics)} 个规章组的映射质量"],
            "quality_metrics": quality_metrics
        }

    def _get_quality_rating(self, score: float) -> str:
        """获取质量评级"""
        if score >= 80:
            return "EXCELLENT"
        elif score >= 60:
            return "GOOD"
        elif score >= 40:
            return "FAIR"
        else:
            return "POOR"

    async def _find_coverage_gaps(self, params: Dict) -> Dict:
        """发现覆盖空白"""
        gaps = []

        for group_num, group_info in self.REGULATION_GROUPS.items():
            expected_docs = group_info["documents"]
            actual_docs = [d for d in expected_docs if any(d == m.get("documents", [""])[0]
                              for m in self.mappings.get(group_num, []))]

            for doc in expected_docs:
                if doc not in actual_docs:
                    gaps.append({
                        "group": group_num,
                        "missing_document": doc,
                        "reason": "文档不在知识库中"
                    })

        # 检查未映射的条款
        for group_num, mappings in self.mappings.items():
            total_possible = len(mappings)
            high_quality = [m for m in mappings if m["equivalence_score"] > 50]

            gaps.append({
                "group": group_num,
                "total_mappings": total_possible,
                "high_quality_mappings": len(high_quality),
                "improvement_needed": total_possible - len(high_quality)
            })

        return {
            "improvements": [f"发现 {len(gaps)} 个覆盖空白"],
            "gaps": gaps
        }

    async def _export_enhanced_mappings(self, params: Dict) -> Dict:
        """导出增强映射"""
        output_path = params.get("output", str(self.processed_dir.parent / "data/enhanced_cross_mappings.json"))

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "timestamp": str(Path.cwd()),
            "groups": self.REGULATION_GROUPS,
            "mappings": self.mappings,
            "bidirectional_mappings": dict(self.bidirectional_mappings),
            "quality_metrics": {},
            "total_mappings": sum(len(m) for m in self.mappings.values())
        }

        # 添加质量指标
        for group_num in self.REGULATION_GROUPS.keys():
            if group_num in self.mappings:
                mappings = self.mappings[group_num]
                avg_score = sum(m["equivalence_score"] for m in mappings) / len(mappings)
                export_data["quality_metrics"][group_num] = {
                    "avg_equivalence_score": avg_score,
                    "mapping_count": len(mappings),
                    "quality_rating": self._get_quality_rating(avg_score)
                }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return {
            "improvements": [f"导出增强映射到 {output_file}"],
            "output": str(output_file),
            "total_mappings": export_data["total_mappings"]
        }

    async def _verify_equivalence(self, params: Dict) -> Dict:
        """验证条款等效性"""
        verification_results = []

        for group_num, mappings in self.mappings.items():
            for mapping in mappings[:30]:  # 限制数量
                section_num = mapping["section_number"]
                sections = mapping["sections"]

                if len(sections) >= 2:
                    # 详细对比每对条款
                    for i in range(len(sections)):
                        for j in range(i + 1, len(sections)):
                            doc_a = sections[i]["document"]
                            doc_b = sections[j]["document"]
                            content_a = sections[i]["full_content"]
                            content_b = sections[j]["full_content"]

                            # 计算相似度
                            similarity = self._calculate_content_similarity(content_a, content_b)

                            verification_results.append({
                                "section": section_num,
                                "document_a": doc_a,
                                "document_b": doc_b,
                                "similarity_score": similarity,
                                "equivalence_level": self._get_equivalence_level(similarity),
                                "content_length_a": len(content_a),
                                "content_length_b": len(content_b)
                            })

        return {
            "improvements": [f"验证 {len(verification_results)} 对条款等效性"],
            "verification_results": verification_results
        }

    def _calculate_content_similarity(self, content_a: str, content_b: str) -> float:
        """计算两段内容的相似度"""
        words_a = set(self._extract_keywords(content_a))
        words_b = set(self._extract_keywords(content_b))

        if not words_a or not words_b:
            return 0.0

        # Jaccard相似度
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)

        return (intersection / union * 100) if union > 0 else 0.0

    def _get_equivalence_level(self, similarity: float) -> str:
        """获取等效性级别"""
        if similarity >= 80:
            return "FULLY_EQUIVALENT"
        elif similarity >= 60:
            return "SUBSTANTIALLY_EQUIVALENT"
        elif similarity >= 40:
            return "PARTIALLY_EQUIVALENT"
        else:
            return "NOT_EQUIVALENT"

    async def _generate_mapping_summary_report(self, params: Dict) -> Dict:
        """生成映射摘要报告"""
        report = {
            "overview": {},
            "by_agency": {},
            "high_quality_mappings": [],
            "low_quality_mappings": [],
            "recommendations": []
        }

        total_mappings = 0
        for group_num, mappings in self.mappings.items():
            total_mappings += len(mappings)

            # 分类
            high_quality = [m for m in mappings if m["equivalence_score"] > 70]
            low_quality = [m for m in mappings if m["equivalence_score"] < 40]

            report["high_quality_mappings"].extend([
                {"group": group_num, "section": m["section_number"], "score": m["equivalence_score"]}
                for m in high_quality[:5]
            ])
            report["low_quality_mappings"].extend([
                {"group": group_num, "section": m["section_number"], "score": m["equivalence_score"]}
                for m in low_quality[:5]
            ])

        report["overview"] = {
            "total_regulation_groups": len(self.mappings),
            "total_mappings": total_mappings,
            "avg_coverage": self._calculate_avg_coverage()
        }

        # 按机构统计
        for group_num, mappings in self.mappings.items():
            for mapping in mappings:
                for section in mapping["sections"]:
                    doc = section["document"]
                    if doc not in report["by_agency"]:
                        report["by_agency"][doc] = 0
                    report["by_agency"][doc] += 1

        # 生成建议
        if report["low_quality_mappings"]:
            report["recommendations"].append("建议审查低质量映射的条款内容")
        if total_mappings < 100:
            report["recommendations"].append("建议增加更多文档以提高映射覆盖率")

        return {
            "improvements": ["生成映射摘要报告"],
            "report": report
        }

    def _calculate_avg_coverage(self) -> float:
        """计算平均覆盖率"""
        if not self.mappings:
            return 0.0

        coverages = []
        for group_num, mappings in self.mappings.items():
            expected = self.REGULATION_GROUPS.get(group_num, {}).get("total_sections_estimated", 100)
            actual = len(mappings)
            coverages.append((actual / expected * 100) if expected > 0 else 0)

        return sum(coverages) / len(coverages) if coverages else 0.0

    async def _find_terminology_differences(self, params: Dict) -> Dict:
        """发现术语差异"""
        terminology_by_agency = defaultdict(set)

        for group_num, mappings in self.mappings.items():
            for mapping in mappings[:20]:
                for section in mapping["sections"]:
                    doc = section["document"]
                    content = section["full_content"]

                    # 提取术语
                    terms = self._extract_technical_terms(content)
                    agency = self._get_agency_from_doc(doc)
                    terminology_by_agency[agency].update(terms)

        # 分析差异
        all_terms = set()
        for terms in terminology_by_agency.values():
            all_terms.update(terms)

        common_terms = set()
        unique_terms = {}

        for agency, terms in terminology_by_agency.items():
            common = all_terms & terms
            common_terms.update(common)
            unique = terms - common
            unique_terms[agency] = list(unique)[:10]

        return {
            "improvements": [f"分析 {len(terminology_by_agency)} 个机构的术语"],
            "terminology_by_agency": {k: list(v)[:20] for k, v in terminology_by_agency.items()},
            "common_terms": list(common_terms)[:30],
            "unique_terms": unique_terms
        }

    def _extract_technical_terms(self, content: str) -> set:
        """提取技术术语"""
        terms = set()

        # 航空领域常见术语模式
        patterns = [
            r'[A-Z]{2,20}(?:-[0-9]+)?',  # 如 APUs, APU, TC-1
            r'[A-Za-z]+(?:[机器系组室])',  # 中文术语
            r'\d+\s*(?:节|条|款|段)',  # 条款引用
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            terms.update(matches)

        # 过滤常见词
        stopwords = {"THE", "AND", "OR", "OF", "IN", "TO", "FOR", "WITH", "BY"}
        terms = {t for t in terms if t not in stopwords and len(t) > 2}

        return terms

    def _get_agency_from_doc(self, doc_name: str) -> str:
        """从文档名获取机构"""
        if "CCAR" in doc_name:
            return "CAAC"
        elif "FAR" in doc_name:
            return "FAA"
        elif "CS" in doc_name or "EASA" in doc_name:
            return "EASA"
        return "UNKNOWN"

    async def _recommend_reading_order(self, params: Dict) -> Dict:
        """推荐阅读顺序"""
        recommendations = {}

        for group_num, group_info in self.REGULATION_GROUPS.items():
            docs = group_info["documents"]

            # 根据中文用户推荐阅读顺序
            if "CCAR" in docs[0]:
                # CAAC优先
                primary = [d for d in docs if "CCAR" in d]
                secondary = [d for d in docs if "FAR" in d]
                tertiary = [d for d in docs if "CS" in d or "EASA" in d]
            elif "FAR" in docs[0]:
                primary = [d for d in docs if "FAR" in d]
                secondary = [d for d in docs if "EASA" in d or "CS" in d]
                tertiary = [d for d in docs if "CCAR" in d]
            else:
                primary = docs[:1]
                secondary = docs[1:2]
                tertiary = docs[2:3]

            recommendations[group_num] = {
                "group_name": group_info["name"],
                "primary_recommendation": primary,
                "secondary_reference": secondary,
                "tertiary_reference": tertiary,
                "reading_strategy": f"先阅读 {primary} 了解基本要求，然后参考 {secondary} 理解国际标准"
            }

        return {
            "improvements": [f"为 {len(recommendations)} 个规章组生成阅读建议"],
            "recommendations": recommendations
        }

    async def _build_bidirectional_mappings(self, params: Dict) -> Dict:
        """构建双向映射"""
        self._build_bidirectional_maps()

        return {
            "improvements": [f"构建 {len(self.bidirectional_mappings)} 个规章组的双向映射"],
            "bidirectional_mappings": dict(self.bidirectional_mappings)
        }


__all__ = ['EnhancedCrossMappingAgent']
