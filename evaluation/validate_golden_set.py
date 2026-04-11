"""
黄金集结构验证脚本
==================
验收标准:
  - 至少 20 道题
  - 覆盖三大适航体系: CCAR-33, FAR-33, CS-E
  - 每题具备 id / regulation / language / query / expected_keywords / expected_answer_type 字段

运行:
    python evaluation/validate_golden_set.py

退出码:
    0 — 验证通过
    1 — 验证失败
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set_sample.json"
MIN_QUESTIONS = 20
REQUIRED_REGULATIONS = {"FAR-33", "CCAR-33", "CS-E"}
REQUIRED_FIELDS = {"id", "regulation", "language", "query", "expected_answer_type"}
VALID_ANSWER_TYPES = {"traceable_fact", "numerical", "method", "comparison",
                      "definition", "cross_reference"}
VALID_LANGUAGES = {"en", "zh"}
VALID_REGULATIONS = {"FAR-33", "CCAR-33", "CS-E", "cross", "general"}


def validate(questions: list) -> tuple[bool, list[str]]:
    errors = []

    # ── 1. Count ──────────────────────────────────────────────────────────
    if len(questions) < MIN_QUESTIONS:
        errors.append(f"Total questions {len(questions)} < {MIN_QUESTIONS}")

    # ── 2. Required regulations coverage ─────────────────────────────────
    covered_regs: set = set()
    for q in questions:
        reg = q.get("regulation", "")
        if reg in REQUIRED_REGULATIONS:
            covered_regs.add(reg)
        # cross/general questions that mention specific regs in sections
        for section in q.get("expected_sections", []) + [q.get("expected_top_section", "")]:
            for r in REQUIRED_REGULATIONS:
                if r.split("-")[0] in str(section):
                    covered_regs.add(r)

    missing = REQUIRED_REGULATIONS - covered_regs
    if missing:
        errors.append(f"Missing coverage for regulations: {missing}")

    # ── 3. Per-question field validation ──────────────────────────────────
    seen_ids: set = set()
    for q in questions:
        qid = q.get("id", "?")

        missing_fields = REQUIRED_FIELDS - set(q.keys())
        if missing_fields:
            errors.append(f"[{qid}] Missing fields: {missing_fields}")

        if qid in seen_ids:
            errors.append(f"Duplicate id: {qid}")
        seen_ids.add(qid)

        if q.get("language") not in VALID_LANGUAGES:
            errors.append(f"[{qid}] Invalid language: {q.get('language')}")

        if q.get("regulation") not in VALID_REGULATIONS:
            errors.append(f"[{qid}] Invalid regulation: {q.get('regulation')}")

        if q.get("expected_answer_type") not in VALID_ANSWER_TYPES:
            errors.append(f"[{qid}] Invalid answer_type: {q.get('expected_answer_type')}")

        if not q.get("query", "").strip():
            errors.append(f"[{qid}] Empty query")

    return len(errors) == 0, errors


def print_stats(questions: list) -> None:
    reg_counts = Counter(q.get("regulation") for q in questions)
    lang_counts = Counter(q.get("language") for q in questions)
    type_counts = Counter(q.get("expected_answer_type") for q in questions)

    print("\n── 覆盖统计 ─────────────────────────────────")
    print(f"  总题数      : {len(questions)}")
    print(f"  法规分布    : {dict(reg_counts)}")
    print(f"  语言分布    : {dict(lang_counts)}")
    print(f"  答案类型    : {dict(type_counts)}")


def main() -> int:
    if not GOLDEN_SET_PATH.exists():
        print(f"❌ 找不到黄金集文件: {GOLDEN_SET_PATH}", file=sys.stderr)
        return 2

    questions = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    passed, errors = validate(questions)

    print("=" * 55)
    print("黄金集结构验证")
    print("=" * 55)
    print_stats(questions)
    print()
    if passed:
        print("✅ PASS — 黄金集结构验证通过")
    else:
        print(f"❌ FAIL — 发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 55)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
