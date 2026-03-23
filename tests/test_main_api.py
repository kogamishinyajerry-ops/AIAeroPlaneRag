from __future__ import annotations

from fastapi.testclient import TestClient


def test_main_health_index_and_query_are_available(main_module, monkeypatch, tmp_path):
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

    monkeypatch.setattr(main_module, "PROCESSED_DATA_DIR", processed_dir)
    monkeypatch.setattr(main_module, "CHROMA_DB_DIR", tmp_path / "chroma_db")

    main_module.vector_engine.search_results = [
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
            "use_guardrail": True,
            "include_graph_subgraph": False,
        },
    )
    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["retrievalCount"] == 1
    assert payload["appVersion"] == "0.3.0"
    assert payload["knowledgeBaseVersion"] == "ccar33-enriched-mock-v1"
    assert payload["promptVersion"] == "rag-prompt-v2"
    assert payload["embeddingVersion"] == "simple-hash-v1"
    assert payload["graphVersion"] == "focused-subgraph-v3"
    assert payload["responseMode"] == "mock"
    assert payload["guardrail"]["status"] == "PASS"
    assert payload["citations"][0]["section"] == "Clause 1"
    assert payload["citations"][0]["documentVersion"] == "test-v1"
    assert payload["graphSubgraph"] is None

    graph_response = client.get("/api/v1/graph/subgraph", params={"query": "compressor"})
    assert graph_response.status_code == 200
    assert graph_response.json()["summary"] == "test graph subgraph"

    source_response = client.get("/api/v1/sources")
    assert source_response.status_code == 200
    source_payload = source_response.json()
    assert source_payload["version"] == "official-sources-v1"
    assert source_payload["total"] >= 1
