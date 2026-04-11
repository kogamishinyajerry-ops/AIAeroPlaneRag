"""
7 维度置信度评分单元测试
验收标准: score_confidence 返回含 7 个维度 + summary + explanation 的结构化结果
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.rag.confidence import (
    score_confidence,
    verify_answer_confidence,
    DIMENSION_LABELS,
    ConfidenceResult,
)

EXPECTED_DIMS = set(DIMENSION_LABELS.keys())

SAMPLE_CONTEXTS = [
    {
        "text": "根据 CCAR-33 第 33.65 条，压气机必须保持足够的喘振裕度。",
        "metadata": {"source": "CCAR-33.md", "authority": "CAAC", "section": "33.65"},
    },
    {
        "text": "FAR 33.65 requires the compressor to maintain adequate surge margin.",
        "metadata": {"source": "FAR-33.md", "authority": "FAA", "section": "33.65"},
    },
]

SAMPLE_ANSWER = (
    "根据 CCAR-33 第 33.65 条，压气机必须在整个批准的飞行包线内保持足够的喘振裕度，"
    "防止压气机失速。FAR 33.65 亦有等效要求，数值不低于 10%。"
    "CS-E 600 条款进一步规定了测试程序，压气机效率不得低于 0.85。"
)


class TestScoreConfidenceStructure:
    """验证 score_confidence 返回结构的完整性"""

    def test_returns_confidence_result_type(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert isinstance(result, dict), "result should be a dict (TypedDict)"

    def test_has_summary_field(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert "summary" in result
        assert isinstance(result["summary"], float)
        assert 0.0 <= result["summary"] <= 1.0

    def test_summary_is_clamped(self):
        # Empty answer should still be clamped
        result = score_confidence("", [], "")
        assert result["summary"] >= 0.15 or "失败" in result["explanation"]

    def test_has_query_type_field(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert "query_type" in result
        assert result["query_type"] in {"regulatory", "method", "comparison", "general"}

    def test_query_type_regulatory_detected(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "CCAR-33 对压气机的要求")
        assert result["query_type"] == "regulatory"

    def test_query_type_method_detected(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "如何验证压气机喘振裕度")
        assert result["query_type"] == "method"

    def test_query_type_comparison_detected(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "FAR-33 与 CCAR-33 的差异")
        assert result["query_type"] == "comparison"

    def test_has_seven_dimensions(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert "dimensions" in result
        dims = result["dimensions"]
        assert isinstance(dims, dict)
        assert len(dims) == 7, f"Expected 7 dimensions, got {len(dims)}: {list(dims.keys())}"

    def test_all_required_dimension_keys_present(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        found_keys = set(result["dimensions"].keys())
        assert found_keys == EXPECTED_DIMS, f"Missing: {EXPECTED_DIMS - found_keys}"

    def test_each_dimension_has_required_fields(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        required = {"name", "label", "score", "weight", "weighted", "detail"}
        for dim_name, dim_val in result["dimensions"].items():
            missing = required - set(dim_val.keys())
            assert not missing, f"Dimension '{dim_name}' missing fields: {missing}"

    def test_dimension_scores_in_valid_range(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        for name, dim in result["dimensions"].items():
            assert 0.0 <= dim["score"] <= 1.0, f"{name}.score={dim['score']} out of [0,1]"
            assert 0.0 <= dim["weight"] <= 1.0, f"{name}.weight={dim['weight']} out of [0,1]"

    def test_weights_sum_to_one(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        total_weight = sum(d["weight"] for d in result["dimensions"].values())
        assert abs(total_weight - 1.0) < 1e-6, f"Weights sum to {total_weight}, not 1.0"

    def test_has_explanation_field(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert "explanation" in result
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 10, "Explanation too short"

    def test_has_uncertainty_markers_field(self):
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert "uncertainty_markers" in result
        assert isinstance(result["uncertainty_markers"], list)

    def test_high_quality_answer_gets_high_score(self):
        """答案引用多机构、有数值、有条款号时，置信度应高"""
        result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机喘振裕度要求")
        assert result["summary"] >= 0.40, f"Expected >= 0.40, got {result['summary']}"

    def test_empty_answer_returns_fallback(self):
        """空答案应返回合理的回退结果"""
        result = score_confidence("", [], "")
        assert "summary" in result
        assert "dimensions" in result
        assert len(result["dimensions"]) == 7

    def test_no_context_reduces_source_coverage(self):
        """无检索上下文时，来源覆盖度应为 0"""
        result = score_confidence("压气机必须保持喘振裕度。", [], "要求")
        dim = result["dimensions"]["source_coverage"]
        assert dim["score"] == 0.0

    def test_cross_regulation_detected_from_answer(self):
        """答案中提到 CCAR + FAR 时，跨规章维度应 > 0.5"""
        result = score_confidence(SAMPLE_ANSWER, [], "压气机要求")
        dim = result["dimensions"]["cross_regulation"]
        assert dim["score"] > 0.5, f"Expected > 0.5, got {dim['score']}"


class TestBackwardCompatibility:
    """verify_answer_confidence 仍返回 (float, List[str])"""

    def test_old_api_returns_tuple(self):
        score, markers = verify_answer_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机要求")
        assert isinstance(score, float)
        assert isinstance(markers, list)

    def test_old_api_score_matches_new_summary(self):
        old_score, _ = verify_answer_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机要求")
        new_result = score_confidence(SAMPLE_ANSWER, SAMPLE_CONTEXTS, "压气机要求")
        assert abs(old_score - new_result["summary"]) < 1e-6
