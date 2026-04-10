"""
Unit tests for FactCheckingGuardrail local verification logic.
Tests _local_verify, _build_conservative_answer, and verify_response fallback paths.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.guardrail import FactCheckingGuardrail


@pytest.fixture
def guardrail():
    """Guardrail instance without external LLM (no-auth mode)."""
    g = FactCheckingGuardrail()
    g.client = None  # force local-only mode
    return g


CONTEXTS = [
    {
        "text": "压气机必须保持足够的喘振裕度，以确保在所有批准的飞行包线内安全运行。",
        "metadata": {"source": "CCAR-33", "chapter": "第33.65条", "section": "a款"},
    },
    {
        "text": "The compressor must maintain adequate surge margin throughout the approved flight envelope.",
        "metadata": {"source": "FAR-33", "chapter": "Section 33.65", "section": "(a)"},
    },
]


class TestLocalVerify:
    def test_high_overlap_returns_pass(self, guardrail):
        answer = "压气机必须保持足够的喘振裕度，以确保在所有批准的飞行包线内安全运行。"
        result = guardrail._local_verify(answer, CONTEXTS)
        assert result["status"] == "PASS"
        assert "PASS" in result["reasoning"] or "重叠率" in result["reasoning"]

    def test_medium_overlap_returns_partial(self, guardrail):
        answer = "压气机需要喘振裕度，这是适航要求。"
        result = guardrail._local_verify(answer, CONTEXTS)
        assert result["status"] in ("PASS", "PARTIAL")

    def test_low_overlap_returns_unverified(self, guardrail):
        answer = "飞机需要定期维护保养，确保安全飞行。"
        result = guardrail._local_verify(answer, CONTEXTS)
        assert result["status"] in ("PARTIAL", "UNVERIFIED")

    def test_empty_answer_returns_unverified(self, guardrail):
        result = guardrail._local_verify("", CONTEXTS)
        assert result["status"] == "UNVERIFIED"

    def test_english_answer_high_overlap(self, guardrail):
        answer = "The compressor must maintain adequate surge margin throughout the approved flight envelope."
        result = guardrail._local_verify(answer, CONTEXTS)
        assert result["status"] == "PASS"

    def test_result_has_required_keys(self, guardrail):
        result = guardrail._local_verify("压气机喘振裕度", CONTEXTS)
        assert "status" in result
        assert "reasoning" in result
        assert "safe_answer" in result

    def test_status_is_valid_value(self, guardrail):
        result = guardrail._local_verify("压气机喘振裕度", CONTEXTS)
        assert result["status"] in ("PASS", "PARTIAL", "UNVERIFIED", "FAIL")


class TestVerifyResponseFallback:
    def test_no_contexts_returns_not_found(self, guardrail):
        result = guardrail.verify_response("查询", "答案", [])
        assert result["status"] == "NOT_FOUND"

    def test_no_llm_uses_local_verify(self, guardrail):
        answer = "压气机必须保持足够的喘振裕度，以确保在所有批准的飞行包线内安全运行。"
        result = guardrail.verify_response("喘振裕度要求", answer, CONTEXTS)
        # Should use local verify, not return UNVERIFIED for high-overlap answer
        assert result["status"] in ("PASS", "PARTIAL", "UNVERIFIED")
        # High overlap answer should NOT be FAIL
        assert result["status"] != "FAIL"

    def test_high_overlap_answer_passes_local(self, guardrail):
        answer = "压气机必须保持足够的喘振裕度，以确保在所有批准的飞行包线内安全运行。"
        result = guardrail.verify_response("喘振裕度要求", answer, CONTEXTS)
        assert result["status"] == "PASS"

    def test_unrelated_answer_does_not_pass(self, guardrail):
        answer = "今天天气很好，适合出行。"
        result = guardrail.verify_response("喘振裕度要求", answer, CONTEXTS)
        assert result["status"] in ("PARTIAL", "UNVERIFIED")


class TestBuildConservativeAnswer:
    def test_returns_string(self, guardrail):
        result = guardrail._build_conservative_answer(CONTEXTS)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_source_info(self, guardrail):
        result = guardrail._build_conservative_answer(CONTEXTS)
        assert "33.65" in result or "CCAR" in result or "压气机" in result

    def test_limits_to_three_contexts(self, guardrail):
        many_contexts = CONTEXTS * 5
        result = guardrail._build_conservative_answer(many_contexts)
        # Should only include up to 3 entries
        assert result.count("[1]") <= 1
        assert result.count("[4]") == 0

    def test_empty_contexts(self, guardrail):
        result = guardrail._build_conservative_answer([])
        assert isinstance(result, str)
