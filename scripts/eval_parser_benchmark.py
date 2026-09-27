#!/usr/bin/env python3
"""Run a lightweight parser gold set using OmniDocBench-style dimensions.

Manifest format:
[
  {
    "id": "paper-table-en",
    "path": "fixtures/paper-table-en.pdf",
    "layout": "multi_column",
    "language": "en",
    "structure_elements": ["heading", "table"],
    "required_markers": ["Results"]
  }
]

This is a local acceptance harness, not a replacement for OmniDocBench or
olmOCR-Bench.  It keeps the same dimensions so a later public-benchmark run
can be compared without changing the report shape.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


KNOWN_STRUCTURE_ELEMENTS = {"heading", "table", "list", "code", "formula"}
KNOWN_REVIEW_STATUSES = {"candidate", "reviewed"}


def evaluation_fingerprint(manifest: object) -> str:
    """Return a stable fingerprint for the exact parser evaluation manifest."""
    canonical = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_manifest(
    manifest: object,
    *,
    min_cases: int = 1,
    require_provenance: bool = False,
    require_files: bool = False,
) -> list[str]:
    """Validate parser gold metadata before invoking a parser or touching files."""
    errors: list[str] = []
    if not isinstance(manifest, list):
        return ["parser manifest must be a JSON array"]
    if len(manifest) < min_cases:
        errors.append(f"parser manifest has {len(manifest)} cases; requires at least {min_cases}")
    seen_ids: set[str] = set()
    for index, case in enumerate(manifest):
        prefix = f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif case_id in seen_ids:
            errors.append(f"{prefix}.id is duplicated")
        else:
            seen_ids.add(case_id)
        path = case.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{prefix}.path must be a non-empty string")
        elif require_files and not Path(path).is_file():
            errors.append(f"{prefix}.path does not point to a file: {path}")
        for field in ("layout", "language"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        elements = case.get("structure_elements", [])
        if not isinstance(elements, list) or any(
            not isinstance(element, str) or element not in KNOWN_STRUCTURE_ELEMENTS
            for element in elements
        ):
            errors.append(f"{prefix}.structure_elements contains an unsupported dimension")
        markers = case.get("required_markers", [])
        if not isinstance(markers, list) or any(
            not isinstance(marker, str) or not marker.strip() for marker in markers
        ):
            errors.append(f"{prefix}.required_markers must contain non-empty strings")
        for field in ("source_ref", "reviewer"):
            if field in case and (not isinstance(case[field], str) or not case[field].strip()):
                errors.append(f"{prefix}.{field} must be a non-empty string when supplied")
        if "review_status" in case and case["review_status"] not in KNOWN_REVIEW_STATUSES:
            errors.append(f"{prefix}.review_status must be one of {sorted(KNOWN_REVIEW_STATUSES)}")
        if "notes" in case and not isinstance(case["notes"], str):
            errors.append(f"{prefix}.notes must be a string when supplied")
        if require_provenance:
            for field in ("source_ref", "reviewer"):
                value = case.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{prefix}.{field} is required for a reviewed parser case")
            if case.get("review_status") != "reviewed":
                errors.append(f"{prefix}.review_status must be 'reviewed' for release evaluation")
    return errors


def compare_reports(
    current: dict[str, Any], baseline: dict[str, Any], *, tolerance: float = 0.0
) -> dict[str, Any]:
    errors: list[str] = []
    current_fingerprint = (
        current.get("evaluation_fingerprint") if isinstance(current, dict) else None
    )
    baseline_fingerprint = (
        baseline.get("evaluation_fingerprint") if isinstance(baseline, dict) else None
    )
    if not isinstance(current_fingerprint, str) or not current_fingerprint.strip():
        errors.append("current report evaluation_fingerprint is missing")
    if not isinstance(baseline_fingerprint, str) or not baseline_fingerprint.strip():
        errors.append("baseline report evaluation_fingerprint is missing")
    if (
        isinstance(current_fingerprint, str)
        and isinstance(baseline_fingerprint, str)
        and current_fingerprint != baseline_fingerprint
    ):
        errors.append("baseline report uses a different evaluation_fingerprint")
    current_cases = current.get("cases") if isinstance(current, dict) else None
    baseline_cases = baseline.get("cases") if isinstance(baseline, dict) else None
    if not isinstance(current_cases, int) or isinstance(current_cases, bool) or current_cases < 1:
        errors.append("current report cases is missing or invalid")
    if (
        not isinstance(baseline_cases, int)
        or isinstance(baseline_cases, bool)
        or baseline_cases < 1
    ):
        errors.append("baseline report cases is missing or invalid")
    if (
        isinstance(current_cases, int)
        and not isinstance(current_cases, bool)
        and isinstance(baseline_cases, int)
        and not isinstance(baseline_cases, bool)
        and current_cases != baseline_cases
    ):
        errors.append("baseline report uses a different cases count")
    current_value = current.get("pass_rate") if isinstance(current, dict) else None
    baseline_value = baseline.get("pass_rate") if isinstance(baseline, dict) else None
    current_rate = (
        float(current_value)
        if isinstance(current_value, (int, float))
        and not isinstance(current_value, bool)
        and math.isfinite(float(current_value))
        else None
    )
    baseline_rate = (
        float(baseline_value)
        if isinstance(baseline_value, (int, float))
        and not isinstance(baseline_value, bool)
        and math.isfinite(float(baseline_value))
        else None
    )
    if current_rate is None:
        errors.append("current report pass_rate is missing or non-finite")
    elif not 0.0 <= current_rate <= 1.0:
        errors.append("current report pass_rate is outside [0,1]")
    if baseline_rate is None:
        errors.append("baseline report pass_rate is missing or non-finite")
    elif not 0.0 <= baseline_rate <= 1.0:
        errors.append("baseline report pass_rate is outside [0,1]")
    if errors:
        return {
            "pass_rate_delta": None,
            "regression": True,
            "ok": False,
            "errors": errors,
            "tolerance": tolerance,
        }
    delta = current_rate - baseline_rate
    return {
        "pass_rate_delta": delta,
        "regression": delta < -tolerance,
        "ok": delta >= -tolerance,
        "errors": [],
        "tolerance": tolerance,
    }


def score_markdown(markdown: str, case: dict[str, Any]) -> dict[str, Any]:
    text = markdown or ""
    required_markers = case.get("required_markers", [])
    marker_hits = sum(1 for marker in required_markers if marker.lower() in text.lower())
    elements = case.get("structure_elements", [])
    detected = {
        "heading": any(line.lstrip().startswith("#") for line in text.splitlines()),
        "table": "|" in text and "---" in text,
        "list": any(line.lstrip().startswith(("- ", "* ", "1. ")) for line in text.splitlines()),
        "code": "```" in text,
        "formula": "$" in text or "\\(" in text or "\\[" in text,
    }
    structure_hits = sum(1 for element in elements if detected.get(element, False))
    checks = len(required_markers) + len(elements)
    passed_checks = marker_hits + structure_hits
    missing_markers = [marker for marker in required_markers if marker.lower() not in text.lower()]
    missing_structure_elements = [
        element for element in elements if not detected.get(element, False)
    ]
    failure_reasons: list[str] = []
    parser_name = str(case.get("parser") or "")
    if parser_name.startswith(("passthrough", "skip")):
        # Never score the original PDF bytes (or an unsupported input) as if
        # they were parser output.  This used to create false 100% smoke runs
        # when all optional parser dependencies were missing.
        failure_reasons.append("parser_passthrough")
    if missing_markers:
        failure_reasons.append("missing_required_markers")
    if missing_structure_elements:
        failure_reasons.append("missing_structure_elements")
    if len(text.strip()) < int(case.get("min_chars", 40)):
        failure_reasons.append("below_min_chars")
    return {
        "id": case.get("id", "unknown"),
        "source_ref": case.get("source_ref"),
        "reviewer": case.get("reviewer"),
        "review_status": case.get("review_status"),
        "layout": case.get("layout", "unknown"),
        "language": case.get("language", "unknown"),
        "parser": case.get("parser"),
        "chars": len(text.strip()),
        "marker_coverage": marker_hits / len(required_markers) if required_markers else 1.0,
        "structure_coverage": structure_hits / len(elements) if elements else 1.0,
        "missing_markers": missing_markers,
        "missing_structure_elements": missing_structure_elements,
        "failure_reasons": failure_reasons,
        "pass": not failure_reasons and passed_checks == checks,
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[f"{result['layout']}::{result['language']}"].append(result)
    return {
        "schema_version": 1,
        "cases": len(results),
        "passed": sum(1 for result in results if result["pass"]),
        "pass_rate": sum(1 for result in results if result["pass"]) / len(results)
        if results
        else 0.0,
        "by_dimension": {
            key: {
                "cases": len(items),
                "passed": sum(1 for item in items if item["pass"]),
                "pass_rate": sum(1 for item in items if item["pass"]) / len(items),
                "marker_coverage": sum(item.get("marker_coverage", 0.0) for item in items)
                / len(items),
                "structure_coverage": sum(item.get("structure_coverage", 0.0) for item in items)
                / len(items),
            }
            for key, items in sorted(groups.items())
        },
        "parser_counts": dict(Counter(result.get("parser") for result in results)),
        "failure_reason_counts": dict(
            Counter(reason for result in results for reason in result.get("failure_reasons", []))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--min-cases", type=int, default=1)
    parser.add_argument("--report-out", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--regression-tolerance", type=float, default=0.0)
    parser.add_argument(
        "--require-provenance",
        action="store_true",
        help="require source_ref, reviewer and reviewed status for every case",
    )
    parser.add_argument(
        "--require-files",
        action="store_true",
        help="fail before parsing when a manifest path is missing",
    )
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    quality_errors = validate_manifest(
        cases,
        min_cases=args.min_cases,
        require_provenance=args.require_provenance,
        require_files=args.require_files,
    )
    if quality_errors:
        for error in quality_errors:
            print(f"ERROR: {error}")
        return 2
    from stratum.services.pdf_to_markdown import pdf_to_markdown

    results = []
    for case in cases:
        path, parser_name = pdf_to_markdown(Path(case["path"]))
        markdown = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        scored = score_markdown(markdown, {**case, "parser": parser_name})
        results.append(scored)
        print(json.dumps(scored, ensure_ascii=False))
    report = aggregate(results)
    report["evaluation_fingerprint"] = evaluation_fingerprint(cases)
    report["provenance"] = {
        "required": args.require_provenance,
        "reviewed_cases": sum(1 for case in cases if case.get("review_status") == "reviewed"),
        "unreviewed_cases": sum(1 for case in cases if case.get("review_status") != "reviewed"),
    }
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        report["baseline_comparison"] = compare_reports(
            report, baseline, tolerance=args.regression_tolerance
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report_out:
        args.report_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if report.get("baseline_comparison", {}).get("regression"):
        return 1
    return 0 if all(result["pass"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
