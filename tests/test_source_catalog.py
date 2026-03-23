from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from knowledge_base.source_catalog import KnowledgeSourceCatalog


def test_source_catalog_loads_seeded_official_sources():
    catalog = KnowledgeSourceCatalog.load()

    assert catalog.version == "official-sources-v1"
    assert len(catalog.sources) >= 8
    assert any(source.id == "caac-ccar-21-r5" for source in catalog.sources)
    assert any(source.id == "faa-part-33" for source in catalog.sources)
    assert any(source.id == "easa-cs-e-amd6" for source in catalog.sources)
