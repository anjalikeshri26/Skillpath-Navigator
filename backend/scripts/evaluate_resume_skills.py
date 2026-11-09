"""Measure skill-extraction precision and recall on evaluation/resume_cases.json.

Run from the backend directory: python -m scripts.evaluate_resume_skills
"""
import json
from pathlib import Path

from app.domain.skills import load_taxonomy

CASES = Path(__file__).resolve().parent.parent / "evaluation" / "resume_cases.json"


def main() -> None:
    taxonomy = load_taxonomy()
    tp = fp = fn = 0
    for i, case in enumerate(json.loads(CASES.read_text())["cases"], 1):
        predicted, expected = set(taxonomy.find_skills(case["text"])), set(case["expected"])
        tp, fp, fn = tp + len(predicted & expected), fp + len(predicted - expected), fn + len(expected - predicted)
        if predicted != expected:
            print(f"case {i}: false positives {sorted(predicted - expected)}, misses {sorted(expected - predicted)}")
    precision, recall = tp / (tp + fp or 1), tp / (tp + fn or 1)
    print(f"precision {precision:.2f}  recall {recall:.2f}  (tp={tp} fp={fp} fn={fn})")


if __name__ == "__main__":
    main()
