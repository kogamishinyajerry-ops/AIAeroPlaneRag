"""
意图检测准确率基准测试
======================
验收标准: 30 道题，准确率 >= 80%（即 >= 24/30 题预测正确）

运行:
    python evaluation/intent_accuracy_bench.py

退出码:
    0 — 通过 (accuracy >= 80%)
    1 — 未通过 (accuracy < 80%)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ── 路径设置 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rag.vector_engine import detect_query_intent, get_primary_intent  # type: ignore

DATASET_PATH = ROOT / "evaluation" / "intent_classification_set.json"
THRESHOLD = 0.80  # 验收门槛


def load_dataset(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["questions"]


def evaluate(questions: List[Dict]) -> Tuple[int, int, List[Dict]]:
    """返回 (correct, total, failure_list)"""
    correct = 0
    failures = []
    for q in questions:
        predicted = get_primary_intent(q["query"])
        expected = q["expected_intent"]
        if predicted == expected:
            correct += 1
        else:
            failures.append({
                "id": q["id"],
                "query": q["query"],
                "expected": expected,
                "predicted": predicted,
                "scores": {k: f"{v:.3f}" for k, v in detect_query_intent(q["query"]).items()},
            })
    return correct, len(questions), failures


def print_report(correct: int, total: int, failures: List[Dict]) -> None:
    accuracy = correct / total if total else 0
    passed = accuracy >= THRESHOLD

    print("=" * 60)
    print("意图检测准确率基准测试结果")
    print("=" * 60)
    print(f"总题数  : {total}")
    print(f"正确数  : {correct}")
    print(f"准确率  : {accuracy:.1%}  (门槛 {THRESHOLD:.0%})")
    print(f"结论    : {'✅ PASS' if passed else '❌ FAIL'}")

    if failures:
        print(f"\n── 错误样本 ({len(failures)} 条) ────────────────────────────────")
        for f in failures:
            print(f"  [{f['id']}] {f['query'][:50]}")
            print(f"        expected={f['expected']}, predicted={f['predicted']}")
            print(f"        scores: {f['scores']}")
    print("=" * 60)


def main() -> int:
    if not DATASET_PATH.exists():
        print(f"❌ 找不到数据集: {DATASET_PATH}", file=sys.stderr)
        return 2

    questions = load_dataset(DATASET_PATH)
    correct, total, failures = evaluate(questions)
    print_report(correct, total, failures)

    accuracy = correct / total if total else 0
    return 0 if accuracy >= THRESHOLD else 1


if __name__ == "__main__":
    sys.exit(main())
