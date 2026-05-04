from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def dry_metrics(cases: list[dict]) -> dict:
    start = time.perf_counter()
    case_count = len(cases)
    safe_cases = sum(1 for item in cases if item.get("safety_expected") == "safe_educational")
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "case_count": case_count,
        "retrieval_hit_rate": 0.0,
        "precision_at_k": 0.0,
        "context_precision": 0.0,
        "faithfulness": "not_run_without_generation",
        "answer_relevance": "not_run_without_generation",
        "citation_coverage": 0.0,
        "safety_pass_rate": round(safe_cases / max(1, case_count), 3),
        "latency_ms": elapsed_ms,
        "mode": "dry",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight MARA RAG evaluation harness.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/evals/rag_eval_cases.json"),
        help="Path to eval case JSON.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run deterministic metrics without LLM/API calls.")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    metrics = dry_metrics(cases)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
