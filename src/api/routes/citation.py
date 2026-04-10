import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from src.api.dependencies.deps import services

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/v1/enhanced/citation/{doc_name}/{section_id}")
def get_full_citation(doc_name: str, section_id: str) -> dict[str, Any]:
    """
    获取完整的条款内容

    用于点击引用时展开显示更多内容
    """
    if services.enhanced_kb is None:
        return {"status": "unavailable", "error": "Enhanced KB not initialized"}

    # 查找完整的条款内容
    import json
    from pathlib import Path

    # 查找结构文件
    structure_file = Path(PROCESSED_DATA_DIR) / f"{doc_name}_structure.json"
    if not structure_file.exists():
        return {"status": "not_found", "error": f"Document {doc_name} not found"}

    with open(structure_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 递归查找条款
    def find_section_content(nodes, target_id):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            # Check if this is the target section
            title = node.get("title", "")
            if section_id in title or (f"§ {section_id}" in title) or (f"第{section_id}条" in title):
                # 返回完整内容
                content_parts = node.get("content_parts", [])
                if content_parts:
                    full_content = "\n".join(content_parts)
                else:
                    full_content = node.get("summary", title)
                return {
                    "title": title,
                    "content": full_content,
                    "summary": node.get("summary", ""),
                    "page": node.get("page", 0),
                    "section_id": section_id
                }

            # Check sections array
            sections = node.get("sections", []) or node.get("nodes", [])
            if sections:
                result = find_section_content(sections, target_id)
                if result:
                    return result

        return None

    structure = data.get("structure", {})
    if isinstance(structure, dict) and "chapters" in structure:
        content = find_section_content(structure["chapters"], section_id)
    elif isinstance(structure, list):
        content = find_section_content(structure, section_id)
    else:
        content = None

    if content:
        return {
            "status": "ok",
            "doc_name": doc_name,
            "section_id": section_id,
            **content
        }
    else:
        return {
            "status": "not_found",
            "error": f"Section {section_id} not found in {doc_name}"
        }



