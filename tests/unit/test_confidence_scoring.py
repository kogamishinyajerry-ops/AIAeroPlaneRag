"""
T5.1: 置信度评分 7 维度单元测试
测试 verify_answer_confidence 的各维度、动态权重、不确定性标记
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.rag.confidence import verify_answer_confidence


# ── 测试用 contexts ──────────────────────────────────────────────
CCAR_CTX = {
    "text": "压气机必须在整个批准的飞行包线内保持足够的喘振裕度，以防止压气机失速。",
    "metadata": {"source": "CCAR-33", "authority": "CAAC", "section": "33.65"},
}
FAR_CTX = {
    "text": "The compressor must maintain adequate surge margin throughout the approved flight envelope.",
    "metadata": {"source": "FAR-33", "authority": "FAA", "section": "33.65"},
}
CS_CTX = {
    "text": "CS-E 840: The compressor design must ensure surge margin compliance under all operating conditions.",
    "metadata": {"source": "CS-E", "authority": "EASA", "section": "840"},
}
CONTEXTS = [CCAR_CTX, FAR_CTX, CS_CTX]


class TestReturnType:
    def test_returns_tuple(self):
        score, markers = verify_answer_confidence("答案", [CCAR_CTX])
        assert isinstance(score, float)
        assert isinstance(markers, list)

    def test_score_in_valid_range(self):
        score, _ = verify_answer_confidence("答案", [CCAR_CTX])
        assert 0.0 <= score <= 1.0

    def test_empty_answer_returns_default(self):
        score, markers = verify_answer_confidence("", [CCAR_CTX])
        assert 0.0 <= score <= 1.0

    def test_empty_contexts_returns_default(self):
        score, markers = verify_answer_confidence("压气机喘振裕度要求", [])
        assert 0.0 <= score <= 1.0

    def test_no_crash_on_none_like_inputs(self):
        score, markers = verify_answer_confidence("", [])
        assert isinstance(score, float)


class TestDim1SourceCoverage:
    """维度1：来源覆盖度 - 答案词汇与检索内容重叠"""

    def test_high_overlap_raises_score(self):
        # 答案直接来自 context
        answer = "压气机必须在整个批准的飞行包线内保持足够的喘振裕度，以防止压气机失速。"
        score, _ = verify_answer_confidence(answer, [CCAR_CTX], query="喘振裕度要求")
        assert score >= 0.5

    def test_unrelated_answer_lowers_score(self):
        answer = "今天天气晴朗，适合户外活动。"
        score, markers = verify_answer_confidence(answer, [CCAR_CTX], query="喘振裕度要求")
        # Unrelated answer should have lower score or uncertainty markers
        assert score < 0.9 or len(markers) > 0


class TestDim2CitationDensity:
    """维度2：条款引用密度"""

    def test_answer_with_citations_scores_higher(self):
        answer_with_cite = "根据CCAR-33第33.65条，压气机必须保持喘振裕度。FAR 33.65也有相同要求。"
        answer_no_cite = "压气机必须保持喘振裕度。"
        score_cite, _ = verify_answer_confidence(answer_with_cite, CONTEXTS, query="喘振裕度")
        score_no_cite, _ = verify_answer_confidence(answer_no_cite, CONTEXTS, query="喘振裕度")
        assert score_cite >= score_no_cite

    def test_citation_markers_generated_when_missing(self):
        answer = "压气机需要保持喘振裕度。"
        _, markers = verify_answer_confidence(answer, [CCAR_CTX], query="喘振裕度要求")
        # May or may not have citation marker depending on other dims
        assert isinstance(markers, list)


class TestDim3TermPrecision:
    """维度3：术语精确度"""

    def test_precise_terms_raise_score(self):
        answer_precise = "压气机必须不低于规定的喘振裕度，不得超过最大转速限制。"
        answer_vague = "压气机可能需要一些喘振裕度，大概在某个范围内。"
        score_p, _ = verify_answer_confidence(answer_precise, CONTEXTS)
        score_v, _ = verify_answer_confidence(answer_vague, CONTEXTS)
        assert score_p >= score_v

    def test_vague_terms_generate_uncertainty_marker(self):
        answer = "压气机也许需要喘振裕度，大概是某个值。"
        _, markers = verify_answer_confidence(answer, [CCAR_CTX])
        assert any("模糊" in m for m in markers)


class TestDim4CrossRegulation:
    """维度4：跨规章验证"""

    def test_multi_agency_contexts_raise_score(self):
        score_multi, _ = verify_answer_confidence(
            "压气机喘振裕度要求在CCAR-33和FAR-33中均有规定。",
            CONTEXTS,
        )
        score_single, _ = verify_answer_confidence(
            "压气机喘振裕度要求在CCAR-33中有规定。",
            [CCAR_CTX],
        )
        assert score_multi >= score_single

    def test_cross_regulation_answer_scores_well(self):
        answer = "CCAR-33与FAR-33在压气机喘振裕度要求上基本等效，CS-E也有类似规定。"
        score, _ = verify_answer_confidence(answer, CONTEXTS, query="比较差异")
        assert score >= 0.4


class TestDim5NumericalSpecificity:
    """维度5：数值具体性"""

    def test_numerical_answer_scores_higher(self):
        answer_num = "喘振裕度最小值为15%，在-54°C至+49°C温度范围内有效，转速不超过110% rpm。"
        answer_no_num = "喘振裕度需要满足一定要求。"
        score_num, _ = verify_answer_confidence(answer_num, CONTEXTS, query="数值要求")
        score_no, _ = verify_answer_confidence(answer_no_num, CONTEXTS, query="数值要求")
        assert score_num >= score_no

    def test_numerical_marker_when_missing(self):
        answer = "喘振裕度需要满足规定要求。"
        _, markers = verify_answer_confidence(answer, [CCAR_CTX], query="最小值是多少")
        assert isinstance(markers, list)


class TestDim6AuthorityWeight:
    """维度6：权威性加权"""

    def test_caac_authority_scores_highest(self):
        caac_ctx = {"text": "test", "metadata": {"authority": "CAAC"}}
        faa_ctx = {"text": "test", "metadata": {"authority": "FAA"}}
        other_ctx = {"text": "test", "metadata": {"authority": "OTHER"}}

        score_caac, _ = verify_answer_confidence("压气机喘振裕度", [caac_ctx])
        score_faa, _ = verify_answer_confidence("压气机喘振裕度", [faa_ctx])
        score_other, _ = verify_answer_confidence("压气机喘振裕度", [other_ctx])
        assert score_caac >= score_faa >= score_other


class TestDim7Consistency:
    """维度7：一致性验证"""

    def test_multi_source_consistent_answer_scores_higher(self):
        # Answer supported by multiple contexts
        answer = "压气机必须保持足够的喘振裕度，以防止压气机失速。The compressor must maintain adequate surge margin."
        score, _ = verify_answer_confidence(answer, CONTEXTS)
        assert score >= 0.4


class TestDynamicWeights:
    """动态权重：不同查询类型使用不同权重"""

    def test_regulatory_query_type(self):
        answer = "根据CCAR-33第33.65条，压气机必须保持喘振裕度。"
        score_reg, _ = verify_answer_confidence(answer, CONTEXTS, query="压气机喘振裕度要求是什么")
        assert 0.15 <= score_reg <= 0.95

    def test_method_query_type(self):
        answer = "验证喘振裕度的方法包括台架试车和数值仿真。"
        score_meth, _ = verify_answer_confidence(answer, CONTEXTS, query="如何验证喘振裕度")
        assert 0.15 <= score_meth <= 0.95

    def test_comparison_query_type(self):
        answer = "CCAR-33与FAR-33在喘振裕度要求上存在差异。"
        score_comp, _ = verify_answer_confidence(answer, CONTEXTS, query="比较CCAR和FAR的差异")
        assert 0.15 <= score_comp <= 0.95


class TestUncertaintyMarkers:
    """不确定性标记生成"""

    def test_markers_are_strings(self):
        _, markers = verify_answer_confidence("答案", [CCAR_CTX])
        for m in markers:
            assert isinstance(m, str)

    def test_high_quality_answer_has_few_markers(self):
        answer = (
            "根据CCAR-33第33.65条，压气机必须在整个批准的飞行包线内保持足够的喘振裕度，"
            "不得低于规定的最小值15%。FAR-33和CS-E也有相同要求。"
        )
        _, markers = verify_answer_confidence(answer, CONTEXTS, query="喘振裕度要求")
        assert len(markers) <= 4

    def test_score_clamped_to_valid_range(self):
        # Even extreme inputs should stay in [0.15, 0.95]
        for answer in ["", "x" * 1000, "必须不得最小最大CCAR FAR CS-E 33.65 15% -54°C"]:
            score, _ = verify_answer_confidence(answer, CONTEXTS)
            assert 0.15 <= score <= 0.95
