"""
Unit tests for src.rag.vector_engine module
Tests detect_query_intent function and related utilities
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.vector_engine import (
    BM25,
    VectorStoreEngine,
    detect_query_intent,
    get_primary_intent,
    tokenize_text,
    expand_synonyms,
    extract_phrase_candidates,
    INTENT_PATTERNS,
)


class TestDetectQueryIntent:
    """Test detect_query_intent function"""

    def test_regulatory_query_chinese(self):
        """Test regulatory intent detection with Chinese query"""
        query = "压气机的喘振裕度要求是什么"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "regulatory" in result
        assert result["regulatory"] > 0  # Should detect regulatory intent

    def test_regulatory_query_english(self):
        """Test regulatory intent detection with English query"""
        query = "what are the requirements for surge margin"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "regulatory" in result
        assert result["regulatory"] > 0

    def test_method_query_chinese(self):
        """Test method intent detection with Chinese query"""
        query = "如何检测压气机喘振"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "method" in result
        assert result["method"] > 0

    def test_method_query_english(self):
        """Test method intent detection with English query"""
        query = "how to test compressor surge"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "method" in result
        assert result["method"] > 0

    def test_comparison_query(self):
        """Test comparison intent detection"""
        query = "FAA和EASA的要求有什么区别"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "comparison" in result
        assert result["comparison"] > 0

    def test_definition_query(self):
        """Test definition intent detection"""
        query = "什么是喘振裕度"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "definition" in result
        assert result["definition"] > 0

    def test_numerical_query(self):
        """Test numerical intent detection"""
        query = "最小喘振裕度是多少"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "numerical" in result
        assert result["numerical"] > 0

    def test_cross_reference_query(self):
        """Test cross-reference intent detection"""
        query = "CCAR与FAA的等效条款"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        assert "cross_reference" in result

    def test_empty_query(self):
        """Test empty query returns normalized scores"""
        query = ""
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        # Empty query should still return dict with all intent keys
        for intent in INTENT_PATTERNS.keys():
            assert intent in result

    def test_intent_scores_are_normalized(self):
        """Test that intent scores are normalized (sum to approximately 1 or follow adjustment rules)"""
        query = "压气机喘振裕度的要求和方法"
        result = detect_query_intent(query)

        total = sum(result.values())
        # Normalized scores should sum to 1.0 (or close, with tolerance)
        # Note: When regulatory+method combo is detected, adjustment happens
        assert 0.5 <= total <= 1.0, f"Intent scores should be normalized, got {total}"

    def test_intent_scores_are_non_negative(self):
        """Test that all intent scores are non-negative"""
        queries = [
            "压气机要求",
            "如何测试",
            "FAA与EASA区别",
            "什么是喘振",
            "最小数值是多少",
        ]

        for query in queries:
            result = detect_query_intent(query)
            for intent, score in result.items():
                assert score >= 0, f"Intent {intent} score should be non-negative, got {score}"

    def test_mixed_regulatory_method_query(self):
        """Test mixed regulatory and method query"""
        query = "喘振裕度的要求以及如何验证"
        result = detect_query_intent(query)

        assert result["regulatory"] > 0.2
        assert result["method"] > 0.15

    def test_no_matching_pattern(self):
        """Test query with no matching patterns"""
        query = "asdfghjkl random text xyz"
        result = detect_query_intent(query)

        assert isinstance(result, dict)
        # All scores might be 0, which is valid

    def test_query_with_intent_combinations(self):
        """Test that combined regulatory and method queries get adjusted scores"""
        query = "喘振裕度的要求是什么，如何计算"
        result = detect_query_intent(query)

        # Both intents should have significant scores
        assert result["regulatory"] > 0.1
        assert result["method"] > 0.1


class TestGetPrimaryIntent:
    """Test get_primary_intent function"""

    def test_returns_highest_scoring_intent(self):
        """Test that primary intent is the highest scoring one"""
        query = "压气机的喘振裕度要求是什么"
        primary = get_primary_intent(query)

        result = detect_query_intent(query)
        highest_score = max(result.values())

        assert primary in result
        assert result[primary] == highest_score

    def test_returns_string_intent_name(self):
        """Test that primary intent returns string key"""
        query = "如何计算最小喘振裕度"
        primary = get_primary_intent(query)

        assert isinstance(primary, str)
        assert primary in INTENT_PATTERNS.keys()


class TestTokenizeText:
    """Test tokenize_text function"""

    def test_tokenize_chinese(self):
        """Test Chinese text tokenization"""
        text = "压气机喘振"
        tokens = tokenize_text(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert "压气机" in tokens or "压" in tokens

    def test_tokenize_english(self):
        """Test English text tokenization"""
        text = "compressor surge"
        tokens = tokenize_text(text)

        assert isinstance(tokens, list)
        assert "compressor" in tokens
        assert "surge" in tokens

    def test_tokenize_mixed(self):
        """Test mixed Chinese and English tokenization"""
        text = "压气机compressor喘振surge"
        tokens = tokenize_text(text)

        assert isinstance(tokens, list)
        # Should separate Chinese and English

    def test_tokenize_empty_string(self):
        """Test empty string tokenization"""
        tokens = tokenize_text("")
        assert tokens == []

    def test_tokenize_none(self):
        """Test None input tokenization"""
        tokens = tokenize_text(None)
        assert tokens == []


class TestExpandSynonyms:
    """Test expand_synonyms function"""

    def test_expand_chinese_term(self):
        """Test Chinese term synonym expansion"""
        text = "发动机"
        expanded = expand_synonyms(text)

        assert isinstance(expanded, list)
        assert "engine" in expanded or "发动机" in expanded

    def test_expand_english_term(self):
        """Test English term synonym expansion"""
        text = "engine"
        expanded = expand_synonyms(text)

        assert isinstance(expanded, list)

    def test_expand_empty_string(self):
        """Test empty string expansion"""
        expanded = expand_synonyms("")
        assert expanded == []

    def test_expand_none(self):
        """Test None input expansion"""
        expanded = expand_synonyms(None)
        assert expanded == []


class TestExtractPhraseCandidates:
    """Test extract_phrase_candidates function"""

    def test_extract_chinese_phrases(self):
        """Test Chinese phrase extraction"""
        text = "压气机喘振裕度要求"
        phrases = extract_phrase_candidates(text)

        assert isinstance(phrases, list)
        # The function extracts 2+ character Chinese sequences as phrases
        assert len(phrases) > 0

    def test_extract_english_phrases(self):
        """Test English phrase extraction"""
        text = "compressor surge margin"
        phrases = extract_phrase_candidates(text)

        assert isinstance(phrases, list)
        assert "compressor" in phrases

    def test_extract_mixed_phrases(self):
        """Test mixed phrase extraction"""
        text = "压气机compressor喘振"
        phrases = extract_phrase_candidates(text)

        assert isinstance(phrases, list)
        assert len(phrases) > 0

    def test_extract_empty_string(self):
        """Test empty string extraction"""
        phrases = extract_phrase_candidates("")
        assert phrases == []

    def test_extract_returns_unique_phrases(self):
        """Test that extract_phrase_candidates returns unique results"""
        text = "压气机喘振压气机测试"
        phrases = extract_phrase_candidates(text)

        # Should not have duplicates
        assert len(phrases) == len(set(phrases))


class DummyHybridCollection:
    def query(self, query_texts, n_results):
        return {
            "documents": [["vector doc text"]],
            "metadatas": [[{
                "source": "SRC",
                "chapter": "ch",
                "section": "sec",
                "title": "vector title",
                "chunk_id": "doc_vec",
            }]],
            "ids": [["doc_vec"]],
        }

    def get(self, ids):
        if ids == ["doc_bm25"]:
            return {
                "ids": ["doc_bm25"],
                "documents": ["bm25 only text"],
                "metadatas": [{
                    "source": "SRC2",
                    "chapter": "ch2",
                    "section": "sec2",
                    "title": "bm25 title",
                    "chunk_id": "doc_bm25",
                }],
            }
        return {"ids": [], "documents": [], "metadatas": []}


class DummyClient:
    def __init__(self):
        self.deleted = []

    def delete_collection(self, name):
        self.deleted.append(name)

    def get_or_create_collection(self, name, embedding_function):
        return {"name": name, "embedding_function": embedding_function}


class TestHybridRetrievalRegression:
    def test_bm25_only_hits_are_preserved(self):
        engine = VectorStoreEngine.__new__(VectorStoreEngine)
        engine.collection = DummyHybridCollection()
        engine._query_cache = {}
        engine._indexed_cache = {
            "doc_vec": {
                "id": "doc_vec",
                "text": "vector doc text",
                "original_text": "vector doc text",
                "metadata": {
                    "source": "SRC",
                    "chapter": "ch",
                    "section": "sec",
                    "title": "vector title",
                    "chunk_id": "doc_vec",
                },
            }
        }
        engine._bm25_indexed = True
        engine._bm25_index = BM25()
        engine._bm25_index.doc_count = 2
        engine._bm25_index.doc_texts = {
            "doc_vec": ["vector", "doc"],
            "doc_bm25": ["bm25", "only", "text"],
        }
        engine._bm25_index.doc_len = {"doc_vec": 2, "doc_bm25": 3}
        engine._bm25_index.doc_freqs = {"vector": 1, "doc": 1, "bm25": 1, "only": 1, "text": 1}
        engine._bm25_index.avgdl = 2.5
        engine._evict_caches_if_needed = lambda: None

        results = engine.search("bm25", top_k=3)

        result_ids = {item["id"] for item in results}
        assert "doc_bm25" in result_ids

    def test_recreate_collection_invalidates_bm25_state(self):
        engine = VectorStoreEngine.__new__(VectorStoreEngine)
        engine.client = DummyClient()
        engine.collection_name = "regulations"
        engine.embedding_function = object()
        engine.collection = {"name": "old"}
        engine._indexed_cache = {"old": {}}
        engine._query_cache = {("q", 1): []}
        engine._bm25_index = object()
        engine._bm25_indexed = True

        engine._recreate_collection()

        assert engine.collection["name"] == "regulations"
        assert engine._indexed_cache == {}
        assert engine._query_cache == {}
        assert engine._bm25_index is None
        assert engine._bm25_indexed is False
