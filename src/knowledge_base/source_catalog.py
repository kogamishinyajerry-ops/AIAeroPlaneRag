from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.settings import SOURCE_CATALOG_PATH, SOURCE_CATALOG_VERSION


SourceLayer = Literal["core_regulations", "certification_guidance", "environment_and_lifecycle"]
SourceStatus = Literal["cataloged", "seeded", "ingested"]


class KnowledgeSource(BaseModel):
    id: str
    title: str
    authority: str
    jurisdiction: str
    layer: SourceLayer
    document_type: str
    language: str
    status: SourceStatus
    official_url: str
    document_url: Optional[str] = None
    local_path: Optional[str] = None
    summary: str
    tags: List[str] = Field(default_factory=list)


class KnowledgeSourceCatalog(BaseModel):
    version: str = SOURCE_CATALOG_VERSION
    sources: List[KnowledgeSource] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "KnowledgeSourceCatalog":
        catalog_path = path or SOURCE_CATALOG_PATH
        if not catalog_path.exists():
            return cls()

        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        return cls.model_validate(payload)

    def grouped(self) -> list[dict]:
        layer_titles = {
            "core_regulations": "Layer 1 - Core Regulations",
            "certification_guidance": "Layer 2 - Certification Guidance",
            "environment_and_lifecycle": "Layer 3 - Environment & Lifecycle",
        }
        groups = []
        for layer, title in layer_titles.items():
            items = [source for source in self.sources if source.layer == layer]
            groups.append(
                {
                    "layer": layer,
                    "title": title,
                    "count": len(items),
                    "sources": [source.model_dump() for source in items],
                }
            )
        return groups

    def filter(self, *, layer: Optional[str] = None, jurisdiction: Optional[str] = None) -> List[KnowledgeSource]:
        items = self.sources
        if layer:
            items = [item for item in items if item.layer == layer]
        if jurisdiction:
            items = [item for item in items if item.jurisdiction.lower() == jurisdiction.lower()]
        return items

    def get_by_id(self, doc_id: str) -> Optional[KnowledgeSource]:
        """根据文档ID查找知识源"""
        import re
        # doc_id可能是完整ID如"caac-ccar-33-r2"或包含路径如"CCAR-33-R2_chapters/..."
        # 使用正则提取基础ID（去掉_chapters/...和.md后缀）
        doc_id_clean = re.sub(r"_chapters/.*$", "", doc_id).replace(".md", "").strip()
        doc_id_lower = doc_id_clean.lower()
        for source in self.sources:
            if source.id.lower() == doc_id_lower:
                return source
            # 也检查是否以ID开头（处理CCAR-33-R2_xxx这样的情况）
            if source.id.lower() in doc_id_lower:
                return source
        return None

    def get_source_url(self, doc_id: str) -> Optional[str]:
        """获取文档的官方链接"""
        source = self.get_by_id(doc_id)
        if source:
            return source.official_url or source.document_url
        return None
