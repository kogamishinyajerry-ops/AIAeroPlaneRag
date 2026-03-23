from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from settings import SOURCE_CATALOG_PATH, SOURCE_CATALOG_VERSION


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
    document_url: str | None = None
    local_path: str | None = None
    summary: str
    tags: list[str] = Field(default_factory=list)


class KnowledgeSourceCatalog(BaseModel):
    version: str = SOURCE_CATALOG_VERSION
    sources: list[KnowledgeSource] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> "KnowledgeSourceCatalog":
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

    def filter(self, *, layer: str | None = None, jurisdiction: str | None = None) -> list[KnowledgeSource]:
        items = self.sources
        if layer:
            items = [item for item in items if item.layer == layer]
        if jurisdiction:
            items = [item for item in items if item.jurisdiction.lower() == jurisdiction.lower()]
        return items

