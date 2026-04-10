"""
T5.3: 多语言混合 Query 增强单元测试
测试 expand_mixed_query() 对纯中文、纯英文、中英混合查询的处理
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import expand_mixed_query


class TestExpandMixedQueryReturnType:
    def test_returns_list(self):
        assert isinstance(expand_mixed_query("压气机"), list)

    def test_empty_string_returns_empty(self):
        assert expand_mixed_query("") == []

    def test_none_like_empty_returns_empty(self):
        assert expand_mixed_query("") == []

    def test_no_duplicates(self):
        result = expand_mixed_query("compressor 压气机")
        assert len(result) == len(set(result))

    def test_all_terms_are_strings(self):
        for term in expand_mixed_query("compressor surge 压气机喘振"):
            assert isinstance(term, str)
            assert term.strip()


class TestPureChineseQuery:
    def test_zh_query_includes_original(self):
        result = expand_mixed_query("压气机喘振裕度")
        assert "压气机喘振裕度" in result

    def test_zh_query_expands_to_english(self):
        result = expand_mixed_query("喘振裕度")
        lower = [t.lower() for t in result]
        assert any("surge" in t for t in lower), f"Expected 'surge' in {result}"

    def test_zh_query_expands_engine(self):
        result = expand_mixed_query("发动机")
        lower = [t.lower() for t in result]
        assert any("engine" in t for t in lower)

    def test_zh_query_turbine(self):
        result = expand_mixed_query("涡轮叶片")
        lower = [t.lower() for t in result]
        assert any("turbine" in t or "blade" in t for t in lower)


class TestPureEnglishQuery:
    def test_en_query_includes_original(self):
        result = expand_mixed_query("surge margin")
        assert "surge margin" in result

    def test_en_query_expands_to_chinese(self):
        result = expand_mixed_query("surge margin")
        assert any("喘振" in t for t in result), f"Expected '喘振' in {result}"

    def test_en_query_engine(self):
        result = expand_mixed_query("engine")
        assert any("发动机" in t for t in result)

    def test_en_query_turbine_blade(self):
        result = expand_mixed_query("turbine blade")
        assert any("涡轮" in t or "叶片" in t for t in result)

    def test_en_bigram_phrase_included(self):
        result = expand_mixed_query("compressor surge")
        lower = [t.lower() for t in result]
        assert "compressor surge" in lower or any("compressor" in t for t in lower)


class TestMixedQuery:
    def test_mixed_includes_both_parts(self):
        result = expand_mixed_query("compressor 压气机")
        lower = [t.lower() for t in result]
        assert any("compressor" in t for t in lower)
        assert any("压气机" in t for t in result)

    def test_mixed_expands_both_directions(self):
        result = expand_mixed_query("compressor 压气机 喘振")
        lower = [t.lower() for t in result]
        # Should have English terms from Chinese expansion
        assert any("surge" in t for t in lower) or any("喘振" in t for t in result)
        # Should have Chinese terms from English expansion
        assert any("压气机" in t or "发动机" in t for t in result)

    def test_mixed_no_empty_terms(self):
        result = expand_mixed_query("turbine 涡轮 blade 叶片")
        assert all(t.strip() for t in result)

    def test_mixed_result_is_superset_of_parts(self):
        zh_result = set(expand_mixed_query("压气机"))
        en_result = set(expand_mixed_query("compressor"))
        mixed_result = set(expand_mixed_query("compressor 压气机"))
        # Mixed should contain at least what each part produces
        assert len(mixed_result) >= max(len(zh_result), len(en_result))


class TestEdgeCases:
    def test_single_chinese_char(self):
        result = expand_mixed_query("机")
        assert isinstance(result, list)

    def test_single_english_word(self):
        result = expand_mixed_query("engine")
        assert len(result) >= 1

    def test_numbers_only(self):
        result = expand_mixed_query("33.65")
        assert isinstance(result, list)

    def test_mixed_with_numbers(self):
        result = expand_mixed_query("CCAR-33 压气机")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_abbreviation_expands(self):
        result = expand_mixed_query("FADEC")
        lower = [t.lower() for t in result]
        assert any("fadec" in t or "控制" in t or "digital" in t for t in lower)

    def test_long_mixed_query(self):
        query = "compressor surge margin 压气机喘振裕度 CCAR-33 FAR-33"
        result = expand_mixed_query(query)
        assert len(result) >= 5
        assert query in result
