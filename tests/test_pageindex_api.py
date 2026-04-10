"""
T4.3: PageIndex API 端点集成测试
验证 /api/v1/query/pageindex 端点可调用并返回结构化结果
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def pageindex_client(tmp_path_factory):
    """Create test client with real PageIndex engine."""
    tmp_path = tmp_path_factory.mktemp("pageindex_test")
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    # Copy real structure file to tmp processed dir
    real_structure = Path(__file__).parent.parent / "data/processed/CCAR-33-R2_structure.json"
    if real_structure.exists():
        import shutil
        shutil.copy(real_structure, processed_dir / "CCAR-33-R2_structure.json")

    # Create minimal markdown file for indexing
    (processed_dir / "CCAR-33.md").write_text(
        "# CCAR-33\n## Chapter 1\n### Clause 1\nTest content.\n",
        encoding="utf-8",
    )

    # Import main with patched dirs
    import importlib
    import sys as _sys
    for mod in list(_sys.modules.keys()):
        if mod == "src.main":
            del _sys.modules[mod]

    import src.main as main_module
    main_module.PROCESSED_DATA_DIR = processed_dir
    main_module.CHROMA_DB_DIR = tmp_path / "chroma_db"

    # Disable auth
    for mod_name in ["src.core.config", "src.api.dependencies.auth"]:
        if mod_name in _sys.modules:
            mod = _sys.modules[mod_name]
            if hasattr(mod, "API_KEYS"):
                mod.API_KEYS.clear()

    # Initialize pageindex engine in deps
    from src.rag.pageindex_engine import PageIndexEngine
    from src.api.dependencies.deps import services
    structure_path = processed_dir / "CCAR-33-R2_structure.json"
    if structure_path.exists():
        services._pageindex_engine = PageIndexEngine(str(structure_path))
    else:
        services._pageindex_engine = None

    # Patch client fixture to also return services for inspection
    return TestClient(main_module.app), services


class TestPageIndexEndpoint:
    def test_pageindex_endpoint_exists(self, pageindex_client):
        client, services = pageindex_client
        if services._pageindex_engine is None:
            pytest.skip("PageIndex engine not available (structure file missing)")

        response = client.post(
            "/api/v1/query/pageindex",
            json={"query": "压气机喘振裕度", "top_k": 3},
        )
        assert response.status_code == 200

    def test_pageindex_returns_query_response_schema(self, pageindex_client):
        client, services = pageindex_client
        if services._pageindex_engine is None:
            pytest.skip("PageIndex engine not available")

        response = client.post(
            "/api/v1/query/pageindex",
            json={"query": "涡轮叶片", "top_k": 3},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "query" in payload
        assert "answer" in payload
        assert "citations" in payload
        assert "responseMode" in payload

    def test_pageindex_response_mode_is_pageindex(self, pageindex_client):
        client, services = pageindex_client
        if services._pageindex_engine is None:
            pytest.skip("PageIndex engine not available")

        response = client.post(
            "/api/v1/query/pageindex",
            json={"query": "燃油系统", "top_k": 3},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["responseMode"] == "pageindex"

    def test_pageindex_returns_citations(self, pageindex_client):
        client, services = pageindex_client
        if services._pageindex_engine is None:
            pytest.skip("PageIndex engine not available")

        response = client.post(
            "/api/v1/query/pageindex",
            json={"query": "涡轮", "top_k": 3},
        )
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["citations"], list)

    def test_pageindex_503_when_engine_unavailable(self, pageindex_client):
        client, services = pageindex_client
        # Temporarily disable engine
        original = services._pageindex_engine
        services._pageindex_engine = None
        try:
            response = client.post(
                "/api/v1/query/pageindex",
                json={"query": "test", "top_k": 3},
            )
            assert response.status_code == 503
        finally:
            services._pageindex_engine = original
