#!/usr/bin/env python3
"""Release gate for retrieval/parser evaluation reports.

This gate intentionally defaults to the documented real-data thresholds:
50 retrieval queries and 20 parser documents.  A sample fixture can still be
used for local development by lowering the thresholds explicitly, but it will
not silently qualify as a production evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _unit_interval(value: Any) -> bool:
    parsed = _finite_float(value)
    return parsed is not None and 0.0 <= parsed <= 1.0


def check_reports(
    retrieval: dict[str, Any],
    parser: dict[str, Any],
    *,
    min_retrieval_queries: int = 50,
    min_parser_cases: int = 20,
    max_retrieval_error_rate: float = 0.0,
    require_no_regression: bool = True,
    require_provenance: bool = True,
    require_metrics: bool = True,
    require_baseline: bool = True,
) -> list[str]:
    if not isinstance(retrieval, dict):
        return ["retrieval report must be a JSON object"]
    if not isinstance(parser, dict):
        return ["parser report must be a JSON object"]
    errors: list[str] = []
    retrieval_count = _nonnegative_int(retrieval.get("queries_total", 0))
    parser_count = _nonnegative_int(parser.get("cases", 0))
    if retrieval_count is None:
        errors.append("retrieval queries_total must be a non-negative integer")
        retrieval_count = 0
    if parser_count is None:
        errors.append("parser cases must be a non-negative integer")
        parser_count = 0
    if retrieval_count < min_retrieval_queries:
        errors.append(
            f"retrieval report has {retrieval_count} queries; requires {min_retrieval_queries}"
        )
    if parser_count < min_parser_cases:
        errors.append(f"parser report has {parser_count} cases; requires {min_parser_cases}")
    if require_baseline:
        retrieval_fingerprint = retrieval.get("evaluation_fingerprint")
        if not isinstance(retrieval_fingerprint, str) or not retrieval_fingerprint.strip():
            errors.append("retrieval report is missing evaluation_fingerprint")
        parser_fingerprint = parser.get("evaluation_fingerprint")
        if not isinstance(parser_fingerprint, str) or not parser_fingerprint.strip():
            errors.append("parser report is missing evaluation_fingerprint")
    if require_metrics:
        retrieval_metrics = retrieval.get("metrics")
        if not isinstance(retrieval_metrics, dict):
            errors.append("retrieval report is missing aggregate metrics")
        else:
            for name in ("recall", "precision", "hit_rate", "mrr"):
                value = retrieval_metrics.get(name)
                parsed = _finite_float(value)
                if parsed is None:
                    errors.append(f"retrieval metric {name} is missing or non-finite")
                elif not 0.0 <= parsed <= 1.0:
                    errors.append(f"retrieval metric {name} is outside [0,1]")
        parser_pass_rate = parser.get("pass_rate")
        if _finite_float(parser_pass_rate) is None:
            errors.append("parser report pass_rate is missing or non-finite")
        dimensions = parser.get("by_dimension")
        if not isinstance(dimensions, dict) or not dimensions:
            errors.append("parser report is missing by_dimension results")
        elif any(
            not isinstance(value, dict)
            or not all(
                _unit_interval(value.get(field))
                for field in ("pass_rate", "marker_coverage", "structure_coverage")
            )
            for value in dimensions.values()
        ):
            errors.append("parser by_dimension results are incomplete or outside [0,1]")
        if require_provenance:
            retrieval_provenance = retrieval.get("provenance", {})
            if not isinstance(retrieval_provenance, dict):
                errors.append("retrieval report provenance must be a JSON object")
                retrieval_provenance = {}
            if retrieval_provenance.get("required") is not True:
                errors.append("retrieval report was not run with provenance enforcement")
            unreviewed_queries = _nonnegative_int(retrieval_provenance.get("unreviewed_queries", 1))
            if unreviewed_queries is None or unreviewed_queries:
                errors.append("retrieval report contains unreviewed gold queries")
            parser_provenance = parser.get("provenance", {})
            if not isinstance(parser_provenance, dict):
                errors.append("parser report provenance must be a JSON object")
                parser_provenance = {}
            if parser_provenance.get("required") is not True:
                errors.append("parser report was not run with provenance enforcement")
            unreviewed_cases = _nonnegative_int(parser_provenance.get("unreviewed_cases", 1))
            if unreviewed_cases is None or unreviewed_cases:
                errors.append("parser report contains unreviewed gold cases")
    error_rate = _finite_float(retrieval.get("error_rate", 1.0))
    if error_rate is None or not 0.0 <= error_rate <= 1.0:
        display = "invalid" if error_rate is None else f"{error_rate:.3f}"
        errors.append(f"retrieval error rate {display} is outside [0,1]")
    elif error_rate > max_retrieval_error_rate:
        errors.append(
            f"retrieval error rate {error_rate:.3f} exceeds {max_retrieval_error_rate:.3f}"
        )
    comparison = retrieval.get("baseline_comparison", {})
    if require_baseline and (not isinstance(comparison, dict) or comparison.get("ok") is not True):
        errors.append("retrieval report is missing a successful baseline comparison")
    if require_no_regression and isinstance(comparison, dict) and comparison.get("ok") is False:
        errors.append("retrieval report regressed against baseline")
    parser_comparison = parser.get("baseline_comparison", {})
    if require_baseline and (
        not isinstance(parser_comparison, dict)
        or parser_comparison.get("ok") is not True
        or parser_comparison.get("regression") is not False
    ):
        errors.append("parser report is missing a non-regressing baseline comparison")
    if (
        require_no_regression
        and isinstance(parser_comparison, dict)
        and parser_comparison.get("regression") is True
    ):
        errors.append("parser report regressed against baseline")
    pass_rate = _finite_float(parser.get("pass_rate", 0.0))
    if pass_rate is None or not 0.0 <= pass_rate <= 1.0:
        errors.append("parser pass_rate is outside [0,1]")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-report", type=Path, required=True)
    parser.add_argument("--parser-report", type=Path, required=True)
    parser.add_argument("--min-retrieval-queries", type=int, default=50)
    parser.add_argument("--min-parser-cases", type=int, default=20)
    parser.add_argument("--max-retrieval-error-rate", type=float, default=0.0)
    parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="local-only escape hatch; never use for a release evaluation",
    )
    parser.add_argument(
        "--allow-missing-baseline",
        action="store_true",
        help="local-only escape hatch; never use for a release evaluation",
    )
    args = parser.parse_args()
    retrieval = json.loads(args.retrieval_report.read_text(encoding="utf-8"))
    parser_report = json.loads(args.parser_report.read_text(encoding="utf-8"))
    errors = check_reports(
        retrieval,
        parser_report,
        min_retrieval_queries=args.min_retrieval_queries,
        min_parser_cases=args.min_parser_cases,
        max_retrieval_error_rate=args.max_retrieval_error_rate,
        require_provenance=not args.allow_unreviewed,
        require_baseline=not args.allow_missing_baseline,
    )
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("Evaluation release gate OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
