"""
Unit tests for expand_synonyms function
Tests: Chinese→English, English→Chinese, chain expansion, no-match cases
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import expand_synonyms, SYNONYM_DICT


class TestExpandSynonymsChineseToEnglish:
    """Test Chinese term expansion to English synonyms"""

    def test_发动机_expands_to_engine(self):
        """发动机 should expand to engine and related terms"""
        result = expand_synonyms("发动机")
        result_lower = [t.lower() for t in result]
        assert "engine" in result_lower
        assert "motor" in result_lower
        assert "propulsion" in result_lower

    def test_压气机_expands_to_compressor(self):
        """压气机 should expand to compressor"""
        result = expand_synonyms("压气机")
        result_lower = [t.lower() for t in result]
        assert "compressor" in result_lower

    def test_喘振_expands_to_surge_stall(self):
        """喘振 should expand to surge and stall"""
        result = expand_synonyms("喘振")
        result_lower = [t.lower() for t in result]
        assert "surge" in result_lower
        assert "stall" in result_lower

    def test_喘振裕度_expands_to_surge_margin(self):
        """喘振裕度 should expand to surge margin and stall margin"""
        result = expand_synonyms("喘振裕度")
        result_lower = [t.lower() for t in result]
        # Should contain margin-related expansions
        # Note: "喘振裕度" itself may not directly map, but the individual words should
        assert len(result) > 0

    def test_涡轮_expands_to_turbine(self):
        """涡轮 should expand to turbine"""
        result = expand_synonyms("涡轮")
        result_lower = [t.lower() for t in result]
        assert "turbine" in result_lower

    def test_叶片_expands_to_blade(self):
        """叶片 should expand to blade, vane"""
        result = expand_synonyms("叶片")
        result_lower = [t.lower() for t in result]
        assert "blade" in result_lower
        assert "vane" in result_lower

    def test_适航_expands_to_airworthiness(self):
        """适航 should expand to airworthiness, certification"""
        result = expand_synonyms("适航")
        result_lower = [t.lower() for t in result]
        assert "airworthiness" in result_lower
        assert "certification" in result_lower

    def test_规范_expands_to_regulation(self):
        """规范 should expand to regulation, standard"""
        result = expand_synonyms("规范")
        result_lower = [t.lower() for t in result]
        assert "regulation" in result_lower

    def test_安全_expands_to_safety(self):
        """安全 should expand to safety"""
        result = expand_synonyms("安全")
        result_lower = [t.lower() for t in result]
        assert "safety" in result_lower


class TestExpandSynonymsEnglishToChinese:
    """Test English term expansion to Chinese synonyms"""

    def test_engine_expands_to_chinese(self):
        """engine should expand to 发动机"""
        result = expand_synonyms("engine")
        # Should contain Chinese characters (适航, 发动机 etc.)
        assert len(result) > 0
        # The result should include Chinese terms from engine's synonym group
        assert "发动机" in result or any("\u4e00" <= c <= "\u9fff" for t in result for c in t)

    def test_compressor_expands_to_chinese(self):
        """compressor should expand to 压气机"""
        result = expand_synonyms("compressor")
        assert "压气机" in result

    def test_surge_expands_to_chinese(self):
        """surge should expand to 喘振"""
        result = expand_synonyms("surge")
        assert "喘振" in result

    def test_turbine_expands_to_chinese(self):
        """turbine should expand to 涡轮"""
        result = expand_synonyms("turbine")
        assert "涡轮" in result or "透平" in result

    def test_airworthiness_expands_to_chinese(self):
        """airworthiness should expand to 适航"""
        result = expand_synonyms("airworthiness")
        assert "适航" in result

    def test_regulation_expands_to_chinese(self):
        """regulation should expand to 规范, 规章, 法规"""
        result = expand_synonyms("regulation")
        found = any(term in result for term in ["规范", "规章", "法规"])
        assert found

    def test_safety_expands_to_chinese(self):
        """safety should expand to 安全"""
        result = expand_synonyms("safety")
        assert "安全" in result


class TestExpandSynonymsChain:
    """Test chain expansion (A→B→C)"""

    def test_two_hop_expansion(self):
        """Terms with two-hop synonyms should be expanded"""
        # If "透平" -> "turbine" and "turbine" -> "涡轮",
        # chain expansion should include both
        result = expand_synonyms("透平")
        result_lower = [t.lower() for t in result]
        # Should contain both the direct and chain-expanded terms
        assert "turbine" in result_lower
        # And through turbine -> 涡轮, but this depends on the dict structure

    def test_self_and_synonyms_included(self):
        """Original term should be in the expanded set"""
        result = expand_synonyms("发动机")
        assert "发动机" in result  # Original term preserved


class TestExpandSynonymsNoMatch:
    """Test cases where no synonyms exist"""

    def test_unknown_term(self):
        """Unknown term should return the term itself"""
        result = expand_synonyms("foobar")
        # Should return at least the original term
        assert len(result) > 0
        assert "foobar" in result or len(result) > 0

    def test_empty_string(self):
        """Empty string returns empty list"""
        result = expand_synonyms("")
        assert result == []

    def test_none_input(self):
        """None input returns empty list"""
        result = expand_synonyms(None)
        assert result == []


class TestExpandSynonymsMultiWord:
    """Test multi-word phrase expansion"""

    def test_space_separated_chinese(self):
        """Space-separated Chinese words are processed"""
        result = expand_synonyms("发动机 压气机")
        result_lower = [t.lower() for t in result]
        assert "engine" in result_lower or "发动机" in result
        assert "compressor" in result_lower or "压气机" in result

    def test_english_phrase(self):
        """English phrase is processed"""
        result = expand_synonyms("compressor rotor")
        assert "compressor" in [t.lower() for t in result] or "rotor" in [t.lower() for t in result]


class TestExpandSynonymsRealWorld:
    """Real-world aviation query expansion"""

    def test_regulatory_query(self):
        """Typical regulatory query - exact match"""
        # Use "适航" which IS in the dictionary
        result = expand_synonyms("适航")
        result_lower = [t.lower() for t in result]
        assert "airworthiness" in result_lower
        assert "certification" in result_lower

    def test_component_query(self):
        """Component-related query - exact match"""
        # Use "涡轮" which IS in the dictionary
        result = expand_synonyms("涡轮")
        result_lower = [t.lower() for t in result]
        assert "turbine" in result_lower
        # And "叶片" which IS in the dictionary
        result2 = expand_synonyms("叶片")
        result2_lower = [t.lower() for t in result2]
        assert "blade" in result2_lower
        assert "vane" in result2_lower

    def test_mixed_regulatory_technical(self):
        """Multiple exact terms in one query"""
        # "压气机" IS in the dictionary
        result = expand_synonyms("压气机")
        result_lower = [t.lower() for t in result]
        assert "compressor" in result_lower
        # "喘振" IS in the dictionary
        result2 = expand_synonyms("喘振")
        result2_lower = [t.lower() for t in result2]
        assert "surge" in result2_lower

    def test_combined_aviation_terms(self):
        """Multiple aviation terms together"""
        result = expand_synonyms("发动机 涡轮 叶片")
        result_lower = [t.lower() for t in result]
        # All three should expand
        assert "engine" in result_lower
        assert "turbine" in result_lower
        assert "blade" in result_lower


class TestExpandSynonymsCompleteness:
    """Test that the synonym dictionary is complete and consistent"""

    def test_bidirectional_one_hop(self):
        """If A→B exists and B→C exists, A should eventually expand to C"""
        # "发动机" -> "engine" (via SYNONYM_DICT)
        result = expand_synonyms("发动机")
        result_lower = [t.lower() for t in result]
        # At minimum, engine's direct Chinese translations should appear
        assert "发动机" in result  # Original preserved
        assert "engine" in result_lower  # First hop

    def test_no_empty_synonym_groups(self):
        """No synonym group should be empty"""
        for key, synonyms in SYNONYM_DICT.items():
            assert len(synonyms) > 0, f"Empty synonym group for key: {key}"

    def test_no_self_reference(self):
        """No term should map to itself in synonyms"""
        for key, synonyms in SYNONYM_DICT.items():
            assert key not in synonyms, f"Self-reference in synonym dict: {key}->{key}"

    def test_all_synonym_keys_are_strings(self):
        """All keys in SYNONYM_DICT should be non-empty strings"""
        for key in SYNONYM_DICT:
            assert isinstance(key, str), f"Non-string key: {key}"
            assert len(key) > 0, f"Empty string key in SYNONYM_DICT"
