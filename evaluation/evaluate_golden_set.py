from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_golden_set(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Golden set must be a JSON list.")
    return data


def summarize_golden_set(items: list[dict[str, Any]]) -> dict[str, Any]:
    ids: list[Any] = []
    top_section_counter: Counter[str] = Counter()
    keyword_counter: Counter[str] = Counter()
    answer_type_counter: Counter[str] = Counter()
    with_top_section = 0
    with_section_list = 0
    with_keywords = 0
    missing_expected_keywords = 0

    for item in items:
        ids.append(item.get("id"))

        top_section = item.get("expected_top_section")
        if isinstance(top_section, str) and top_section.strip():
            with_top_section += 1
            top_section_counter[top_section.strip()] += 1

        sections = item.get("expected_sections")
        if isinstance(sections, list) and sections:
            with_section_list += 1
            for section in sections:
                if isinstance(section, str) and section.strip():
                    top_section_counter[section.strip()] += 1

        keywords = item.get("expected_keywords")
        if isinstance(keywords, list) and keywords:
            with_keywords += 1
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    keyword_counter[keyword.strip()] += 1
        else:
            missing_expected_keywords += 1

        answer_type = item.get("expected_answer_type")
        if isinstance(answer_type, str) and answer_type.strip():
            answer_type_counter[answer_type.strip()] += 1

    total = len(items)
    keyword_total = sum(keyword_counter.values())

    return {
        "total": total,
        "ids": ids,
        "with_top_section": with_top_section,
        "with_section_list": with_section_list,
        "with_keywords": with_keywords,
        "missing_expected_keywords": missing_expected_keywords,
        "average_keywords_per_question": round(keyword_total / total, 2) if total else 0.0,
        "answer_type_counts": dict(answer_type_counter),
        "top_sections": top_section_counter.most_common(10),
        "top_keywords": keyword_counter.most_common(10),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a golden set template.")
    parser.add_argument(
        "--golden-set",
        default=str(Path(__file__).with_name("golden_set_sample.json")),
        help="Path to a golden set JSON file.",
    )
    args = parser.parse_args()

    path = Path(args.golden_set)
    items = load_golden_set(path)
    summary = summarize_golden_set(items)

    print(json.dumps({"source": str(path), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
