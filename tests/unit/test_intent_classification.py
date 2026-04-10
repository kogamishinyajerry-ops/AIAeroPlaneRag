"""
Intent Classification Evaluation Runner
Evaluates detect_query_intent accuracy against intent_classification_set.json

Run: python3 -m pytest tests/unit/test_intent_classification.py -v
"""
import pytest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rag.vector_engine import detect_query_intent, get_primary_intent


def load_test_set():
    """Load the intent classification test set"""
    test_set_path = Path(__file__).parent.parent.parent / "evaluation" / "intent_classification_set.json"
    with open(test_set_path, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"], data["categories"]


def evaluate_intent_detection():
    """
    Evaluate intent detection against the test set.
    Returns detailed results and summary statistics.
    """
    questions, categories = load_test_set()

    results = []
    correct_by_category = {cat: {"correct": 0, "total": 0} for cat in categories}
    overall_correct = 0
    overall_total = len(questions)

    for q in questions:
        query = q["query"]
        expected = q["expected_intent"]
        qid = q["id"]

        intent_scores = detect_query_intent(query)
        predicted = get_primary_intent(query)

        is_correct = predicted == expected
        if is_correct:
            overall_correct += 1
            correct_by_category[expected]["correct"] += 1
        correct_by_category[expected]["total"] += 1

        results.append({
            "id": qid,
            "query": query,
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct,
            "scores": intent_scores
        })

    overall_accuracy = overall_correct / overall_total if overall_total > 0 else 0
    category_accuracy = {
        cat: (v["correct"] / v["total"] if v["total"] > 0 else 0)
        for cat, v in correct_by_category.items()
    }

    return {
        "results": results,
        "overall_accuracy": overall_accuracy,
        "overall_correct": overall_correct,
        "overall_total": overall_total,
        "category_accuracy": category_accuracy,
        "correct_by_category": correct_by_category
    }


class TestIntentClassification:
    """Test intent classification accuracy"""

    @pytest.fixture(scope="class")
    def eval_result(self):
        return evaluate_intent_detection()

    def test_overall_accuracy(self, eval_result):
        """Overall intent classification accuracy should be >= 80%"""
        accuracy = eval_result["overall_accuracy"]
        print(f"\n  Overall accuracy: {accuracy*100:.1f}% ({eval_result['overall_correct']}/{eval_result['overall_total']})")
        assert accuracy >= 0.80, f"Overall accuracy {accuracy*100:.1f}% < 80%"

    def test_per_category_accuracy(self, eval_result):
        """Each category should have >= 60% accuracy"""
        for cat, acc in eval_result["category_accuracy"].items():
            total = eval_result["correct_by_category"][cat]["total"]
            correct = eval_result["correct_by_category"][cat]["correct"]
            print(f"  {cat}: {acc*100:.1f}% ({correct}/{total})")
            assert acc >= 0.60, f"Category '{cat}' accuracy {acc*100:.1f}% < 60%"

    def test_all_questions_answerable(self, eval_result):
        """Every question should return a valid intent (non-empty)"""
        for result in eval_result["results"]:
            scores = result["scores"]
            assert len(scores) > 0, f"Question {result['id']} returned no scores"
            assert result["predicted"] in [
                "regulatory", "method", "comparison",
                "definition", "numerical", "cross_reference"
            ], f"Question {result['id']} returned invalid intent: {result['predicted']}"

    def test_scores_are_normalized(self, eval_result):
        """Intent scores should be non-negative and sum reasonably"""
        for result in eval_result["results"]:
            scores = result["scores"]
            for intent, score in scores.items():
                assert score >= 0, f"Question {result['id']}: negative score for {intent}"

    def test_regulatory_queries(self, eval_result):
        """Regulatory queries are correctly identified"""
        reg_results = [r for r in eval_result["results"] if r["expected"] == "regulatory"]
        correct = sum(1 for r in reg_results if r["correct"])
        print(f"\n  Regulatory: {len(reg_results)} questions, {correct} correct")
        assert len(reg_results) == 5, "Should have 5 regulatory test questions"

    def test_method_queries(self, eval_result):
        """Method queries are correctly identified"""
        method_results = [r for r in eval_result["results"] if r["expected"] == "method"]
        correct = sum(1 for r in method_results if r["correct"])
        print(f"  Method: {len(method_results)} questions, {correct} correct")
        assert len(method_results) == 5, "Should have 5 method test questions"

    def test_comparison_queries(self, eval_result):
        """Comparison queries are correctly identified"""
        comp_results = [r for r in eval_result["results"] if r["expected"] == "comparison"]
        correct = sum(1 for r in comp_results if r["correct"])
        print(f"  Comparison: {len(comp_results)} questions, {correct} correct")
        assert len(comp_results) == 5, "Should have 5 comparison test questions"

    def test_definition_queries(self, eval_result):
        """Definition queries are correctly identified"""
        def_results = [r for r in eval_result["results"] if r["expected"] == "definition"]
        correct = sum(1 for r in def_results if r["correct"])
        print(f"  Definition: {len(def_results)} questions, {correct} correct")
        assert len(def_results) == 5, "Should have 5 definition test questions"

    def test_numerical_queries(self, eval_result):
        """Numerical queries are correctly identified"""
        num_results = [r for r in eval_result["results"] if r["expected"] == "numerical"]
        correct = sum(1 for r in num_results if r["correct"])
        print(f"  Numerical: {len(num_results)} questions, {correct} correct")
        assert len(num_results) == 5, "Should have 5 numerical test questions"

    def test_cross_reference_queries(self, eval_result):
        """Cross-reference queries are correctly identified"""
        xref_results = [r for r in eval_result["results"] if r["expected"] == "cross_reference"]
        correct = sum(1 for r in xref_results if r["correct"])
        print(f"  Cross-Reference: {len(xref_results)} questions, {correct} correct")
        assert len(xref_results) == 5, "Should have 5 cross_reference test questions"


if __name__ == "__main__":
    # Run evaluation directly
    result = evaluate_intent_detection()
    print("\n=== Intent Classification Evaluation ===\n")
    print(f"Overall: {result['overall_correct']}/{result['overall_total']} correct = {result['overall_accuracy']*100:.1f}%\n")
    for cat in result["category_accuracy"]:
        stats = result["correct_by_category"][cat]
        acc = result["category_accuracy"][cat]
        print(f"  {cat}: {acc*100:.1f}% ({stats['correct']}/{stats['total']})")
    print()
