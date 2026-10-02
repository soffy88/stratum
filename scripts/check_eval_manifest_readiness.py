#!/usr/bin/env python3
"""Check parser/retrieval gold manifests before running external evaluations.

This is a preflight report, not a metric result. It only checks record counts,
review status, and manifest shape; it never claims that a substrate mapping or
parser annotation is semantically correct.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.eval_parser_benchmark import validate_manifest
    from scripts.eval_retrieval import validate_golden_set
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from eval_parser_benchmark import validate_manifest
    from eval_retrieval import validate_golden_set


def _summary(
    cases: list[dict[str, Any]], *, minimum: int, check_files: bool = False
) -> dict[str, Any]:
    reviewed = sum(1 for case in cases if case.get("review_status") == "reviewed")
    files_missing = (
        sum(1 for case in cases if not Path(str(case.get("path", ""))).is_file())
        if check_files
        else 0
    )
    return {
        "cases": len(cases),
        "reviewed": reviewed,
        "unreviewed": len(cases) - reviewed,
        "minimum_required": minimum,
        "threshold_met": len(cases) >= minimum,
        "provenance_complete": bool(cases) and reviewed == len(cases),
        "files_checked": check_files,
        "files_missing": files_missing,
        "files_complete": not files_missing if check_files else None,
        "ready": (
            len(cases) >= minimum
            and reviewed == len(cases)
            and (not check_files or files_missing == 0)
        ),
    }


def build_readiness_report(
    retrieval_cases: list[dict[str, Any]],
    parser_cases: list[dict[str, Any]],
    *,
    min_retrieval_queries: int = 50,
    min_parser_cases: int = 20,
) -> dict[str, Any]:
    """Return count/review readiness without contacting APIs or databases."""
    retrieval = _summary(retrieval_cases, minimum=min_retrieval_queries)
    parser = _summary(parser_cases, minimum=min_parser_cases, check_files=True)
    return {
        "schema_version": 1,
        "report_type": "evaluation_manifest_readiness",
        "metric_results_available": False,
        "retrieval": retrieval,
        "parser": parser,
        "ready": retrieval["ready"] and parser["ready"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-manifest", type=Path, required=True)
    parser.add_argument("--parser-manifest", type=Path, required=True)
    parser.add_argument("--min-retrieval-queries", type=int, default=50)
    parser.add_argument("--min-parser-cases", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    retrieval_cases = json.loads(args.retrieval_manifest.read_text(encoding="utf-8"))
    parser_cases = json.loads(args.parser_manifest.read_text(encoding="utf-8"))
    errors = [
        *validate_golden_set(retrieval_cases, min_queries=1),
        *validate_manifest(parser_cases, min_cases=1),
    ]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2

    report = build_readiness_report(
        retrieval_cases,
        parser_cases,
        min_retrieval_queries=args.min_retrieval_queries,
        min_parser_cases=args.min_parser_cases,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
