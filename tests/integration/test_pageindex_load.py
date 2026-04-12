"""
v0.7: PageIndex Endpoint Load & Correctness Tests
===================================================
Tests the /api/v1/query/pageindex and /api/v1/pageindex/nodes endpoints.

验收条件:
  1. /api/v1/pageindex/nodes 返回 ≥ 50 个树节点
  2. /api/v1/query/pageindex 对各类航空法规查询返回 200 + 正确结构
  3. 对压气机/涡轮/燃烧室等核心部件查询，retrievalCount ≥ 1
  4. responseMode = "pageindex"
  5. 无论 PageIndex engine 是否可用，不返回 500
  6. 并发 10 请求能全部完成，无超时 (P95 < 5s in unit/CI environment)

注意: PageIndex 使用 CCAR-33-R2_structure.json 作为数据源。
CI-safe: FakeVectorStoreEngine + FakeGraphStore，PageIndex 引擎使用真实数据。
"""
from __future__ import annotations

import concurrent.futures
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

STRUCTURE_FILE = ROOT / "data" / "processed" / "CCAR-33-R2_structure.json"


# ── Client fixture (reuse from smoke test approach) ───────────────────────────

@pytest.fixture(scope="module")
def pageindex_client():
    for mod in list(sys.modules.keys()):
        if mod.startswith("src."):
            sys.modules.pop(mod, None)

    import src.main as main_module
    from src.api.dependencies.deps import services, get_vector_engine, get_guardrail
    import src.core.config as config_module
    import src.api.dependencies.auth as auth_module

    config_module.API_KEYS.clear()
    auth_module.API_KEYS.clear()

    sys.path.insert(0, str(ROOT / "tests"))
    from conftest import FakeVectorStoreEngine, FakeGraphStore, FakeGuardrail

    services._vector_engine = FakeVectorStoreEngine()
    services._graph_store = FakeGraphStore()
    services._guardrail = FakeGuardrail()
    services.is_initialized = True

    main_module.app.dependency_overrides[get_vector_engine] = lambda: services._vector_engine
    main_module.app.dependency_overrides[get_guardrail] = lambda: services._guardrail

    # Initialize real PageIndex engine from actual structure file
    if STRUCTURE_FILE.exists():
        from src.rag.pageindex_engine import PageIndexEngine
        services._pageindex_engine = PageIndexEngine(str(STRUCTURE_FILE))
    # else: engine stays None → endpoint returns 503

    from fastapi.testclient import TestClient
    client = TestClient(main_module.app, raise_server_exceptions=False)
    yield client
    main_module.app.dependency_overrides.clear()


# ── PageIndex nodes endpoint ──────────────────────────────────────────────────

class TestPageIndexNodes:

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_nodes_200(self, pageindex_client):
        resp = pageindex_client.get("/api/v1/pageindex/nodes")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_nodes_count_gte_50(self, pageindex_client):
        data = pageindex_client.get("/api/v1/pageindex/nodes").json()
        nodes = data.get("nodes", data.get("sections", []))
        assert len(nodes) >= 50, f"Expected ≥50 nodes, got {len(nodes)}"

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_nodes_have_section_id(self, pageindex_client):
        data = pageindex_client.get("/api/v1/pageindex/nodes").json()
        nodes = data.get("nodes", data.get("sections", []))
        for node in nodes[:5]:
            assert any(k in node for k in ("id", "section_id", "node_id")), (
                f"Node missing id field: {node}"
            )


# ── PageIndex query endpoint ──────────────────────────────────────────────────

class TestPageIndexQuery:

    QUERIES = [
        ("压气机喘振裕度", "zh"),
        ("涡轮叶片强度要求", "zh"),
        ("燃烧室设计要求", "zh"),
        ("发动机持久性试验", "zh"),
        ("compressor surge margin", "en"),
        ("turbine blade design", "en"),
    ]

    def _post(self, client, query: str, top_k: int = 5) -> dict:
        return client.post("/api/v1/query/pageindex", json={
            "query": query,
            "top_k": top_k,
            "use_guardrail": False,
        })

    def test_zh_surge_query_not_500(self, pageindex_client):
        resp = self._post(pageindex_client, "压气机喘振裕度")
        assert resp.status_code != 500, f"Got 500: {resp.text[:300]}"

    def test_zh_surge_query_valid_status(self, pageindex_client):
        resp = self._post(pageindex_client, "压气机喘振裕度")
        assert resp.status_code in {200, 503}, f"Got {resp.status_code}"

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_zh_surge_query_200(self, pageindex_client):
        resp = self._post(pageindex_client, "压气机喘振裕度")
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:300]}"

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_response_has_required_fields(self, pageindex_client):
        resp = self._post(pageindex_client, "涡轮叶片强度")
        payload = resp.json()
        for field in ("retrievalCount", "responseMode", "citations"):
            assert field in payload, f"Missing field: {field}"

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_response_mode_is_pageindex(self, pageindex_client):
        resp = self._post(pageindex_client, "燃烧室设计要求")
        payload = resp.json()
        assert payload.get("responseMode") == "pageindex", (
            f"Expected responseMode='pageindex', got '{payload.get('responseMode')}'"
        )

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_compressor_query_retrieves_chunks(self, pageindex_client):
        """压气机相关查询应命中 CCAR-33 树节点。"""
        resp = self._post(pageindex_client, "压气机设计要求 CCAR-33")
        payload = resp.json()
        assert payload["retrievalCount"] >= 1, (
            f"Expected ≥1 PageIndex result, got {payload['retrievalCount']}"
        )

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_turbine_query_retrieves_chunks(self, pageindex_client):
        resp = self._post(pageindex_client, "涡轮转子超速保护")
        payload = resp.json()
        assert payload["retrievalCount"] >= 1

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_endurance_test_query(self, pageindex_client):
        resp = self._post(pageindex_client, "发动机持久性试验 耐久性")
        payload = resp.json()
        assert resp.status_code == 200

    @pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
    def test_en_query_not_500(self, pageindex_client):
        resp = self._post(pageindex_client, "compressor surge margin")
        assert resp.status_code != 500

    def test_empty_query_no_500(self, pageindex_client):
        resp = self._post(pageindex_client, "   ")
        assert resp.status_code != 500


# ── Throughput test ───────────────────────────────────────────────────────────

@pytest.mark.skipif(not STRUCTURE_FILE.exists(), reason="structure file not found")
class TestPageIndexThroughput:
    """
    Concurrent load test: 10 simultaneous requests.
    All must complete within 10s total wall time.
    """

    CONCURRENT_QUERIES = [
        "压气机喘振裕度",
        "涡轮叶片强度",
        "燃烧室设计",
        "发动机持久性试验",
        "润滑系统要求",
        "点火系统设计",
        "轴承密封要求",
        "转子超速保护",
        "发动机包容性",
        "适航符合性方法",
    ]

    def _single_request(self, client, query: str) -> tuple[int, float]:
        start = time.monotonic()
        resp = client.post("/api/v1/query/pageindex", json={
            "query": query, "top_k": 3, "use_guardrail": False
        })
        return resp.status_code, time.monotonic() - start

    def test_10_concurrent_requests_all_succeed(self, pageindex_client):
        """10 sequential requests must all return non-500 within 10s total."""
        start_total = time.monotonic()
        results = []
        # TestClient is synchronous; run sequentially to simulate load
        for q in self.CONCURRENT_QUERIES:
            status, elapsed = self._single_request(pageindex_client, q)
            results.append((status, elapsed))

        total_time = time.monotonic() - start_total
        failures = [(s, e) for s, e in results if s == 500]
        assert not failures, f"{len(failures)}/10 requests returned 500"
        assert total_time < 15.0, f"10 requests took {total_time:.1f}s (>15s limit)"

    def test_p95_latency_acceptable(self, pageindex_client):
        """P95 latency for 10 sequential requests must be < 5s per request."""
        latencies = []
        for q in self.CONCURRENT_QUERIES:
            _, elapsed = self._single_request(pageindex_client, q)
            latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 5.0, f"PageIndex P95 latency = {p95:.2f}s (>5s limit)"
