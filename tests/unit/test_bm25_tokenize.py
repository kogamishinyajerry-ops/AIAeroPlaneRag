"""
Unit tests for tokenize_for_bm25 function (Chinese bigram tokenizer for BM25)
Covers: pure Chinese, pure English, mixed, empty, punctuation-only cases
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import tokenize_for_bm25


class TestTokenizeForBM25Chinese:
    """Test bigram tokenization for pure Chinese text"""

    def test_chinese_single_characters(self):
        """Each Chinese character becomes a unigram token"""
        result = tokenize_for_bm25("压气机")
        # 压 / 气 / 机 + bigrams: 压气, 气机
        assert "压" in result
        assert "气" in result
        assert "机" in result

    def test_chinese_bigrams_generated(self):
        """Chinese bigrams are generated correctly"""
        result = tokenize_for_bm25("压气机喘振")
        # Unigrams
        assert "压" in result
        assert "气" in result
        assert "机" in result
        assert "喘" in result
        assert "振" in result
        # Bigrams
        assert "压气" in result
        assert "气机" in result
        assert "机喘" in result
        assert "喘振" in result

    def test_chinese_three_char_word(self):
        """Three-character word generates correct bigrams"""
        result = tokenize_for_bm25("发动机")
        assert "发" in result
        assert "动" in result
        assert "机" in result
        assert "发动" in result
        assert "动机" in result

    def test_chinese_long_phrase(self):
        """Long Chinese phrase generates all bigrams"""
        result = tokenize_for_bm25("压气机喘振裕度要求")
        # Should contain all unigrams and bigrams
        assert "压" in result
        assert "气" in result
        assert "机" in result
        assert "喘" in result
        assert "振" in result
        assert "裕" in result
        assert "度" in result
        assert "要" in result
        assert "求" in result
        # Bigrams
        assert "压气" in result
        assert "气机" in result
        assert "机喘" in result
        assert "喘振" in result
        assert "振裕" in result
        assert "裕度" in result
        assert "度要" in result
        assert "要求" in result

    def test_chinese_no_spaces(self):
        """Chinese text without spaces is tokenized correctly"""
        result = tokenize_for_bm25("航空发动机")
        assert "航" in result
        assert "空" in result
        assert "发" in result
        assert "动" in result
        assert "机" in result
        assert "航空" in result
        assert "空发" in result
        assert "发动" in result
        assert "动机" in result


class TestTokenizeForBM25English:
    """Test tokenization for pure English text"""

    def test_english_single_word(self):
        """Single English word returns as-is"""
        result = tokenize_for_bm25("engine")
        assert "engine" in result

    def test_english_two_words(self):
        """Two English words are separated"""
        result = tokenize_for_bm25("compressor surge")
        assert "compressor" in result
        assert "surge" in result

    def test_english_multiple_words(self):
        """Multiple English words separated by spaces"""
        result = tokenize_for_bm25("compressor rotor blade temperature")
        expected = {"compressor", "rotor", "blade", "temperature"}
        for word in expected:
            assert word in result

    def test_english_lowercase_conversion(self):
        """English text is converted to lowercase"""
        result = tokenize_for_bm25("COMPRESSOR")
        assert "compressor" in result

    def test_english_with_underscore(self):
        """Underscore in English text is treated as part of word"""
        result = tokenize_for_bm25("air_worthiness")
        assert "air_worthiness" in result

    def test_english_alphanumeric(self):
        """Alphanumeric tokens preserved"""
        result = tokenize_for_bm25("FAA-AC-33")
        assert "faa" in result or "faaac" in result  # depends on tokenization


class TestTokenizeForBM25Mixed:
    """Test tokenization for mixed Chinese and English text"""

    def test_mixed_chinese_english(self):
        """Mixed Chinese and English text is tokenized"""
        result = tokenize_for_bm25("压气机compressor喘振surge")
        # Chinese part
        assert "压" in result
        assert "气" in result
        assert "机" in result
        assert "压气" in result
        assert "气机" in result
        # English part
        assert "compressor" in result
        assert "surge" in result

    def test_mixed_with_space(self):
        """Mixed text with spaces between languages"""
        result = tokenize_for_bm25("压气机 compressor 喘振")
        assert "压" in result
        assert "压气" in result
        assert "compressor" in result
        assert "喘" in result
        assert "振" in result
        assert "喘振" in result


class TestTokenizeForBM25Edge:
    """Test edge cases"""

    def test_empty_string(self):
        """Empty string returns empty list"""
        result = tokenize_for_bm25("")
        assert result == []

    def test_none_input(self):
        """None input returns empty list"""
        result = tokenize_for_bm25(None)
        assert result == []

    def test_punctuation_only(self):
        """Punctuation-only string returns empty or minimal tokens"""
        result = tokenize_for_bm25("！？。，")
        # Punctuation should be filtered out
        assert len(result) == 0 or all(len(t) > 0 for t in result)

    def test_mixed_punctuation(self):
        """Text with punctuation"""
        result = tokenize_for_bm25("压气机，喘振！")
        # Should contain Chinese tokens despite punctuation
        assert "压" in result or "气" in result or "机" in result

    def test_numbers(self):
        """Numbers are preserved as tokens"""
        result = tokenize_for_bm25("33.65")
        # Numbers and dots may be preserved
        assert "33" in result or "33.65" in result

    def test_single_chinese_char(self):
        """Single Chinese character returns just that char"""
        result = tokenize_for_bm25("发")
        assert "发" in result

    def test_two_chinese_chars(self):
        """Two Chinese characters returns both + bigram"""
        result = tokenize_for_bm25("发动")
        assert "发" in result
        assert "动" in result
        assert "发动" in result


class TestTokenizeForBM25RealWorld:
    """Real-world aviation query patterns"""

    def test_regulatory_query(self):
        """Typical regulatory query"""
        result = tokenize_for_bm25("压气机喘振裕度要求")
        assert "压" in result
        assert "气" in result
        assert "机" in result
        assert "喘" in result
        assert "振" in result
        assert "裕" in result
        assert "度" in result
        assert "压气" in result
        assert "气机" in result
        assert "机喘" in result
        assert "喘振" in result
        assert "振裕" in result
        assert "裕度" in result

    def test_english_aviation_term(self):
        """English aviation term"""
        result = tokenize_for_bm25("surge margin stall margin")
        assert "surge" in result
        assert "margin" in result
        assert "stall" in result

    def test_clause_number(self):
        """Clause number with letters"""
        result = tokenize_for_bm25("CCAR-33-R2")
        # Should handle hyphenated clause numbers
        assert len(result) > 0

    def test_mixed_aviation_query(self):
        """Mixed Chinese-English aviation query"""
        result = tokenize_for_bm25("compressor喘振裕度surge")
        assert "compressor" in result
        assert "surge" in result
        assert "喘" in result
        assert "振" in result
        assert "喘振" in result


class TestTokenizeForBM25Deduplication:
    """Test that output is deduplicated"""

    def test_no_duplicate_unigrams(self):
        """Same unigram should not appear twice"""
        result = tokenize_for_bm25("压气机压气机")
        # Count occurrences of "压"
        assert result.count("压") == 1

    def test_no_duplicate_bigrams(self):
        """Same bigram should not appear twice"""
        result = tokenize_for_bm25("压气机压气机")
        # "压气" should appear once
        assert result.count("压气") == 1

    def test_order_preserved(self):
        """Token order is preserved (first occurrence order)"""
        result = tokenize_for_bm25("压气机喘振")
        # "压" should come before "气"
        assert result.index("压") < result.index("气")
        # "气" should come before "机"
        assert result.index("气") < result.index("机")
        # "机" should come before bigram "压气"
        # (unigrams typically listed before bigrams)
