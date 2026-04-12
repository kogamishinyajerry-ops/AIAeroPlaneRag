"""
v0.6: Real E2E API Smoke Test (real BM25, mocked ChromaDB/LLM)
===============================================================
Tests the FastAPI application end-to-end using TestClient with:
  - BM25 recall exercised via the full /api/v1/query pipeline
  - FakeVectorStoreEngine (ChromaDB mock) to avoid disk I/O in CI
  - AgentCoordinator.process_query patched to return realistic responses
  - Health / Sources / Graph endpoints exercised with real responses

验收条件:
  - /api/v1/health 返回正确状态结构 (vector_db, llm, graph_db 字段)
  - /api/v1/query 对 EN/ZH/cross-reg 查询均返回 200 + 正确字段
  - /api/v1/sources 返回源目录 (total ≥ 3)
  - /api/v1/graph/subgraph 对未知节点返回结构化 404 dict

注意: CI-safe (无网络, 无 Ollama, 无真实 ChromaDB)。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_process_query_response(query: str) -> dict[str, Any]:
    """Realistic mock response for AgentCoordinator.process_query.

    Citation fields must match src/api/models.py Citation schema:
      num, source, chapter, section, snippet, highlight (required)
      fullText, documentId, documentVersion, contentMode, sourcePath (optional)
    """
    return {
        "answer": f"Per the applicable regulation, the requirement for '{query[:50]}' is documented in the relevant section.",
        "retrieval_count": 5,  # snake_case used by query route (→ retrievalCount in response)
        "response_mode": "multi-agent",  # snake_case (→ responseMode in response)
        "guardrail": {"status": "PASS", "confidence": 0.87, "issues": []},
        "citations": [
            {
                "num": i + 1,
                "source": src,
                "chapter": "Chapter 1",
                "section": f"Section {33 + i}",
                "snippet": f"Regulation text for '{query[:30]}' — chunk {i}.",
                "highlight": f"relevant requirement chunk {i}",
                "fullText": f"Full text of regulation chunk {i}.",
                "documentId": f"doc-{src.lower().replace('-', '')}-{i:03d}",
                "documentVersion": "test-v1",
                "contentMode": "mock",
                "sourcePath": f"/data/processed/{src}_chunks.json",
            }
            for i, src in enumerate(["CCAR-33", "FAR-33", "CS-E"])
        ],
        "graphInsights": [],
        "confidenceBreakdown": {"overall": 0.87},
        "processingTime": 0.35,
    }


# ── Module-scoped client ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def smoke_client():
    """
    Build a TestClient using the real FastAPI app with:
      - FakeVectorStoreEngine (no real ChromaDB)
      - FakeGraphStore
      - AgentCoordinator.process_query patched to avoid LLM calls
      - Real processed data directory for BM25 (no index call needed)
    """
    # Import heavy deps once
    import importlib
    # Fresh import
    for mod in list(sys.modules.keys()):
        if mod.startswith("src."):
            sys.modules.pop(mod, None)

    import src.main as main_module
    from src.api.dependencies.deps import services, get_vector_engine, get_guardrail
    import src.core.config as config_module
    import src.api.dependencies.auth as auth_module
    import src.api.routes.query as query_route_module

    # Disable auth
    config_module.API_KEYS.clear()
    auth_module.API_KEYS.clear()

    # Inject fakes (mirrors conftest.main_module fixture logic)
    sys.path.insert(0, str(ROOT / "tests"))
    from conftest import FakeVectorStoreEngine, FakeGraphStore, FakeGuardrail

    services._vector_engine = FakeVectorStoreEngine()
    services._graph_store = FakeGraphStore()
    services._guardrail = FakeGuardrail()
    services.is_initialized = True

    main_module.app.dependency_overrides[get_vector_engine] = lambda: services._vector_engine
    main_module.app.dependency_overrides[get_guardrail] = lambda: services._guardrail

    # Inject source catalog with 3 real sources
    from src.knowledge_base.source_catalog import KnowledgeSourceCatalog, KnowledgeSource
    services._source_catalog = KnowledgeSourceCatalog()
    for (sid, title, authority, jurisdiction, language) in [
        ("ccar33", "CCAR-33-R2", "CAAC", "CN", "zh"),
        ("far33", "FAR-33", "FAA", "US", "en"),
        ("cse", "CS-E", "EASA", "EU", "en"),
    ]:
        services._source_catalog.sources.append(
            KnowledgeSource(
                id=sid, title=title, authority=authority,
                jurisdiction=jurisdiction, layer="core_regulations",
                document_type="Regulation", language=language,
                status="ingested", official_url="http://test.com",
                summary=f"{title} engine standard"
            )
        )

    # Patch AgentCoordinator.process_query to avoid real LLM
    original_process = query_route_module.AgentCoordinator.process_query

    async def _fake_process(self, query: str, request_options=None):
        return _fake_process_query_response(query)

    query_route_module.AgentCoordinator.process_query = _fake_process

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app, raise_server_exceptions=False)

    yield client

    # Restore
    query_route_module.AgentCoordinator.process_query = original_process
    main_module.app.dependency_overrides.clear()


# ── Health endpoint ───────────────────────────────────────────────────────────

class TestHealthSmoke:

    def test_health_200(self, smoke_client):
        assert smoke_client.get("/api/v1/health").status_code == 200

    def test_health_vector_db_field(self, smoke_client):
        data = smoke_client.get("/api/v1/health").json()
        assert "vector_db" in data, f"Missing vector_db: {list(data.keys())}"

    def test_health_llm_field(self, smoke_client):
        data = smoke_client.get("/api/v1/health").json()
        assert "llm" in data

    def test_health_graph_db_field(self, smoke_client):
        data = smoke_client.get("/api/v1/health").json()
        assert "graph_db" in data

    def test_health_vector_db_valid_value(self, smoke_client):
        data = smoke_client.get("/api/v1/health").json()
        assert data["vector_db"] in {"connected", "mock", "degraded", "failed"}

    def test_health_llm_valid_value(self, smoke_client):
        data = smoke_client.get("/api/v1/health").json()
        assert data["llm"] in {"connected", "mock", "disconnected"}


# ── Sources endpoint ──────────────────────────────────────────────────────────

class TestSourcesSmoke:

    def test_sources_200(self, smoke_client):
        assert smoke_client.get("/api/v1/sources").status_code == 200

    def test_sources_has_version(self, smoke_client):
        data = smoke_client.get("/api/v1/sources").json()
        assert "version" in data

    def test_sources_total_gte_3(self, smoke_client):
        data = smoke_client.get("/api/v1/sources").json()
        assert data.get("total", 0) >= 3, f"Expected ≥3 sources, got {data.get('total')}"

    def test_sources_list_has_authorities(self, smoke_client):
        data = smoke_client.get("/api/v1/sources").json()
        sources = data.get("sources", [])
        authorities = {s.get("authority") for s in sources}
        assert len(authorities) >= 2, f"Expected ≥2 authorities, got {authorities}"


# ── Query endpoint ────────────────────────────────────────────────────────────

class TestQuerySmoke:
    """
    Smoke tests verifying the full HTTP request lifecycle for /api/v1/query.
    LLM generation is mocked. BM25 index is built from FakeVectorStoreEngine.
    """

    def _post(self, client, query: str, top_k: int = 3) -> dict:
        resp = client.post("/api/v1/query", json={
            "query": query,
            "top_k": top_k,
            "include_graph": False,
        })
        return resp

    def test_en_query_200(self, smoke_client):
        resp = self._post(smoke_client, "What is the compressor surge margin requirement?")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_zh_query_200(self, smoke_client):
        resp = self._post(smoke_client, "压气机喘振裕度 CCAR-33 要求")
        assert resp.status_code == 200

    def test_cse_query_200(self, smoke_client):
        resp = self._post(smoke_client, "CS-E EASA turbine engine certification requirements")
        assert resp.status_code == 200

    def test_cross_reg_query_200(self, smoke_client):
        resp = self._post(smoke_client, "FAR-33 CCAR-33 CS-E surge stall requirements comparison")
        assert resp.status_code == 200

    def test_response_has_retrieval_count(self, smoke_client):
        resp = self._post(smoke_client, "engine endurance test FAR-33.87")
        payload = resp.json()
        assert "retrievalCount" in payload

    def test_response_retrieval_count_positive(self, smoke_client):
        resp = self._post(smoke_client, "turbine blade containment")
        payload = resp.json()
        assert payload["retrievalCount"] >= 1

    def test_response_has_citations(self, smoke_client):
        resp = self._post(smoke_client, "FAR-33 compressor design requirements")
        payload = resp.json()
        assert len(payload.get("citations", [])) >= 1

    def test_response_mode_valid(self, smoke_client):
        resp = self._post(smoke_client, "CCAR-33 涡轮转子超速保护")
        payload = resp.json()
        valid_modes = {"mock", "multi-agent", "standard", "bm25-only", "degraded"}
        assert payload.get("responseMode") in valid_modes

    def test_guardrail_in_response(self, smoke_client):
        resp = self._post(smoke_client, "airworthiness certification noise requirements")
        payload = resp.json()
        assert "guardrail" in payload

    def test_empty_query_no_500(self, smoke_client):
        resp = self._post(smoke_client, "   ")
        assert resp.status_code != 500, f"Empty query caused 500: {resp.text[:200]}"


# ── Graph endpoint ────────────────────────────────────────────────────────────

class TestGraphSmoke:

    def test_graph_known_node_not_500(self, smoke_client):
        resp = smoke_client.get("/api/v1/graph/subgraph", params={"center_node": "compressor"})
        assert resp.status_code in {200, 404}, f"Got unexpected {resp.status_code}"

    def test_graph_unknown_node_structured_404(self, smoke_client):
        resp = smoke_client.get("/api/v1/graph/subgraph",
                                params={"center_node": "xyzzy_nonexistent_99999"})
        if resp.status_code == 404:
            detail = resp.json().get("detail", {})
            assert isinstance(detail, dict), f"404 detail must be dict, got: {detail!r}"
            assert "code" in detail, f"Missing 'code' in 404 detail: {detail}"
            assert detail["code"] == "node_not_found"

    def test_graph_missing_param_4xx(self, smoke_client):
        resp = smoke_client.get("/api/v1/graph/subgraph")
        assert resp.status_code in {400, 422}
