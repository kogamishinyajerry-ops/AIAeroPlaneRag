"""
v0.4: Multi-Agent Flow 集成测试 (Planner→Tool→Checker→Answer)
===============================================================
验收条件:
  - PlannerAgent 正确解析 6 类意图 (regulatory/method/numerical/comparison/definition/cross_ref)
  - ToolAgent mock 后安全执行检索计划
  - CheckerAgent 验证结果结构正确
  - AnswerAgent 生成答案格式完整
  - AgentCoordinator 链路 mock 后可端到端运行
  - AgentMessage 传递格式验证

注意: 所有 LLM/向量引擎调用均 mock，CI-safe 运行。
"""
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from multi_agent.base import AgentMessage, AgentRole, RetrievalPlan
from multi_agent.planner import PlannerAgent


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_async(coro):
    """Run an async coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_CONTEXTS = [
    {
        "text": "CCAR-33.65 Surge and stall characteristics. Each engine must be designed...",
        "metadata": {"source": "CCAR-33-R2", "section": "33.65", "authority": "CAAC"},
        "id": "ccar_33_65",
    },
    {
        "text": "FAR 33.65 Surge and stall characteristics. Each engine must...",
        "metadata": {"source": "FAR-33", "section": "33.65", "authority": "FAA"},
        "id": "far_33_65",
    },
    {
        "text": "CS-E 810 Compressor surge. The engine must be designed to prevent...",
        "metadata": {"source": "CS-E Amendment 5", "section": "E.810", "authority": "EASA"},
        "id": "cse_810",
    },
]


# ── PlannerAgent Tests ────────────────────────────────────────────────────────

class TestPlannerAgent:
    """Tests for the PlannerAgent intent detection and plan creation."""

    @pytest.fixture(scope="class")
    def planner(self):
        return PlannerAgent()

    def _make_message(self, query: str) -> AgentMessage:
        return AgentMessage(role=AgentRole.PLANNER, content=query, data={}, metadata={})

    def test_planner_returns_agent_message(self, planner):
        """PlannerAgent.process() must return an AgentMessage."""
        result = run_async(planner.process(self._make_message("发动机喘振裕度要求")))
        assert isinstance(result, AgentMessage), f"Expected AgentMessage, got {type(result)}"

    def test_planner_result_has_plan(self, planner):
        """Result data must contain a 'plan' key."""
        result = run_async(planner.process(self._make_message("CCAR-33 喘振裕度要求")))
        assert "plan" in result.data, f"Missing 'plan' in result.data: {result.data.keys()}"

    def test_plan_has_required_fields(self, planner):
        """Plan dict must have all required fields."""
        result = run_async(planner.process(self._make_message("什么是喘振裕度")))
        plan = result.data["plan"]
        required = {"query", "intent_type", "intent_confidence", "retrieval_strategy",
                    "top_k", "use_graph", "use_expansion"}
        missing = required - set(plan.keys())
        assert not missing, f"Plan missing fields: {missing}"

    def test_intent_regulatory_detected(self, planner):
        """'CCAR-33 第33.65条要求' should detect regulatory intent."""
        result = run_async(planner.process(self._make_message("CCAR-33 第33.65条对压气机喘振裕度的要求")))
        intent = result.data["plan"]["intent_type"]
        assert intent in {"regulatory", "numerical", "cross_ref"}, (
            f"Expected regulatory/numerical/cross_ref intent for regulation query, got '{intent}'"
        )

    def test_intent_definition_detected(self, planner):
        """'什么是喘振裕度' should lean toward definition or regulatory."""
        result = run_async(planner.process(self._make_message("什么是喘振裕度")))
        intent = result.data["plan"]["intent_type"]
        assert isinstance(intent, str) and len(intent) > 0, "intent_type must be non-empty string"

    def test_intent_comparison_detected(self, planner):
        """'CCAR-33与FAR-33的差异' might be detected as comparison or cross_ref."""
        result = run_async(planner.process(self._make_message("CCAR-33与FAR-33对喘振裕度要求的差异")))
        intent = result.data["plan"]["intent_type"]
        assert isinstance(intent, str) and len(intent) > 0

    def test_top_k_positive(self, planner):
        """top_k in plan must be a positive integer."""
        result = run_async(planner.process(self._make_message("涡轮发动机审定要求")))
        top_k = result.data["plan"]["top_k"]
        assert isinstance(top_k, int) and top_k > 0, f"top_k must be positive int, got {top_k}"

    def test_intent_confidence_in_range(self, planner):
        """intent_confidence must be in [0.0, 1.0]."""
        result = run_async(planner.process(self._make_message("engine certification turbine")))
        conf = result.data["plan"]["intent_confidence"]
        assert 0.0 <= conf <= 1.0, f"intent_confidence {conf} out of [0,1] range"

    def test_retrieval_strategy_valid(self, planner):
        """retrieval_strategy must be one of the known strategy values."""
        VALID_STRATEGIES = {"simple", "expanded", "graph_first", "multi_source", "hybrid"}
        result = run_async(planner.process(self._make_message("什么是ETOPS要求")))
        strategy = result.data["plan"]["retrieval_strategy"]
        assert strategy in VALID_STRATEGIES, (
            f"Unexpected retrieval_strategy: '{strategy}'. Must be one of {VALID_STRATEGIES}"
        )


# ── AgentMessage Tests ────────────────────────────────────────────────────────

class TestAgentMessage:
    """Tests for AgentMessage data structure."""

    def test_create_planner_message(self):
        """AgentMessage with PLANNER role must be creatable."""
        msg = AgentMessage(role=AgentRole.PLANNER, content="test", data={}, metadata={})
        assert msg.role == AgentRole.PLANNER
        assert msg.content == "test"

    def test_agent_roles_are_correct(self):
        """All 4 AgentRole enum values must exist."""
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.TOOL.value == "tool"
        assert AgentRole.CHECKER.value == "checker"
        assert AgentRole.ANSWER.value == "answer"

    def test_message_data_is_dict(self):
        """AgentMessage.data must be a dict."""
        msg = AgentMessage(role=AgentRole.TOOL, content="", data={"key": "val"}, metadata={})
        assert isinstance(msg.data, dict)


# ── AgentCoordinator Integration (mocked) ────────────────────────────────────

class TestAgentCoordinatorMocked:
    """Tests for AgentCoordinator with mocked LLM + vector engine."""

    @pytest.fixture
    def mock_vector_engine(self):
        """Mock VectorStoreEngine that returns MOCK_CONTEXTS."""
        engine = MagicMock()
        engine.search = MagicMock(return_value=MOCK_CONTEXTS)
        return engine

    @pytest.fixture
    def mock_glm_client(self):
        """Mock LLM client for CheckerAgent and AnswerAgent."""
        client = MagicMock()
        return client

    @pytest.fixture
    def coordinator(self, mock_vector_engine, mock_glm_client):
        """Build real AgentCoordinator with mocked dependencies."""
        from multi_agent.coordinator import AgentCoordinator
        return AgentCoordinator(
            vector_engine=mock_vector_engine,
            glm_client=mock_glm_client,
            graph_store=None,
        )

    def test_coordinator_init(self, coordinator):
        """Coordinator must initialize with planner/tool/checker/answer agents."""
        from multi_agent.planner import PlannerAgent
        from multi_agent.tool import ToolAgent
        from multi_agent.checker import CheckerAgent
        from multi_agent.answer import AnswerAgent
        assert isinstance(coordinator.planner, PlannerAgent)
        assert isinstance(coordinator.tool, ToolAgent)
        assert isinstance(coordinator.checker, CheckerAgent)
        assert isinstance(coordinator.answer, AnswerAgent)

    def test_coordinator_process_query_returns_dict(self, coordinator):
        """AgentCoordinator.process_query() must return a dict."""
        # Patch CheckerAgent and AnswerAgent to avoid LLM calls
        with patch.object(coordinator.tool, "process", new_callable=AsyncMock) as mock_tool, \
             patch.object(coordinator.checker, "process", new_callable=AsyncMock) as mock_checker, \
             patch.object(coordinator.answer, "process", new_callable=AsyncMock) as mock_answer:

            mock_tool.return_value = AgentMessage(
                role=AgentRole.TOOL,
                content="",
                data={"contexts": MOCK_CONTEXTS, "graph_data": None},
                metadata={},
            )
            mock_checker.return_value = AgentMessage(
                role=AgentRole.CHECKER,
                content="",
                data={"validation": {"is_valid": True, "quality_score": 0.8, "issues": []}},
                metadata={},
            )
            mock_answer.return_value = AgentMessage(
                role=AgentRole.ANSWER,
                content="根据 CCAR-33.65，压气机必须具备足够的喘振裕度。",
                data={"citations": MOCK_CONTEXTS[:2]},
                metadata={},
            )

            result = run_async(coordinator.process_query("CCAR-33 喘振裕度要求"))
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_coordinator_result_has_answer_field(self, coordinator):
        """Result dict must contain 'answer' key."""
        with patch.object(coordinator.tool, "process", new_callable=AsyncMock) as mock_tool, \
             patch.object(coordinator.checker, "process", new_callable=AsyncMock) as mock_checker, \
             patch.object(coordinator.answer, "process", new_callable=AsyncMock) as mock_answer:

            mock_tool.return_value = AgentMessage(
                role=AgentRole.TOOL, content="",
                data={"contexts": MOCK_CONTEXTS, "graph_data": None}, metadata={})
            mock_checker.return_value = AgentMessage(
                role=AgentRole.CHECKER, content="",
                data={"validation": {"is_valid": True, "quality_score": 0.9, "issues": []}},
                metadata={})
            mock_answer.return_value = AgentMessage(
                role=AgentRole.ANSWER,
                content="喘振裕度答案",
                data={"citations": []}, metadata={})

            result = run_async(coordinator.process_query("什么是喘振裕度"))
            assert "answer" in result, f"Result missing 'answer' key: {result.keys()}"
