from typing import Any, Dict, List, Optional
from src.api.models import Citation
from src.settings import DOCUMENT_VERSION

def build_citations(contexts: List[Dict[str, Any]], min_length: int = 500) -> List[Citation]:
    """
    Build citations from retrieval contexts.

    Ensures snippets are at least 500 characters to provide adequate context.
    """
    citations: List[Citation] = []
    for index, context in enumerate(contexts, start=1):
        metadata = context.get("metadata", {})
        full_text = (context.get("original_text") or context.get("text", "")).strip()
        if not full_text:
            full_text = context.get("text", "")

        # Use enhanced content if available
        if "expanded_content" in metadata:
            full_text = metadata["expanded_content"]

        # Ensure at least min_length characters (default 500 for better context)
        if len(full_text) <= min_length + 100:
            snippet = full_text  # Show all if reasonably short
        else:
            # Try to break at sentence boundary for better readability
            snippet = full_text[:min_length]
            last_period = snippet.rfind("。")
            last_newline = snippet.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > min_length * 0.5:  # At least 50% of target
                snippet = snippet[:break_point + 1]
            snippet = snippet + "..."

        # Highlight is first sentence or first 150 chars
        highlight = full_text.splitlines()[0][:150] if full_text else ""

        citations.append(
            Citation(
                num=index,
                source=metadata.get("source", "Unknown source"),
                chapter=metadata.get("chapter", "未知章节"),
                section=metadata.get("section", "未知条款"),
                snippet=snippet,
                highlight=highlight,
                fullText=full_text,
                documentId=metadata.get("document_id"),
                documentVersion=metadata.get("document_version", DOCUMENT_VERSION),
                contentMode=metadata.get("content_mode", "unknown"),
                sourcePath=metadata.get("source_path"),
            )
        )
    return citations



