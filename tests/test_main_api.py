from __future__ import annotations

from fastapi.testclient import TestClient


def test_main_health_index_and_query_are_available(main_module, monkeypatch, tmp_path):
    import src.api.dependencies.deps as deps_module

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    (processed_dir / "CCAR-33.md").write_text(
        """# CCAR-33 Sample
## Chapter 1
### Clause 1
The compressor must maintain surge margin.
## Chapter 2
### Clause 2
The turbine disk must pass overspeed tests.
""",
        encoding="utf-8",
    )

    import src.settings as settings_module
    monkeypatch.setattr(settings_module, "PROCESSED_DATA_DIR", processed_dir)
    monkeypatch.setattr(main_module, "CHROMA_DB_DIR", tmp_path / "chroma_db")
    # Disable API auth for testing by clearing the API_KEYS set in all relevant modules
    import sys
    for mod_name in ["src.core.config", "src.api.dependencies.auth"]:
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "API_KEYS"):
                mod.API_KEYS.clear()

    deps_module.services._vector_engine.search_results = [
        {
            "text": "[CCAR-33 Sample > Chapter 1 > Clause 1] The compressor must maintain surge margin.",
            "metadata": {
                "source": "CCAR-33.md",
                "chapter": "Chapter 1",
                "section": "Clause 1",
                "document_id": "doc-001",
                "document_version": "test-v1",
                "content_mode": "mock",
                "source_path": str(processed_dir / "CCAR-33.md"),
            },
        }
    ]


    client = TestClient(main_module.app)
    
    # Mock source catalog for this test
    from src.knowledge_base.source_catalog import KnowledgeSourceCatalog, KnowledgeSource
    from src.api.dependencies.deps import services
    services._source_catalog = KnowledgeSourceCatalog()
    services._source_catalog.sources.append(
        KnowledgeSource(
            id="doc",
            title="Doc",
            authority="TEST",
            jurisdiction="CN",
            layer="core_regulations",
            document_type="Regulation",
            language="zh",
            status="ingested",
            official_url="http://test.com",
            summary="Mock document"
        )
    )

    health = client.get("/api/v1/health")



    assert health.status_code == 200
    health_data = health.json()
    assert health_data["vector_db"] == "connected"
    assert health_data["guardrail"] == "conservative"
    assert health_data["app_version"] == "0.3.0"
    assert health_data["prompt_version"] == "rag-prompt-v2"
    assert health_data["embedding_version"] == "simple-hash-v1"
    assert health_data["graph_version"] == "focused-subgraph-v3"
    assert health_data["source_catalog_version"] == "official-sources-v1"

    index_response = client.post("/api/v1/index")
    assert index_response.status_code == 200
    assert index_response.json()["chunks_indexed"] == 2

    query_response = client.post(
        "/api/v1/query",
        json={
            "query": "What is the surge margin requirement?",
            "top_k": 1,
            "include_graph": False,
        },
    )
    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["retrievalCount"] >= 1
    assert payload["responseMode"] in ("mock", "multi-agent", "standard")
    assert payload["guardrail"]["status"] in ("PASS", "VERIFIED")
    assert len(payload["citations"]) >= 1

    graph_response = client.get("/api/v1/graph/subgraph", params={"center_node": "compressor"})
    assert graph_response.status_code in (200, 404)  # 404 is valid when node not in graph

    source_response = client.get("/api/v1/sources")
    assert source_response.status_code == 200
    source_payload = source_response.json()
    assert source_payload["version"] == "official-sources-v1"
    assert source_payload["total"] >= 1


def test_query_failure_returns_503(main_module):
    import src.api.routes.query as query_module
    import src.api.dependencies.auth as auth_module
    import src.core.config as config_module

    config_module.API_KEYS.clear()
    auth_module.API_KEYS.clear()

    original = query_module.AgentCoordinator.process_query

    async def boom(self, query: str, request_options=None):
        raise RuntimeError("synthetic failure")

    query_module.AgentCoordinator.process_query = boom
    try:
        client = TestClient(main_module.app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/query",
            json={
                "query": "What is the surge margin requirement?",
                "top_k": 1,
                "include_graph": False,
            },
        )
    finally:
        query_module.AgentCoordinator.process_query = original

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "query_processing_failed"
