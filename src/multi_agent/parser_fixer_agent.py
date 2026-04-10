#!/usr/bin/env python3
"""
ParserFixerAgent - 专门修复文档解析问题

职责:
- 检测解析问题的文档
- 修复缺失的字段
- 重新计算统计数据
- 标准化文档结构
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.multi_agent.agent_base import BaseAgent, AgentTask


class ParserFixerAgent(BaseAgent):
    """
    解析修复 Agent

    自动检测和修复:
    1. 缺失的 total_sections 字段
    2. 缺失的 summary 字段
    3. 结构不一致问题
    4. 空的 sections/nodes 数组
    """

    def __init__(self, knowledge_base_path: str):
        super().__init__("ParserFixerAgent", knowledge_base_path)
        self.processed_dir = Path(knowledge_base_path)
        self.fix_log_path = self.processed_dir.parent / "logs/parser_fixes.json"

    def get_capabilities(self) -> List[str]:
        return [
            "detect_issues",
            "fix_missing_fields",
            "recalculate_stats",
            "standardize_structure",
            "regenerate_summary"
        ]

    async def process(self, task: AgentTask) -> Any:
        action = task.action

        if action == "detect_issues":
            return await self._detect_issues(task.params)
        elif action == "fix_missing_fields":
            return await self._fix_missing_fields(task.params)
        elif action == "recalculate_stats":
            return await self._recalculate_stats(task.params)
        elif action == "standardize_structure":
            return await self._standardize_structure(task.params)
        elif action == "regenerate_summary":
            return await self._regenerate_summary(task.params)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _detect_issues(self, params: Dict) -> Dict:
        """检测所有文档的解析问题"""
        issues = []
        documents = []

        for structure_file in self.processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", structure_file.stem)
            doc_issues = []

            # Check 1: Missing total_sections
            if "total_sections" not in data or data["total_sections"] == 0:
                doc_issues.append("missing_or_zero_total_sections")

            # Check 2: Missing structure
            if "structure" not in data:
                doc_issues.append("missing_structure")

            # Check 3: Wrong format (needs chapters or nodes)
            structure = data.get("structure", {})
            has_chapters = isinstance(structure, dict) and "chapters" in structure
            has_nodes = isinstance(structure, list)

            if not has_chapters and not has_nodes:
                doc_issues.append("invalid_structure_format")

            # Count actual sections
            section_count = self._count_sections(data)
            if section_count == 0:
                doc_issues.append("no_sections_found")

            if doc_issues:
                issues.append({
                    "document": doc_name,
                    "file": str(structure_file),
                    "issues": doc_issues,
                    "actual_sections": section_count
                })
                documents.append(doc_name)

        return {
            "improvements": [f"检测到 {len(documents)} 个文档有解析问题"],
            "issues": issues,
            "affected_documents": documents
        }

    async def _fix_missing_fields(self, params: Dict) -> Dict:
        """修复缺失的字段"""
        target_doc = params.get("document")
        fixes_made = []

        for structure_file in self.processed_dir.glob("*_structure.json"):
            if target_doc and target_doc not in structure_file.stem:
                continue

            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", structure_file.stem)
            modified = False

            # Fix 1: Add total_sections
            if "total_sections" not in data or data["total_sections"] == 0:
                section_count = self._count_sections(data)
                data["total_sections"] = section_count
                fixes_made.append(f"{doc_name}: 设置 total_sections = {section_count}")
                modified = True

            # Fix 2: Add agency if missing
            if "agency" not in data:
                if doc_name.startswith("FAR"):
                    data["agency"] = "FAA"
                elif doc_name.startswith("CS"):
                    data["agency"] = "EASA"
                elif doc_name.startswith("CCAR"):
                    data["agency"] = "CAAC"
                else:
                    data["agency"] = "UNKNOWN"
                fixes_made.append(f"{doc_name}: 设置 agency = {data['agency']}")
                modified = True

            # Fix 3: Add document_type
            if "document_type" not in data:
                data["document_type"] = "text_based"
                modified = True

            # Fix 4: Ensure total_pages exists
            if "total_pages" not in data:
                data["total_pages"] = 0
                modified = True

            # Fix 5: Ensure parse_quality exists
            if "parse_quality" not in data:
                section_count = data.get("total_sections", 0)
                if section_count > 300:
                    data["parse_quality"] = "excellent"
                elif section_count > 100:
                    data["parse_quality"] = "good"
                else:
                    data["parse_quality"] = "partial"
                modified = True

            # Save if modified
            if modified:
                with open(structure_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                fixes_made.append(f"{doc_name}: 文件已更新")

        return {
            "improvements": fixes_made,
            "fixed_count": len([f for f in fixes_made if "文件已更新" in f])
        }

    async def _recalculate_stats(self, params: Dict) -> Dict:
        """重新计算所有统计数据"""
        results = []

        for structure_file in self.processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", structure_file.stem)

            # Count sections
            section_count = self._count_sections(data)

            # Count pages (if available in nodes)
            page_count = data.get("total_pages", 0)

            # Update
            old_sections = data.get("total_sections", 0)
            data["total_sections"] = section_count

            # Save
            with open(structure_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            results.append({
                "document": doc_name,
                "old_sections": old_sections,
                "new_sections": section_count,
                "pages": page_count
            })

        return {
            "improvements": [f"重新计算 {len(results)} 个文档的统计数据"],
            "results": results
        }

    async def _standardize_structure(self, params: Dict) -> Dict:
        """标准化文档结构格式"""
        # This would convert between different structure formats
        # For now, just report what we have
        formats = {}

        for structure_file in self.processed_dir.glob("*_structure.json"):
            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", structure_file.stem)
            structure = data.get("structure", {})

            if isinstance(structure, dict) and "chapters" in structure:
                formats[doc_name] = "FAR_format"  # {chapters: [...]}
            elif isinstance(structure, list):
                formats[doc_name] = "CCAR_format"  # [{nodes: [...]}]
            else:
                formats[doc_name] = "unknown"

        return {
            "improvements": [f"分析 {len(formats)} 个文档的结构格式"],
            "formats": formats
        }

    async def _regenerate_summary(self, params: Dict) -> Dict:
        """为缺失摘要的节点生成摘要"""
        target_doc = params.get("document")
        regenerated = 0

        for structure_file in self.processed_dir.glob("*_structure.json"):
            if target_doc and target_doc not in structure_file.stem:
                continue

            with open(structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            doc_name = data.get("doc_name", structure_file.stem)
            modified = False

            def fix_summaries(nodes):
                nonlocal regenerated, modified
                for node in nodes:
                    if not isinstance(node, dict):
                        continue

                    # Generate summary from title if missing
                    if not node.get("summary") or len(node.get("summary", "")) < 5:
                        title = node.get("title", "")
                        if title:
                            node["summary"] = title[:100]
                            regenerated += 1
                            modified = True

                    # Recurse
                    children = node.get("nodes", []) or node.get("sections", [])
                    if children:
                        fix_summaries(children)

            structure = data.get("structure", {})
            if isinstance(structure, dict) and "chapters" in structure:
                fix_summaries(structure["chapters"])
            elif isinstance(structure, list):
                fix_summaries(structure)

            if modified:
                with open(structure_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

        return {
            "improvements": [f"为 {regenerated} 个节点生成摘要"],
            "regenerated_count": regenerated
        }

    def _count_sections(self, data: Dict) -> int:
        """递归统计条款数量"""
        count = 0
        structure = data.get("structure", {})

        def count_nodes(nodes):
            nonlocal count
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                title = node.get("title", "")
                # Check if this is a section (has 条 or § in title)
                if "条" in title or "§" in title:
                    count += 1
                # Recurse
                children = node.get("nodes", []) or node.get("sections", [])
                if children:
                    count_nodes(children)

        if isinstance(structure, dict) and "chapters" in structure:
            count_nodes(structure["chapters"])
        elif isinstance(structure, list):
            count_nodes(structure)

        return count


# Export
__all__ = ['ParserFixerAgent']
