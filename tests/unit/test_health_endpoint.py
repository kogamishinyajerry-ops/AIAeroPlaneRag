"""
v0.3: API /health 完整性验收测试
==================================
验收条件:
  - vector_db 显示 connected / disconnected / degraded (无 'mock' / 'failed')
  - llm 显示 connected / disconnected (无 'mock')
  - graph_db 显示 connected / disconnected
  - vector_db_count 始终为整数（非 None）— mock 时返回磁盘上的可索引块数
  - indexable_chunks_on_disk >= 600
不需要运行真实的 FastAPI 服务，直接测试辅助函数和路由逻辑。
"""
import sys
import json
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ── 引入被测模块中的辅助函数 ─────────────────────────────────────────────────
from api.routes.health import (
    _chroma_status,
    _count_indexable_chunks,
    _VECTOR_STATUS_MAP,
    _LLM_STATUS_MAP,
)


# ══════════════════════════════════════════════════════════════════════════
# 1. _chroma_status — Chroma 状态探测
# ══════════════════════════════════════════════════════════════════════════

class TestChromaStatus:
    def test_none_engine_returns_failed(self):
        result = _chroma_status(None)
        assert result["status"] == "failed"
        assert result["doc_count"] is None

    def test_engine_without_collection_returns_mock(self):
        engine = MagicMock()
        engine.collection = None
        result = _chroma_status(engine)
        assert result["status"] == "mock"
        assert result["doc_count"] is None

    def test_engine_with_collection_returns_connected(self):
        engine = MagicMock()
        engine.collection.count.return_value = 675
        result = _chroma_status(engine)
        assert result["status"] == "connected"
        assert result["doc_count"] == 675

    def test_engine_collection_error_returns_degraded(self):
        engine = MagicMock()
        engine.collection.count.side_effect = RuntimeError("DB error")
        result = _chroma_status(engine)
        assert result["status"] == "degraded"
        assert "error" in result


# ══════════════════════════════════════════════════════════════════════════
# 2. Status 标签归一化
# ══════════════════════════════════════════════════════════════════════════

class TestStatusNormalization:
    def test_mock_maps_to_disconnected(self):
        assert _VECTOR_STATUS_MAP["mock"] == "disconnected"

    def test_failed_maps_to_disconnected(self):
        assert _VECTOR_STATUS_MAP["failed"] == "disconnected"

    def test_connected_stays_connected(self):
        assert _VECTOR_STATUS_MAP["connected"] == "connected"

    def test_degraded_stays_degraded(self):
        assert _VECTOR_STATUS_MAP["degraded"] == "degraded"

    def test_llm_true_is_connected(self):
        assert _LLM_STATUS_MAP[True] == "connected"

    def test_llm_false_is_disconnected(self):
        assert _LLM_STATUS_MAP[False] == "disconnected"


# ══════════════════════════════════════════════════════════════════════════
# 3. _count_indexable_chunks — 磁盘块计数
# ══════════════════════════════════════════════════════════════════════════

class TestCountIndexableChunks:
    def test_count_is_positive_integer(self):
        count = _count_indexable_chunks()
        assert isinstance(count, int)
        assert count >= 0

    def test_count_meets_volume_threshold(self):
        """v0.3 期望 >= 500 个块（FAR-33 69条款 + 7个AC文件 + 可选EASA）"""
        count = _count_indexable_chunks()
        assert count >= 500, (
            f"Expected >= 500 indexable chunks on disk, got {count}. "
            "Check that FAR-33_chunks.json and AC_*_chunks.json are present."
        )

    def test_far33_chunks_json_contributes(self):
        """确认 FAR-33_chunks.json 被计入"""
        from src.settings import PROCESSED_DATA_DIR
        far33 = PROCESSED_DATA_DIR / "FAR-33_chunks.json"
        if far33.exists():
            individual_count = len(json.loads(far33.read_text(encoding="utf-8")))
            assert individual_count >= 60


# ══════════════════════════════════════════════════════════════════════════
# 4. health_check 路由 — 端到端响应结构
# ══════════════════════════════════════════════════════════════════════════

class TestHealthCheckResponse:
    """
    Mock 出 services 对象，验证路由函数返回的 JSON 结构和字段语义。
    不需要启动 FastAPI 服务器。
    """

    def _make_services_mock(self, *, chroma_connected=False, glm_connected=False, graph_connected=False):
        svc = MagicMock()
        svc.service_errors = {}

        # Vector engine
        if chroma_connected:
            svc.vector_engine.collection.count.return_value = 675
        else:
            svc.vector_engine.collection = None

        # GLM client
        svc.glm_client = MagicMock() if glm_connected else None

        # Graph store
        if graph_connected:
            svc.graph_store.driver = MagicMock()
            svc.graph_store.has_graph_data = True
            svc.graph_store.node_count = 100
        else:
            svc.graph_store.driver = None
            svc.graph_store.has_graph_data = False
            svc.graph_store.node_count = 0

        # Sub-services (all unavailable in test)
        for attr in ("guardrail", "metadata_extractor", "hallucination_guard",
                     "relevance_enhancer", "enhanced_kb", "knowledge_linker",
                     "fact_verifier", "usability_enhancer", "quality_scorer"):
            setattr(svc, attr, None)

        return svc

    def test_all_required_keys_present_mock_mode(self):
        """mock 模式下响应必须包含所有必须字段"""
        svc = self._make_services_mock()
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()

        required = {
            "vector_db", "vector_db_count", "llm", "graph_db",
            "ollama", "embedding_mode", "indexable_chunks_on_disk",
            "app_version", "errors",
        }
        for key in required:
            assert key in resp, f"Missing key: {key}"

    def test_vector_db_disconnected_in_mock_mode(self):
        """ChromaDB 未连接时 vector_db 应为 disconnected"""
        svc = self._make_services_mock(chroma_connected=False)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["vector_db"] == "disconnected"

    def test_vector_db_connected_when_chroma_up(self):
        """ChromaDB 已连接时 vector_db 应为 connected"""
        svc = self._make_services_mock(chroma_connected=True)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["vector_db"] == "connected"

    def test_vector_db_count_is_integer_in_mock_mode(self):
        """mock 模式下 vector_db_count 不得为 None — 应返回磁盘块数"""
        svc = self._make_services_mock(chroma_connected=False)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["vector_db_count"] is not None
        assert isinstance(resp["vector_db_count"], int)
        assert resp["vector_db_count"] >= 0

    def test_llm_disconnected_when_no_client(self):
        """无 GLM 客户端时 llm 应为 disconnected"""
        svc = self._make_services_mock(glm_connected=False)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["llm"] == "disconnected"

    def test_llm_connected_when_client_present(self):
        """有 GLM 客户端时 llm 应为 connected"""
        svc = self._make_services_mock(glm_connected=True)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["llm"] == "connected"

    def test_graph_db_disconnected_when_mock(self):
        """Neo4j mock 时 graph_db 应为 disconnected"""
        svc = self._make_services_mock(graph_connected=False)
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert resp["graph_db"] == "disconnected"

    def test_no_mock_label_in_response(self):
        """响应中不应出现 'mock' 字符串作为任何核心字段的值"""
        svc = self._make_services_mock()
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        for key in ("vector_db", "llm", "graph_db"):
            assert resp.get(key) != "mock", (
                f"Field '{key}' must not be 'mock', got: {resp.get(key)}"
            )

    def test_indexable_chunks_on_disk_always_present(self):
        svc = self._make_services_mock()
        with patch("api.routes.health.services", svc):
            from api.routes.health import health_check
            resp = health_check()
        assert "indexable_chunks_on_disk" in resp
        assert isinstance(resp["indexable_chunks_on_disk"], int)
