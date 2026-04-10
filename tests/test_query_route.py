"""
Unit tests for src.api.routes.query module
Tests query endpoint functionality
"""
import os
import sys
from pathlib import Path

# Setup path to import from src
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
import asyncio


class TestQueryRequest:
    """Test QueryRequest model validation"""

    def test_valid_query_request(self):
        """Test valid query request creation"""
        from src.api.routes.query import QueryRequest

        request = QueryRequest(query="压气机喘振要求")
        assert request.query == "压气机喘振要求"
        assert request.top_k == 3  # default
        assert request.include_graph is True  # default

    def test_custom_top_k(self):
        """Test query request with custom top_k"""
        from src.api.routes.query import QueryRequest

        request = QueryRequest(query="测试查询", top_k=5)
        assert request.top_k == 5

    def test_top_k_minimum_enforced(self):
        """Test that top_k minimum is enforced"""
        from src.api.routes.query import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryRequest(query="测试", top_k=0)  # below minimum of 1

    def test_top_k_maximum_enforced(self):
        """Test that top_k maximum is enforced"""
        from src.api.routes.query import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryRequest(query="测试", top_k=11)  # above maximum of 10

    def test_empty_query_rejected(self):
        """Test that empty query is rejected"""
        from src.api.routes.query import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_query_max_length_enforced(self):
        """Test that query max length is enforced"""
        from src.api.routes.query import QueryRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 501)  # above max 500

    def test_optional_response_mode(self):
        """Test query request with optional response_mode"""
        from src.api.routes.query import QueryRequest

        request = QueryRequest(query="测试", response_mode="detailed")
        assert request.response_mode == "detailed"


class TestQueryResponse:
    """Test QueryResponse model"""

    def test_valid_query_response(self):
        """Test valid query response creation"""
        from src.api.routes.query import QueryResponse, Citation

        citation = Citation(
            num=1,
            source="CCAR-33",
            snippet="test snippet",
            highlight="highlight",
            fullText="full text",
            documentId="doc1",
            documentVersion="v1",
            contentMode="structured",
            sourcePath="/path/to/doc",
        )

        response = QueryResponse(
            query="测试查询",
            answer="测试回答",
            citations=[citation],
            guardrail={"status": "VERIFIED"},
            responseMode="llm-generated",
            retrievalCount=1,
        )

        assert response.query == "测试查询"
        assert response.answer == "测试回答"
        assert len(response.citations) == 1
        assert response.retrievalCount == 1

    def test_response_with_optional_fields(self):
        """Test query response with all optional fields"""
        from src.api.routes.query import QueryResponse

        response = QueryResponse(
            query="测试",
            answer="答案",
            citations=[],
            guardrail={"status": "PASS"},
            responseMode="llm-generated",
            confidence=0.95,
            thinkingProcess="思考过程",
            reasoningSteps=["步骤1", "步骤2"],
            uncertaintyMarkers=["不确定性1"],
            graphInsights=[{"node": "test"}],
            retrievalCount=0,
            processingTimeMs=100,
            intentDetection={"regulatory": 0.8},
        )

        assert response.confidence == 0.95
        assert response.thinkingProcess == "思考过程"
        assert response.reasoningSteps == ["步骤1", "步骤2"]


class TestFallbackAnswer:
    """Test _fallback_answer function"""

    def test_fallback_with_no_contexts(self):
        """Test fallback answer with empty contexts"""
        from src.api.routes.query import _fallback_answer

        result = _fallback_answer([])
        assert "抱歉" in result or "未找到" in result

    def test_fallback_with_contexts(self):
        """Test fallback answer with contexts"""
        from src.api.routes.query import _fallback_answer

        contexts = [
            {
                "text": "这是测试内容",
                "metadata": {"source": "CCAR-33"}
            },
            {
                "text": "更多测试内容",
                "metadata": {"source": "FAR-25"}
            }
        ]

        result = _fallback_answer(contexts)
        assert "CCAR-33" in result or "检索" in result

    def test_fallback_truncates_long_text(self):
        """Test that fallback truncates very long text"""
        from src.api.routes.query import _fallback_answer

        long_text = "x" * 500
        contexts = [
            {
                "text": long_text,
                "metadata": {"source": "TEST"}
            }
        ]

        result = _fallback_answer(contexts)
        # Should not contain full 500 character text
        assert len(result) < 1000


class TestDetectQueryIntentIntegration:
    """Test detect_query_intent integration with query endpoint"""

    def test_intent_detection_in_query_request(self):
        """Test that intent detection works correctly"""
        # Import directly from the module path
        from src.rag.vector_engine import detect_query_intent

        query = "压气机的喘振裕度要求是什么"
        intent = detect_query_intent(query)

        assert "regulatory" in intent
        assert intent["regulatory"] > 0


class TestCitation:
    """Test Citation model"""

    def test_citation_all_fields(self):
        """Test citation with all fields"""
        from src.api.routes.query import Citation

        citation = Citation(
            num=1,
            source="CCAR-33-R2",
            chapter="第33.65条",
            section="a款",
            snippet="喘振裕度要求",
            highlight="喘振裕度",
            fullText="完整的条款内容",
            documentId="ccar33-65",
            documentVersion="v2",
            contentMode="structured",
            sourcePath="/docs/ccar33.md",
        )

        assert citation.num == 1
        assert citation.source == "CCAR-33-R2"
        assert citation.chapter == "第33.65条"
        assert citation.section == "a款"

    def test_citation_required_fields_only(self):
        """Test citation with only required fields"""
        from src.api.routes.query import Citation

        citation = Citation(
            num=1,
            source="TEST",
            snippet="snippet",
            highlight="highlight",
            fullText="full text",
            documentId="doc1",
            documentVersion="v1",
            contentMode="text",
            sourcePath="/path",
        )

        assert citation.chapter == ""
        assert citation.section == ""


class TestQueryEndpointModels:
    """Test query endpoint model validation"""

    def test_query_request_examples(self):
        """Test that QueryRequest examples are properly defined"""
        from src.api.routes.query import QueryRequest

        examples = QueryRequest.model_config.get("json_schema_extra", {}).get("examples", [])
        assert len(examples) > 0
        assert "query" in examples[0]

    def test_response_model_has_correct_version_fields(self):
        """Test that QueryResponse has version fields"""
        from src.api.routes.query import QueryResponse

        # Check default values
        response = QueryResponse(
            query="test",
            answer="answer",
            citations=[],
            guardrail={},
            responseMode="test",
            retrievalCount=0,
        )

        assert hasattr(response, "embeddingVersion")
        assert hasattr(response, "promptVersion")
        assert hasattr(response, "responseVersion")


class TestRequestContractPropagation:
    def test_planner_applies_request_overrides(self):
        from src.multi_agent.planner import PlannerAgent
        from src.multi_agent.base import AgentMessage, AgentRole

        planner = PlannerAgent()
        message = AgentMessage(
            role=AgentRole.PLANNER,
            content="FAA和EASA的要求有什么区别",
            data={"request": {"top_k": 2, "include_graph": False, "response_mode": "graph-first"}},
            metadata={},
        )

        result = asyncio.run(planner.process(message))
        plan = result.data["plan"]

        assert plan["top_k"] == 2
        assert plan["use_graph"] is True
        assert plan["retrieval_strategy"] == "graph_first"
        assert plan["response_mode"] == "graph-first"

    def test_tool_uses_graph_store_when_include_graph_enabled(self):
        from src.multi_agent.tool import ToolAgent
        from src.multi_agent.base import AgentMessage, AgentRole

        class FakeVectorEngine:
            def search(self, query: str, top_k: int = 3):
                return [{"text": "ctx", "metadata": {"chunk_id": "c1", "source": "S"}}]

        class FakeGraphStore:
            def get_subgraph(self, query: str, limit: int = 20, include_parameters: bool = False):
                return {
                    "summary": f"graph for {query}",
                    "nodes": [{"id": "n1", "label": "Node"}],
                    "edges": [{"source": "n1", "target": "n1", "type": "SELF"}],
                }

        tool = ToolAgent(FakeVectorEngine(), FakeGraphStore())
        message = AgentMessage(
            role=AgentRole.TOOL,
            content="",
            data={"plan": {"query": "压气机", "top_k": 1, "use_graph": True, "retrieval_strategy": "simple"}},
            metadata={},
        )

        result = asyncio.run(tool.process(message))
        graph_data = result.data["result"]["graph_data"]

        assert graph_data is not None
        assert graph_data["summary"] == "graph for 压气机"
        assert len(graph_data["nodes"]) == 1

    def test_execute_rag_query_forwards_request_contract(self):
        from src.api.routes import query as query_module

        captured = {}

        class FakeCoordinator:
            def __init__(self, vector_engine, glm_client=None, graph_store=None):
                captured["graph_store"] = graph_store

            async def process_query(self, query: str, request_options=None):
                captured["query"] = query
                captured["request_options"] = dict(request_options or {})
                return {
                    "answer": "ok",
                    "citations": [],
                    "graph_insights": [{"type": "node_distribution", "data": {"regulation": 1}}],
                    "quality_score": 0.8,
                    "is_valid": True,
                    "intent_type": "regulatory",
                    "retrieval_count": 2,
                    "relevance_scores": [0.9],
                    "quality_issues": [],
                    "quality_suggestions": [],
                    "response_mode": "graph-first",
                }

        original_coordinator = query_module.AgentCoordinator
        original_graph_store = query_module.services._graph_store
        query_module.AgentCoordinator = FakeCoordinator
        query_module.services._graph_store = object()
        try:
            req = query_module.QueryRequest(
                query="压气机喘振要求",
                top_k=4,
                include_graph=True,
                response_mode="graph-first",
            )
            response = asyncio.run(
                query_module.execute_rag_query(
                    req=req,
                    api_key="test",
                    vector_engine=object(),
                )
            )
        finally:
            query_module.AgentCoordinator = original_coordinator
            query_module.services._graph_store = original_graph_store

        assert captured["query"] == "压气机喘振要求"
        assert captured["request_options"] == {
            "top_k": 4,
            "include_graph": True,
            "response_mode": "graph-first",
        }
        assert captured["graph_store"] is not None
        assert response.responseMode == "graph-first"
        assert response.graphInsights
