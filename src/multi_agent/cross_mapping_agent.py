#!/usr/bin/env python3
"""
CrossMappingAgent - 建立CCAR/FAA/EASA之间的精确映射

职责:
- 基于条款编号建立对应关系 (如 25.1 ↔ 25.1)
- 发现跨机构的相似条款
- 构建映射关系表
- 支持跨规章查询
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent.agent_base import BaseAgent, AgentTask


class CrossMappingAgent(BaseAgent):
    """
    跨机构映射 Agent

    建立:
    - CCAR-25-R4 ↔ FAR-25 ↔ CS-25 (运输类飞机)
    - CCAR-33-R2 ↔ FAR-33 ↔ CS-E (发动机)
    - CCAR-29-R2 ↔ FAR-29 (旋翼机)
    - CCAR-23 ↔ FAR-23 (正常类飞机)
    """

    # Regulation correspondences
    REGULATION_GROUPS = {
        "25": {
            "name": "大型运输类飞机",
            "documents": ["CCAR-25-R4", "FAR-25", "CS-25"]
        },
        "33": {
            "name": "航空发动机",
            "documents": ["CCAR-33-R2", "FAR-33", "CS-E"]
        },
        "29": {
            "name": "运输类旋翼机",
            "documents": ["CCAR-29-R2", "FAR-29"]
        },
        "23": {
            "name": "正常类飞机",
            "documents": ["CCAR-23", "FAR-23"]
        }
    }

    def __init__(self, knowledge_base_path: str):
        super().__init__("CrossMappingAgent", knowledge_base_path)
        self.processed_dir = Path(knowledge_base_path)
        self.mapping_cache_path = self.processed_dir.parent / "data/cross_mappings.json"
        self.mappings: Dict[str, Dict] = {}

    def get_capabilities(self) -> List[str]:
        return [
            "build_section_mappings",
            "find_equivalent_sections",
            "create_mapping_table",
            "export_mappings",
            "analyze_coverage"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "build_section_mappings":
            return await self._build_section_mappings(task.params)
        elif action == "find_equivalent_sections":
            return await self._find_equivalent_sections(task.params)
        elif action == "create_mapping_table":
            return await self._create_mapping_table(task.params)
        elif action == "export_mappings":
            return await self._export_mappings(task.params)
        elif action == "analyze_coverage":
            return await self._analyze_coverage(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _build_section_mappings(self, params: Dict) -> Dict:
        """建立所有规章的条款映射"""
        all_mappings = {}
        total_mappings = 0

        # Load all documents
        documents = {}
        for structure_file in self.processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            doc_name = data.get("doc_name", structure_file.stem)
            documents[doc_name] = data

        # For each regulation group
        for group_num, group_info in self.REGULATION_GROUPS.items():
            group_docs = {k: v for k, v in documents.items()
                         if any(d in k for d in group_info["documents"])}

            if len(group_docs) < 2:
                continue

            # Extract section numbers from each document
            sections_by_doc = {}
            for doc_name, doc_data in group_docs.items():
                sections = self._extract_sections(doc_data)
                sections_by_doc[doc_name] = sections

            # Build mappings based on section number
            group_mappings = self._map_by_section_number(sections_by_doc)
            all_mappings[group_num] = group_mappings
            total_mappings += len(group_mappings)

        # Cache mappings
        self.mappings = all_mappings

        return {
            "improvements": [f"建立 {total_mappings} 个跨规章条款映射"],
            "mappings": all_mappings,
            "total_mappings": total_mappings
        }

    async def _find_equivalent_sections(self, params: Dict) -> Dict:
        """查找等效条款"""
        query = params.get("query")  # Format: "doc_name:section_number"
        top_k = params.get("top_k", 5)

        if not query or ":" not in query:
            return {"improvements": [], "equivalent": []}

        doc_name, section_num = query.split(":", 1)

        # Extract base number (e.g., "25.1" from "FAR-25:25.1")
        match = re.search(r'(\d+(?:\.\d+)?)', section_num)
        if not match:
            return {"improvements": [], "equivalent": []}

        base_num = match.group(1)

        # Find group
        group_num = base_num.split(".")[0] if "." in base_num else None
        if not group_num or group_num not in self.mappings:
            return {"improvements": [], "equivalent": []}

        # Find equivalents
        equivalents = []
        for mapping in self.mappings[group_num]:
            if any(base_num in m.get("section", "") for m in mapping.get("sections", [])):
                equivalents = mapping.get("sections", [])
                break

        return {
            "improvements": [f"找到 {len(equivalents)} 个等效条款"],
            "equivalent": equivalents
        }

    async def _create_mapping_table(self, params: Dict) -> Dict:
        """创建映射关系表"""
        group_num = params.get("group", "25")

        if group_num not in self.mappings:
            return {"improvements": [f"组 {group_num} 没有映射数据"]}

        mappings = self.mappings[group_num]
        table = []

        for mapping in mappings:
            row = {}
            for section_info in mapping.get("sections", []):
                doc = section_info.get("document", "")
                num = section_info.get("section", "")
                row[doc] = num
            table.append(row)

        return {
            "improvements": [f"创建组 {group_num} 的映射表，共 {len(table)} 行"],
            "table": table
        }

    async def _export_mappings(self, params: Dict) -> Dict:
        """导出映射关系"""
        output_path = params.get("output", str(self.mapping_cache_path))

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "timestamp": str(datetime.now()),
            "groups": self.REGULATION_GROUPS,
            "mappings": self.mappings,
            "total_mappings": sum(len(m) for m in self.mappings.values())
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return {
            "improvements": [f"映射关系已导出到 {output_file}"],
            "output": str(output_file)
        }

    async def _analyze_coverage(self, params: Dict) -> Dict:
        """分析映射覆盖率"""
        coverage = {}

        for group_num, group_info in self.REGULATION_GROUPS.items():
            if group_num not in self.mappings:
                coverage[group_num] = {"mappings": 0, "documents": []}
                continue

            docs_in_group = set()
            for mapping in self.mappings[group_num]:
                for section in mapping.get("sections", []):
                    docs_in_group.add(section.get("document", ""))

            coverage[group_num] = {
                "mappings": len(self.mappings[group_num]),
                "documents": list(docs_in_group),
                "expected_documents": len(group_info["documents"])
            }

        return {
            "improvements": [f"分析 {len(coverage)} 个规章组的映射覆盖率"],
            "coverage": coverage
        }

    def _extract_sections(self, doc_data: Dict) -> List[Dict]:
        """提取文档中的所有条款"""
        sections = []
        doc_name = doc_data.get("doc_name", "")

        def extract(nodes):
            for node in nodes:
                if not isinstance(node, dict):
                    continue

                title = node.get("title", "")
                # Extract section number
                match = re.search(r'(\d+(?:\.\d+)+)', title)
                if match:
                    sections.append({
                        "document": doc_name,
                        "section": match.group(1),
                        "title": title
                    })

                # Recurse
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    extract(children)

        structure = doc_data.get("structure", {})
        if isinstance(structure, dict) and "chapters" in structure:
            extract(structure["chapters"])
        elif isinstance(structure, list):
            extract(structure)

        return sections

    def _map_by_section_number(self, sections_by_doc: Dict) -> List[Dict]:
        """基于条款编号建立映射"""
        # Group by section number
        by_number = defaultdict(list)

        for doc_name, sections in sections_by_doc.items():
            for section in sections:
                by_number[section["section"]].append({
                    "document": doc_name,
                    "section": section["section"],
                    "title": section["title"]
                })

        # Create mappings (only where we have multiple documents)
        mappings = []
        for num, docs_sections in by_number.items():
            if len(docs_sections) >= 2:
                mappings.append({
                    "section_number": num,
                    "sections": docs_sections
                })

        return mappings


from datetime import datetime

# Export
__all__ = ['CrossMappingAgent']
