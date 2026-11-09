"""Measure recall@k of the resource retriever on evaluation/retrieval_cases.json.

Run from the backend directory: python -m scripts.evaluate_retrieval
"""
import json
from pathlib import Path

from app.services.catalog import _index

CASES = Path(__file__).resolve().parent.parent / "evaluation" / "retrieval_cases.json"


def main(k: int = 3) -> None:
    cases = json.loads(CASES.read_text())["cases"]
    hits = 0
    for case in cases:
        top = [doc_id for doc_id, _ in _index().search(case["query"], k=k)]
        ok = bool(set(top) & set(case["relevant"]))
        hits += ok
        if not ok:
            print(f"miss: {case['query']!r} -> {top}")
    print(f"recall@{k}: {hits}/{len(cases)} = {hits / len(cases):.2f}")


if __name__ == "__main__":
    main()
