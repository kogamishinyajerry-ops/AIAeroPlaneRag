#!/usr/bin/env python3
"""
可用性增强Agent

专注于提升系统可用性从48.3到70+
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


class UsabilityEnhancerAgent(BaseAgent):
    """可用性增强Agent"""

    def __init__(self, knowledge_base_path: str):
        super().__init__("UsabilityEnhancerAgent", knowledge_base_path)

    def get_capabilities(self) -> List[str]:
        return [
            "enrich_metadata",
            "expand_citations",
            "generate_visualizations"
        ]

    async def process(self, task: AgentTask) -> Any:
        """处理任务"""
        action = task.action

        if action == "enrich_metadata":
            return await self._enrich_metadata(task.params)
        elif action == "expand_citations":
            return await self._expand_citations(task.params)
        elif action == "generate_visualizations":
            return await self._generate_visualizations(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _enrich_metadata(self, params: Dict) -> Dict:
        """丰富元数据"""
        improvements = []

        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                # 统计条款数量
                clause_count = self._count_clauses(data)
                improvements.append(f"{doc_name}: {clause_count} 个条款")

            except Exception as e:
                logger.warning(f"处理 {structure_file} 失败: {e}")

        return {"improvements": improvements}

    async def _expand_citations(self, params: Dict) -> Dict:
        """扩展引用片段"""
        min_length = params.get("min_length", 500)
        improvements = []

        for structure_file in self.kb_path.glob("*_structure.json"):
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                # 扩展内容
                expanded_count = self._expand_content_in_data(data, min_length)
                improvements.append(f"{doc_name}: 扩展了 {expanded_count} 个条款")

            except Exception as e:
                logger.warning(f"扩展 {structure_file} 失败: {e}")

        return {"improvements": improvements}

    async def _generate_visualizations(self, params: Dict) -> Dict:
        """生成可视化数据"""
        improvements = []

        # 创建可视化目录
        viz_dir = self.kb_path / "visualizations"
        viz_dir.mkdir(exist_ok=True)

        # 生成条款层级图
        hierarchy = self._generate_hierarchy()
        with open(viz_dir / "hierarchy.json", 'w', encoding='utf-8') as f:
            json.dump(hierarchy, f, ensure_ascii=False, indent=2)
        improvements.append(f"生成层级图: {len(hierarchy.get('nodes', []))} 个节点")

        # 生成关系图谱
        relationships = self._generate_relationships()
        with open(viz_dir / "relationships.json", 'w', encoding='utf-8') as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)
        improvements.append(f"生成关系图谱: {len(relationships.get('edges', []))} 条边")

        return {"improvements": improvements}

    def _count_clauses(self, data: Dict) -> int:
        """统计条款数量"""
        count = 0

        def count_nodes(nodes):
            nonlocal count
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                if re.search(r'§\s*[\d.]+|第\s*[\d.]+\s*条', title):
                    count += 1

                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    count_nodes(children)

        structure = data.get("structure", [])
        if isinstance(structure, list):
            count_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            count_nodes(structure["chapters"])

        return count

    def _expand_content_in_data(self, data: Dict, min_length: int) -> int:
        """扩展数据中的内容"""
        count = 0

        def expand_nodes(nodes):
            nonlocal count
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                content_parts = node.get("content_parts", [])
                summary = node.get("summary", "")

                current_length = len(summary) + sum(len(p) for p in content_parts)

                if current_length < min_length and content_parts:
                    # 合并所有内容
                    node["expanded_content"] = summary + "\n".join(content_parts)
                    count += 1

                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    expand_nodes(children)

        structure = data.get("structure", [])
        if isinstance(structure, list):
            expand_nodes(structure)
        elif isinstance(structure, dict) and "chapters" in structure:
            expand_nodes(structure["chapters"])

        return count

    def _generate_hierarchy(self) -> Dict:
        """生成层级图"""
        nodes = []
        edges = []

        for structure_file in list(self.kb_path.glob("*_structure.json"))[:5]:  # 限制文件数量
            try:
                with open(structure_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                doc_name = data.get("doc_name", structure_file.stem.replace("_structure", ""))

                def build_nodes(nodes_list, parent_id=None, level=0):
                    for node in nodes_list[:20]:  # 限制节点数量
                        if not isinstance(node, dict):
                            continue

                        title = node.get("title", "")[:50]
                        node_id = f"{doc_name}:{len(nodes)}"

                        nodes.append({"id": node_id, "label": title, "document": doc_name, "level": level})

                        if parent_id:
                            edges.append({"source": parent_id, "target": node_id, "type": "hierarchy"})

                        children = node.get("nodes", []) or node.get("sections", [])
                        if children and level < 3:  # 限制深度
                            build_nodes(children, node_id, level + 1)

                structure = data.get("structure", [])
                if isinstance(structure, list):
                    build_nodes(structure)
                elif isinstance(structure, dict) and "chapters" in structure:
                    build_nodes(structure["chapters"])

            except Exception as e:
                logger.warning(f"生成层级图失败 {structure_file}: {e}")

        return {"nodes": nodes[:100], "edges": edges[:200], "generated_at": datetime.now().isoformat()}

    def _generate_relationships(self) -> Dict:
        """生成关系图谱"""
        nodes = []
        edges = []

        # 收集所有文档
        docs = set()
        for structure_file in self.kb_path.glob("*_structure.json"):
            doc_name = structure_file.stem.replace("_structure", "")
            docs.add(doc_name)

        # 添加文档节点
        for doc in sorted(docs)[:10]:
            nodes.append({"id": doc, "label": doc, "type": "document"})

        # 添加文档间关系（基于规章类型）
        doc_groups = {
            "CCAR-25-R2": ["CCAR-25-R4", "FAR-25", "CS-25"],
            "CCAR-33-R2": ["FAR-33", "CS-E"],
        }

        for doc, related in doc_groups.items():
            if doc in docs:
                for rel in related:
                    if rel in docs:
                        edges.append({"source": doc, "target": rel, "type": "related"})

        return {"nodes": nodes, "edges": edges, "generated_at": datetime.now().isoformat()}


__all__ = ['UsabilityEnhancerAgent']
