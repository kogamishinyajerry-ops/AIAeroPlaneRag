import json
import logging
from typing import List
from src.settings import PROCESSED_DATA_DIR
logger = logging.getLogger(__name__)

def _tokenize_text(text: str) -> List[str]:
    tokens = []
    buffer = []

    def flush() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in (text or "").lower():
        if "\u4e00" <= char <= "\u9fff":
            flush()
            tokens.append(char)
        elif char.isalnum() or char == "_":
            buffer.append(char)
        else:
            flush()

    flush()
    return [token for token in tokens if token.strip()]



def extract_keywords_from_query(query: str) -> List[str]:
    stopwords = {
        "什么",
        "哪些",
        "如何",
        "是否",
        "要求",
        "规定",
        "条款",
        "关于",
        "以及",
        "the",
        "what",
        "which",
        "does",
        "requirement",
    }
    keywords = []
    for token in _tokenize_text(query):
        if len(token) < 2:
            continue
        if token.lower() in stopwords:
            continue
        keywords.append(token)
    return list(dict.fromkeys(keywords[:6]))



def expand_query_with_synonyms(query: str, terminology: dict, abbreviations: dict) -> str:
    """使用术语库扩展查询"""
    expanded_terms = [query]

    # 查找缩写
    for abbr, full_forms in abbreviations.items():
        if abbr.lower() in query.lower():
            for full_form in full_forms:
                if full_form not in query:
                    expanded_terms.append(full_form)

    # 查找同义词
    for term_id, term_data in terminology.items():
        term_text = term_data.get("text", "")
        if term_text in query and len(term_text) >= 2:
            term_type = term_data.get("type", "")
            if term_type == "abbreviation":
                # 查找全称
                for abbr, full_forms in abbreviations.items():
                    if term_text in full_forms or abbr == term_text:
                        expanded_terms.extend(full_forms)

    # 返回扩展后的查询
    return " ".join(expanded_terms)



def expand_query_with_terminology(query: str) -> str:
    """使用术语库扩展查询"""
    try:
        # 优先使用增强术语库
        terminology = load_terminology()
        abbreviations = load_abbreviations()

        if terminology or abbreviations:
            expanded = expand_query_with_synonyms(query, terminology, abbreviations)
            if expanded != query:
                logger.info(f"[TERMINOLOGY] Expanded: {query[:30]}... -> {expanded[:30]}...")
            return expanded

        # 回退到原始术语库
        if not knowledge_linker:
            return query

        # 加载扩展术语
        terminology_file = PROCESSED_DATA_DIR / "knowledge_links" / "expanded_terminology.json"
        if terminology_file.exists():
            with open(terminology_file, 'r', encoding='utf-8') as f:
                terminology = json.load(f)

            # 扩展查询
            expanded_terms = []
            for term, variants in terminology.items():
                if term in query or any(v in query for v in variants):
                    expanded_terms.extend(variants)

            if expanded_terms:
                return query + " " + " ".join(expanded_terms[:5])
    except Exception as e:
        logger.warning(f"Terminology expansion failed: {e}")

    return query



