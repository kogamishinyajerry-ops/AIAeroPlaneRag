#!/usr/bin/env python3
"""
知识关联Agent

专注于提升可信度从54.1到70+
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

from .agent_base import BaseAgent, AgentTask

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeLinkerAgent(BaseAgent):
    """知识关联Agent"""

    def __init__(self, knowledge_base_path: str):
        super().__init__("KnowledgeLinkerAgent", knowledge_base_path)

        # 领域聚类
        self.domain_clusters = {
            "发动机": ["发动机", "APU", "涡轮", "燃烧室"],
            "结构": ["机身", "机翼", "起落架", "襟翼"],
            "系统": ["液压", "燃油", "空调", "电气"],
            "安全": ["防火", "防爆", "应急", "撤离"],
        }

    def get_capabilities(self) -> List[str]:
        return [
            "build_cross_links",
            "expand_terminology",
            "optimize_relevance",
            "create_clusters"
        ]

    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        action = task.action

        if action == "build_cross_links":
            return await self._build_cross_links(task.params)
        elif action == "expand_terminology":
            return await self._expand_terminology(task.params)
        elif action == "optimize_relevance":
            return await self._optimize_relevance(task.params)
        elif action == "create_clusters":
            return await self._create_clusters(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _build_cross_links(self, params: Dict) -> Dict:
        """建立跨文档关联"""
        improvements = []

        # 发现等效条款
        equivalent_links = self._find_equivalent_clauses()
        improvements.append(f"发现 {len(equivalent_links)} 对等效条款")

        # 发现引用关联
        reference_links = self._find_reference_links()
        improvements.append(f"发现 {len(reference_links)} 个引用关联")

        # 保存关联数据
        links_dir = self.kb_path / "knowledge_links"
        links_dir.mkdir(exist_ok=True)

        with open(links_dir / "cross_document_links.json", 'w', encoding='utf-8') as f:
            json.dump({
                "equivalent_links": equivalent_links,
                "reference_links": reference_links,
                "generated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        return {
            "improvements": improvements,
            "metrics": {
                "equivalent_links": len(equivalent_links),
                "reference_links": len(reference_links)
            }
        }

    async def _expand_terminology(self, params: Dict) -> Dict:
        """扩展术语覆盖"""
        improvements = []

        # 航空专业术语映射
        terminology_map = {
            "发动机": ["engine", "动力装置", "引擎"],
            "防火": ["fire protection", "防火墙", "阻燃"],
            "液压系统": ["hydraulic system", "液压"],
            "APU": ["辅助动力装置", "Auxiliary Power Unit"],
            "OEI": ["One Engine Inoperative", "单发失效"],
            "ETOPS": ["Extended Operations", "延伸航程"],
        }

        # 保存术语映射
        links_dir = self.kb_path / "knowledge_links"
        links_dir.mkdir(exist_ok=True)

        with open(links_dir / "expanded_terminology.json", 'w', encoding='utf-8') as f:
            json.dump(terminology_map, f, ensure_ascii=False, indent=2)

        improvements.append(f"扩展了 {len(terminology_map)} 个术语的同义词")

        return {"improvements": improvements}

    async def _optimize_relevance(self, params: Dict) -> Dict:
        """优化相关性排序"""
        improvements = []

        # 构建查询-条款映射
        query_mapping = self._build_query_mapping()

        # 保存映射
        links_dir = self.kb_path / "knowledge_links"
        links_dir.mkdir(exist_ok=True)

        with open(links_dir / "relevance_optimization.json", 'w', encoding='utf-8') as f:
            json.dump(query_mapping, f, ensure_ascii=False, indent=2)

        improvements.append(f"构建了 {len(query_mapping)} 个查询映射")

        return {"improvements": improvements}

    async def _create_clusters(self, params: Dict) -> Dict:
        """创建主题聚类"""
        improvements = []

        clusters = {}

        # 为每个领域创建聚类
        for domain, terms in self.domain_clusters.items():
            clauses_in_domain = []

            for structure_file in self.kb_path.glob("*_structure.json"):
                try:
                    with open(structure_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                    # 查找包含领域术语的条款
                    def find_clauses(nodes):
                        for node in nodes:
                            if not isinstance(node, dict):
                                continue

                            title = node.get("title", "")
                            content = node.get("summary", "")

                            if any(term in title or term in content for term in terms):
                                clause_match = re.search(r'§\s*([\d.]+)', title)
                                if clause_match:
                                    clauses_in_domain.append({
                                        "document": doc_name,
                                        "section": clause_match.group(1),
                                        "title": title
                                    })

                            children = node.get("nodes", []) or node.get("sections", [])
                            if children:
                                find_clauses(children)

                    structure = data.get("structure", [])
                    if isinstance(structure, list):
                        find_clauses(structure)
                    elif isinstance(structure, dict) and "chapters" in structure:
                        find_clauses(structure["chapters"])

                except Exception as e:
                    logger.warning(f"聚类失败 {structure_file}: {e}")

            clusters[domain] = clauses_in_domain[:20]  # 限制数量

        # 保存聚类
        links_dir = self.kb_path / "knowledge_links"
        links_dir.mkdir(exist_ok=True)

        with open(links_dir / "domain_clusters.json", 'w', encoding='utf-8') as f:
            json.dump(clusters, f, ensure_ascii=False, indent=2)

        improvements.append(f"创建了 {len(clusters)} 个领域聚类")

        return {"improvements": improvements}

    def _find_equivalent_clauses(self) -> List[Dict]:
        """查找等效条款"""
        # 已知的等效条款映射
        return [
            {"type": "equivalent", "clauses": ["CCAR-25-R4:25.1", "FAR-25:25.1"]},
            {"type": "equivalent", "clauses": ["CCAR-33-R2:33.5", "FAR-33:33.5"]},
            {"type": "equivalent", "clauses": ["CCAR-29-R2:29.1", "FAR-29:29.1"]},
        ]

    def _find_reference_links(self) -> List[Dict]:
        """查找引用关联"""
        references = []

        # 从结构文件中查找引用
        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                def find_refs(nodes):
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue

                        title = node.get("title", "")
                        content_parts = node.get("content_parts", [])

                        # 查找引用
                        content = " ".join(content_parts)
                        refs = re.findall(r'(?:CCAR|FAR|CS)[-]?\d+[-R]?\d*', content)

                        if refs:
                            section_match = re.search(r'§\s*([\d.]+)', title)
                            if section_match:
                                for ref in refs[:3]:  # 限制数量
                                    references.append({
                                        "type": "reference",
                                        "source": f"{doc_name}:{section_match.group(1)}",
                                        "target": ref
                                    })

                        children = node.get("nodes", []) or node.get("sections", [])
                        if children:
                            find_refs(children)

                structure = data.get("structure", [])
                if isinstance(structure, list):
                    find_refs(structure)
                elif isinstance(structure, dict) and "chapters" in structure:
                    find_refs(structure["chapters"])

            except Exception as e:
                logger.warning(f"查找引用失败 {structure_file}: {e}")

        return references[:100]  # 限制数量

    def _build_query_mapping(self) -> Dict:
        """构建查询-条款映射"""
        mapping = defaultdict(list)

        # 从结构文件中提取关键词
        for structure_file in list(self.kb_path.glob("*_structure.json"))[:5]:
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                def extract_mapping(nodes):
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue

                        title = node.get("title", "")

                        # 提取条款号
                        section_match = re.search(r'§\s*([\d.]+)', title)
                        if section_match:
                            clause_id = f"{doc_name}:{section_match.group(1)}"

                            # 提取关键词
                            keywords = re.findall(r'[\u4e00-\u9fff]{2,}', title)

                            for keyword in keywords:
                                mapping[keyword].append(clause_id)

                        children = node.get("nodes", []) or node.get("sections", [])
                        if children:
                            extract_mapping(children)

                structure = data.get("structure", [])
                if isinstance(structure, list):
                    extract_mapping(structure)
                elif isinstance(structure, dict) and "chapters" in structure:
                    extract_mapping(structure["chapters"])

            except Exception as e:
                logger.warning(f"构建映射失败 {structure_file}: {e}")

        return dict(mapping)


__all__ = ['KnowledgeLinkerAgent']
