from __future__ import annotations

import json

from evaluation.evaluate_golden_set import load_golden_set, summarize_golden_set


def test_golden_set_summary_counts_top_sections_keywords_and_answer_types(tmp_path):
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(
        json.dumps(
            [
                {
                    "id": "Q-001",
                    "query": "What does the compressor surge margin require?",
                    "expected_top_section": "Section 33.23 - Surge Margin",
                    "expected_keywords": ["surge margin", "compressor"],
                    "expected_answer_type": "traceable_fact",
                },
                {
                    "id": "Q-002",
                    "query": "What are the compressor design requirements?",
                    "expected_sections": ["Section 33.21 - Compressor Design"],
                    "expected_keywords": ["compressor", "design"],
                    "expected_answer_type": "traceable_fact",
                },
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    items = load_golden_set(golden_path)
    summary = summarize_golden_set(items)

    assert summary["total"] == 2
    assert summary["with_top_section"] == 1
    assert summary["with_section_list"] == 1
    assert summary["with_keywords"] == 2
    assert summary["answer_type_counts"]["traceable_fact"] == 2
    assert summary["top_sections"][0][0] == "Section 33.23 - Surge Margin"
