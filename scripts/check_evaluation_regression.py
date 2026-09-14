#!/usr/bin/env python3
"""Fail-closed comparison of two frozen evaluation result documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


QUALITY_KEYS = (
    "fragment_quality",
    "evidence_extraction",
    "claim_correctness",
    "concept_normalization",
    "relation_accuracy",
    "grounded_answer_correctness",
)


def _metrics(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = dict(payload.get("metrics", payload))
    aliases = {
        "Recall@5": "recall_at_5",
        "Recall@10": "recall_at_10",
        "MRR": "mrr",
        "nDCG@10": "ndcg_at_10",
    }
    for source, target in aliases.items():
        if source in metrics and target not in metrics:
            metrics[target] = metrics[source]
    return metrics


def compare(baseline: Path, candidate: Path, max_p95_delta: float = 0.0) -> dict:
    old = _metrics(baseline)
    new = _metrics(candidate)
    regressions = {}
    required_quality = ("recall_at_5", "recall_at_10", "mrr", "ndcg_at_10", *QUALITY_KEYS)
    required_contract = ("citation_recall", "citation_precision", "provenance_correctness")
    for key in (*required_quality, *required_contract):
        if key in old and key not in new:
            regressions[f"missing_{key}"] = {"baseline": old[key], "candidate": None}
        elif key in old and key in new and new[key] < old[key]:
            regressions[key] = {"baseline": old[key], "candidate": new[key]}
    old_latency = old.get("latency", {}).get("p95_ms")
    new_latency = new.get("latency", {}).get("p95_ms")
    if (
        old_latency is not None
        and new_latency is not None
        and new_latency - old_latency > max_p95_delta
    ):
        regressions["p95_latency"] = {"baseline": old_latency, "candidate": new_latency}
    for key in (
        "security_leakage",
        "isolation_leaks",
        "cross_user_leakage_count",
        "citation_regression",
        "provenance_regression",
    ):
        if new.get(key, 0) != 0:
            regressions[key] = new[key]
    return {"quality_regression": len(regressions) != 0, "regressions": regressions}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--max-p95-delta", type=float, default=0.0)
    args = parser.parse_args()
    result = compare(args.baseline, args.candidate, args.max_p95_delta)
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result["quality_regression"])


if __name__ == "__main__":
    raise SystemExit(main())
