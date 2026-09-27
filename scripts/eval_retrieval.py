#!/usr/bin/env python3
"""Retrieval eval harness — measure public-standard retrieval metrics.

This is the missing "ruler": without it, every retrieval change (rerank,
expansion, chunking, embedding swap) is a blind bet. Run it before and after a
change to know whether quality actually moved.

Golden set format (JSON list):
    [
      {"query": "什么是注意力机制", "relevant_substrate_ids": ["01ABC...", "01DEF..."]},
      ...
    ]
Build it from real questions you care about + the substrate ids that *should*
surface. 50-100 reviewed entries is the release target; smaller fixtures are
useful for local development but do not satisfy the release gate.

Usage:
    export STRATUM_EVAL_TOKEN=<jwt>            # or pass --token
    python3 scripts/eval_retrieval.py --golden scripts/eval_golden_set.example.json
    python3 scripts/eval_retrieval.py --golden my_set.json --rerank
    python3 scripts/eval_retrieval.py --golden my_set.json --rerank --expand --top-k 10

The printed names map to the usual RAG evaluation vocabulary: recall@k,
precision@k, hit-rate@k and MRR@k.  Generation-level RAGAS faithfulness is
intentionally kept separate because this harness does not call an LLM judge.
Exit code is non-zero if the golden set is empty or all queries error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

KNOWN_REVIEW_STATUSES = {"candidate", "reviewed"}


def evaluation_fingerprint(golden: object) -> str:
    """Return a stable fingerprint for the exact reviewed retrieval set."""
    canonical = json.dumps(
        golden, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_golden_set(
    golden: object, *, min_queries: int = 1, require_provenance: bool = False
) -> list[str]:
    """Return data-quality errors without contacting the retrieval API."""
    errors: list[str] = []
    if not isinstance(golden, list):
        return ["golden set must be a JSON array"]
    if len(golden) < min_queries:
        errors.append(f"golden set has {len(golden)} queries; requires at least {min_queries}")
    seen_queries: set[str] = set()
    for index, item in enumerate(golden):
        prefix = f"item[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            errors.append(f"{prefix}.query must be a non-empty string")
        elif query.strip() in seen_queries:
            errors.append(f"{prefix}.query is duplicated")
        else:
            seen_queries.add(query.strip())
        relevant = item.get("relevant_substrate_ids")
        if not isinstance(relevant, list) or not relevant:
            errors.append(f"{prefix}.relevant_substrate_ids must be a non-empty array")
        elif any(not isinstance(value, str) or not value.strip() for value in relevant):
            errors.append(f"{prefix}.relevant_substrate_ids contains an empty/non-string ID")
        elif len(set(relevant)) != len(relevant):
            errors.append(f"{prefix}.relevant_substrate_ids contains duplicates")
        for field in ("query_id", "source_ref", "reviewer"):
            if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                errors.append(f"{prefix}.{field} must be a non-empty string when supplied")
        if "review_status" in item and item["review_status"] not in KNOWN_REVIEW_STATUSES:
            errors.append(f"{prefix}.review_status must be one of {sorted(KNOWN_REVIEW_STATUSES)}")
        if "rationale" in item and (
            not isinstance(item["rationale"], str) or not item["rationale"].strip()
        ):
            errors.append(f"{prefix}.rationale must be a non-empty string when supplied")
        if require_provenance:
            for field in ("source_ref", "reviewer", "rationale"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{prefix}.{field} is required for a reviewed gold query")
            if item.get("review_status") != "reviewed":
                errors.append(f"{prefix}.review_status must be 'reviewed' for release evaluation")
    return errors


def compare_reports(current: dict, baseline: dict, *, tolerance: float = 0.0) -> dict[str, object]:
    """Compare aggregate metrics; positive deltas are improvements."""
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
    current_queries = current.get("queries_total") if isinstance(current, dict) else None
    baseline_queries = baseline.get("queries_total") if isinstance(baseline, dict) else None
    if (
        not isinstance(current_queries, int)
        or isinstance(current_queries, bool)
        or current_queries < 1
    ):
        errors.append("current report queries_total is missing or invalid")
    if (
        not isinstance(baseline_queries, int)
        or isinstance(baseline_queries, bool)
        or baseline_queries < 1
    ):
        errors.append("baseline report queries_total is missing or invalid")
    if (
        isinstance(current_queries, int)
        and not isinstance(current_queries, bool)
        and isinstance(baseline_queries, int)
        and not isinstance(baseline_queries, bool)
        and current_queries != baseline_queries
    ):
        errors.append("baseline report uses a different queries_total")
    current_metrics = current.get("metrics") if isinstance(current, dict) else None
    baseline_metrics = baseline.get("metrics") if isinstance(baseline, dict) else None
    if not isinstance(current_metrics, dict):
        errors.append("current report is missing aggregate metrics")
        current_metrics = {}
    if not isinstance(baseline_metrics, dict):
        errors.append("baseline report is missing aggregate metrics")
        baseline_metrics = {}
    regressions: dict[str, float] = {}
    deltas: dict[str, float] = {}
    for name in ("recall", "precision", "hit_rate", "mrr"):
        current_value = current_metrics.get(name)
        baseline_value = baseline_metrics.get(name)
        if (
            not isinstance(current_value, (int, float))
            or isinstance(current_value, bool)
            or not math.isfinite(float(current_value))
        ):
            errors.append(f"current metric {name} is missing or non-finite")
            continue
        if (
            not isinstance(baseline_value, (int, float))
            or isinstance(baseline_value, bool)
            or not math.isfinite(float(baseline_value))
        ):
            errors.append(f"baseline metric {name} is missing or non-finite")
            continue
        if not 0.0 <= float(current_value) <= 1.0:
            errors.append(f"current metric {name} is outside [0,1]")
            continue
        if not 0.0 <= float(baseline_value) <= 1.0:
            errors.append(f"baseline metric {name} is outside [0,1]")
            continue
        delta = float(current_value) - float(baseline_value)
        deltas[name] = delta
        if delta < -tolerance:
            regressions[name] = delta
    return {
        "deltas": deltas,
        "regressions": regressions,
        "errors": errors,
        "ok": not regressions and not errors,
    }


def _post_search(
    base_url: str, token: str, query: str, top_k: int, rerank: bool, expand: bool, timeout: float
) -> list[str]:
    """Return ordered list of result substrate ids for a query."""
    body = json.dumps(
        {
            "query": query,
            "top_k": top_k,
            "rerank": rerank,
            "expand": expand,
        }
    ).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/search",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return [r["id"] for r in data.get("results", [])]


def _metrics(ranked_ids: list[str], relevant: set[str], k: int) -> tuple[float, float]:
    """Return (recall@k, reciprocal_rank@k) for one query."""
    if not relevant:
        return 0.0, 0.0
    top = ranked_ids[:k]
    hits = sum(1 for i in top if i in relevant)
    recall = hits / len(relevant)
    rr = 0.0
    for rank, i in enumerate(top, start=1):
        if i in relevant:
            rr = 1.0 / rank
            break
    return recall, rr


def _metric_summary(ranked_ids: list[str], relevant: set[str], k: int) -> dict[str, float]:
    """Return retrieval metrics with names compatible with common RAG reports."""
    top = ranked_ids[:k]
    hits = sum(1 for item in top if item in relevant)
    recall, rr = _metrics(ranked_ids, relevant, k)
    return {
        "recall": recall,
        "precision": hits / len(top) if top else 0.0,
        "hit_rate": 1.0 if hits else 0.0,
        "mrr": rr,
    }


def _first_relevant_rank(ranked_ids: list[str], relevant: set[str], k: int) -> int | None:
    for rank, item in enumerate(ranked_ids[:k], start=1):
        if item in relevant:
            return rank
    return None


def _trace_provenance(item: dict[str, object]) -> dict[str, object]:
    """Echo review metadata into a query trace without changing metric inputs."""
    return {
        "query_id": item.get("query_id"),
        "source_ref": item.get("source_ref"),
        "reviewer": item.get("reviewer"),
        "review_status": item.get("review_status"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", required=True, help="path to golden set JSON")
    ap.add_argument(
        "--base-url", default=os.environ.get("STRATUM_EVAL_BASE_URL", "https://stratum.kanpan.co")
    )
    ap.add_argument("--token", default=os.environ.get("STRATUM_EVAL_TOKEN", ""))
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--min-queries", type=int, default=1)
    ap.add_argument("--max-error-rate", type=float, default=1.0)
    ap.add_argument("--report-out", help="write a machine-readable report JSON")
    ap.add_argument("--baseline", help="previous report JSON for regression comparison")
    ap.add_argument("--regression-tolerance", type=float, default=0.0)
    ap.add_argument(
        "--require-provenance",
        action="store_true",
        help="require source_ref, reviewer, rationale and reviewed status for every query",
    )
    args = ap.parse_args()

    with open(args.golden, encoding="utf-8") as f:
        golden = json.load(f)
    quality_errors = validate_golden_set(
        golden, min_queries=args.min_queries, require_provenance=args.require_provenance
    )
    if quality_errors:
        for error in quality_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if not args.token:
        print("ERROR: provide --token or set STRATUM_EVAL_TOKEN", file=sys.stderr)
        return 2

    k = args.top_k
    recalls: list[float] = []
    precisions: list[float] = []
    hit_rates: list[float] = []
    rrs: list[float] = []
    query_results: list[dict[str, object]] = []
    errors = 0
    t0 = time.time()

    print(
        f"Eval: {len(golden)} queries | top_k={k} | "
        f"rerank={args.rerank} expand={args.expand} | {args.base_url}"
    )
    print("-" * 72)
    for item in golden:
        q = item["query"]
        relevant = set(item.get("relevant_substrate_ids", []))
        try:
            ranked = _post_search(
                args.base_url, args.token, q, k, args.rerank, args.expand, args.timeout
            )
        except (urllib.error.URLError, KeyError, ValueError) as e:
            errors += 1
            query_results.append(
                {
                    **_trace_provenance(item),
                    "query": q,
                    "status": "error",
                    "error": str(e)[:500],
                }
            )
            print(f"  [ERR] {q[:40]!r}: {e}")
            continue
        metrics = _metric_summary(ranked, relevant, k)
        query_results.append(
            {
                **_trace_provenance(item),
                "query": q,
                "status": "scored",
                "relevant_substrate_ids": sorted(relevant),
                "retrieved_substrate_ids": ranked[:k],
                "first_relevant_rank": _first_relevant_rank(ranked, relevant, k),
                "metrics": metrics,
            }
        )
        recalls.append(metrics["recall"])
        precisions.append(metrics["precision"])
        hit_rates.append(metrics["hit_rate"])
        rrs.append(metrics["mrr"])
        print(
            f"  recall@{k}={metrics['recall']:.2f}  "
            f"precision@{k}={metrics['precision']:.2f}  "
            f"hit-rate@{k}={metrics['hit_rate']:.2f}  "
            f"mrr@{k}={metrics['mrr']:.2f}  {q[:44]}"
        )

    print("-" * 72)
    n = len(recalls)
    if n == 0:
        print("All queries errored.", file=sys.stderr)
        return 1
    print(f"queries scored : {n}/{len(golden)}  (errors: {errors})")
    print(f"recall@{k}      : {sum(recalls) / n:.3f}")
    metrics = {
        "recall": sum(recalls) / n,
        "precision": sum(precisions) / n,
        "hit_rate": sum(hit_rates) / n,
        "mrr": sum(rrs) / n,
    }
    print(f"precision@{k}   : {metrics['precision']:.3f}")
    print(f"hit-rate@{k}    : {metrics['hit_rate']:.3f}")
    print(f"MRR@{k}         : {metrics['mrr']:.3f}")
    print(f"elapsed        : {time.time() - t0:.1f}s")
    report = {
        "schema_version": 1,
        "metrics": metrics,
        "evaluation_fingerprint": evaluation_fingerprint(golden),
        "queries_total": len(golden),
        "queries_scored": n,
        "errors": errors,
        "error_rate": errors / len(golden),
        "query_results": query_results,
        "config": {"top_k": k, "rerank": args.rerank, "expand": args.expand},
        "provenance": {
            "required": args.require_provenance,
            "reviewed_queries": sum(
                1 for item in golden if item.get("review_status") == "reviewed"
            ),
            "unreviewed_queries": sum(
                1 for item in golden if item.get("review_status") != "reviewed"
            ),
        },
    }
    if args.baseline:
        with open(args.baseline, encoding="utf-8") as f:
            report["baseline_comparison"] = compare_reports(
                report, json.load(f), tolerance=args.regression_tolerance
            )
    if args.report_out:
        with open(args.report_out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    if report["error_rate"] > args.max_error_rate:
        print(
            f"ERROR: error rate {report['error_rate']:.3f} exceeds {args.max_error_rate:.3f}",
            file=sys.stderr,
        )
        return 1
    if report.get("baseline_comparison", {}).get("ok") is False:
        print("ERROR: regression detected against baseline", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
