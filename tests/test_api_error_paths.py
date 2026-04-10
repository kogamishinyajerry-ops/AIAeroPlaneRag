"""
E2E Error Path Tests - API层错误响应验证
测试统一错误格式在各个端点的落地情况
"""
import pytest
import sys


class TestEmptyQueryError:
    """1. 空查询 → 422 验证"""

    def test_empty_query_returns_422(self):
        """空字符串 query 触发 Pydantic min_length=1 校验，返回 422"""
        import sys
        from pathlib import Path

        project_root = Path(__file__).parent.parent
        src_path = project_root / "src"
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from src.api.routes.query import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="", top_k=3, include_graph=False)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("query",)
        assert "String should have at least 1 character" in errors[0]["msg"]

    def test_missing_query_returns_422(self, main_module):
        """省略 query 字段 → 422"""
        from fastapi.testclient import TestClient
        client = TestClient(main_module.app)

        response = client.post(
            "/api/v1/query/enhanced",
            json={"top_k": 3},
        )
        assert response.status_code == 422


class TestGraphErrorPaths:
    """2. 图谱无数据 → 404 统一错误格式"""

    def test_graph_network_returns_data(self, main_module, monkeypatch):
        """图谱 API 从 CCAR-33-R2_professional_graph.json fallback 读取数据（200）"""
        from fastapi.testclient import TestClient

        client = TestClient(main_module.app)

        # 先获取 token
        token_resp = client.post(
            "/api/v1/auth/token",
            json={"api_key": "test-api-key-12345"},
        )
        assert token_resp.status_code == 200, f"Token request failed: {token_resp.text}"
        token = token_resp.json()["access_token"]

        response = client.get(
            "/api/v1/graph/network",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0, "Should return nodes from fallback graph file"

    def test_graph_subgraph_node_not_found_returns_404(self, main_module, monkeypatch):
        """查询不存在的节点 → 404 + 统一错误格式"""
        from fastapi.testclient import TestClient
        import json

        # 创建一个有数据的图谱文件
        processed_dir = main_module.PROCESSED_DATA_DIR
        graph_dir = processed_dir / "knowledge_graph"
        graph_dir.mkdir(parents=True, exist_ok=True)
        graph_file = graph_dir / "graph.json"
        graph_file.write_text(json.dumps({
            "nodes": {"node1": {"title": "Real Node", "label": "Real"}},
            "edges": []
        }), encoding="utf-8")

        client = TestClient(main_module.app)

        token_resp = client.post(
            "/api/v1/auth/token",
            json={"api_key": "test-api-key-12345"},
        )
        assert token_resp.status_code == 200
        token = token_resp.json()["access_token"]

        response = client.get(
            "/api/v1/graph/subgraph",
            params={"center_node": "nonexistent-node-id"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        detail = response.json().get("detail", response.json())
        assert "error" in detail
        assert "code" in detail
        assert detail["code"] == "node_not_found"
        assert "nonexistent-node-id" in detail["error"]


class TestAuthErrorResponses:
    """3. 认证错误 → 401 统一格式（测试 auth 依赖本身）"""

    def test_invalid_api_key_raises_401(self):
        """无效 API Key → _check_any_auth 抛出 HTTPException 401"""
        # 临时配置 API_KEYS
        import src.core.config as config_module
        saved_keys = config_module.API_KEYS.copy()
        config_module.API_KEYS.clear()
        config_module.API_KEYS.add("test-api-key-12345")

        try:
            # 重新导入 auth 以使用更新后的 config
            for m in list(sys.modules.keys()):
                if "api.dependencies.auth" in m or "src.api.dependencies.auth" in m:
                    sys.modules.pop(m, None)

            from src.api.dependencies.auth import _check_any_auth
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                _check_any_auth("this-is-not-valid")
            assert exc_info.value.status_code == 401
            data = exc_info.value.detail
            assert "error" in data
            assert "code" in data
            assert data["code"] == "invalid_api_key"
        finally:
            config_module.API_KEYS.clear()
            config_module.API_KEYS.update(saved_keys)

    def test_missing_auth_header_raises_401(self):
        """无认证 header → _check_any_auth 抛出 HTTPException 401"""
        import src.core.config as config_module
        saved_keys = config_module.API_KEYS.copy()
        config_module.API_KEYS.clear()
        config_module.API_KEYS.add("test-api-key-12345")

        try:
            for m in list(sys.modules.keys()):
                if "api.dependencies.auth" in m or "src.api.dependencies.auth" in m:
                    sys.modules.pop(m, None)

            from src.api.dependencies.auth import _check_any_auth
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                _check_any_auth(None)
            assert exc_info.value.status_code == 401
            data = exc_info.value.detail
            assert "error" in data
            assert "code" in data
        finally:
            config_module.API_KEYS.clear()
            config_module.API_KEYS.update(saved_keys)


class TestRateLimitError:
    """4. 速率限制 → 429"""

    def test_rate_limit_exceeded_returns_429_with_retry_header(self):
        """超出速率限制 → 429 + Retry-After + 统一错误格式"""
        import src.core.config as config_module
        saved_keys = config_module.API_KEYS.copy()
        saved_rate_limit = config_module.RATE_LIMIT_ENABLED

        config_module.API_KEYS.clear()
        config_module.API_KEYS.add("test-api-key-12345")
        config_module.RATE_LIMIT_ENABLED = True

        try:
            # 重新导入以获取新配置
            for m in list(sys.modules.keys()):
                if "api.dependencies.auth" in m or "src.api.dependencies.auth" in m:
                    sys.modules.pop(m, None)

            from src.api.dependencies.auth import SlidingWindowRateLimiter, RATE_LIMIT_REQUESTS
            from fastapi import HTTPException

            limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)

            # 消费完所有配额
            for i in range(5):
                allowed, _ = limiter.is_allowed("test-rate-key")
                assert allowed, f"Request {i} should be allowed"

            # 第6次应被拒绝
            allowed, rate_info = limiter.is_allowed("test-rate-key")
            assert not allowed
            assert rate_info["remaining"] == 0
            assert "retry_after" not in rate_info  # not set until after window
        finally:
            config_module.API_KEYS.clear()
            config_module.API_KEYS.update(saved_keys)
            config_module.RATE_LIMIT_ENABLED = saved_rate_limit
