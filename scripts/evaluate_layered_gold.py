#!/usr/bin/env python3
"""Evaluate frozen, layer-specific AII gold records.

Input is JSON containing records with ``layer`` and a layer-specific expected
payload.  The runner does not infer labels from model output and never turns a
missing layer into a passing score.  This keeps ingestion, fragmentation,
evidence, claims, citations, concepts, relations, retrieval, and grounding
measurable independently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

LAYERS = (
    "ingestion",
    "fragmentation",
    "evidence_extraction",
    "claim_correctness",
    "citation_completeness",
    "concept_normalization",
    "relation_accuracy",
    "retrieval",
    "answer_grounding",
)


def validate_gold(records: list[dict[str, Any]]) -> None:
    """Validate the human-reviewed gold envelope before scoring it.

    A release gold record must identify its tenant and canonical source, retain
    an auditable provenance note, and carry an expected output.  Synthetic
    records are useful for development but are deliberately rejected here.
    """
    required = {"owner_id", "source_ids", "provenance", "expected_output"}
    for index, record in enumerate(records):
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"record {index}: missing gold fields: {', '.join(missing)}")
        if record.get("gold_origin") == "synthetic" or record.get("synthetic_only"):
            raise ValueError(f"record {index}: synthetic-only records cannot be release gold")
        if not isinstance(record["owner_id"], str) or not record["owner_id"]:
            raise ValueError(f"record {index}: owner_id must be non-empty")
        if not isinstance(record["source_ids"], list) or not record["source_ids"]:
            raise ValueError(f"record {index}: source_ids must be non-empty")
        if not isinstance(record["provenance"], dict) or not record["provenance"]:
            raise ValueError(f"record {index}: provenance must be an object")


def _normalise_retrieval_gold(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map the frozen v1 retrieval envelope to the layered gold envelope.

    This is an in-memory compatibility adapter; the frozen file is never
    rewritten.  New layers must use the explicit envelope directly.
    """
    normalised = []
    for record in records:
        if record.get("layer") == "retrieval":
            record = dict(record)
            record.setdefault("owner_id", record.get("user_id", ""))
            record.setdefault("source_ids", record.get("expected_source_ids", []))
            record.setdefault(
                "provenance",
                {
                    "source_ref": record.get("source_ref", ""),
                    "verification_basis": record.get("verification_basis", ""),
                },
            )
            record.setdefault(
                "expected_output",
                {"source_ids": record.get("expected_source_ids", [])},
            )
        normalised.append(record)
    return normalised


def _f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    precision = len(expected & actual) / len(actual)
    recall = len(expected & actual) / len(expected)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def score(record: dict[str, Any]) -> float:
    if record.get("layer") == "retrieval" and "expected_ids" in record and "actual_ids" in record:
        expected = set(map(str, record["expected_ids"]))
        ranked = list(map(str, record["actual_ids"]))[: int(record.get("k", 10))]
        if not expected:
            return 0.0
        hits = [rank for rank, item in enumerate(ranked, 1) if item in expected]
        recall = len(hits) / len(expected)
        reciprocal_rank = 1 / hits[0] if hits else 0.0
        dcg = sum(1 / math.log2(rank + 1) for rank in hits)
        ideal = min(len(expected), len(ranked))
        idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal + 1))
        return (recall + reciprocal_rank + (dcg / idcg if idcg else 0.0)) / 3
    expected = record.get("expected")
    actual = record.get("actual")
    if isinstance(expected, list) and isinstance(actual, list):
        return _f1(set(map(str, expected)), set(map(str, actual)))
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = set(expected) | set(actual)
        return (
            sum(expected.get(key) == actual.get(key) for key in keys) / len(keys) if keys else 1.0
        )
    return float(expected == actual)


def retrieval_metrics(record: dict[str, Any]) -> dict[str, float]:
    expected = set(map(str, record.get("expected_ids", [])))
    ranked = list(map(str, record.get("actual_ids", [])))[: int(record.get("k", 10))]
    hits = [rank for rank, item in enumerate(ranked, 1) if item in expected]
    recall = len(hits) / len(expected) if expected else 0.0
    mrr = 1 / hits[0] if hits else 0.0
    dcg = sum(1 / math.log2(rank + 1) for rank in hits)
    ideal = min(len(expected), len(ranked))
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal + 1))
    recall_at_5 = sum(1 for rank in hits if rank <= 5) / len(expected) if expected else 0.0
    return {
        "recall_at_5": recall_at_5,
        "recall_at_10": recall,
        "mrr": mrr,
        "ndcg_at_10": dcg / idcg if idcg else 0.0,
    }


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50_ms": 0.0, "p95_ms": 0.0}
    ordered = sorted(values)
    return {
        "p50_ms": round(statistics.median(ordered), 3),
        "p95_ms": round(ordered[min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)], 3),
    }


def _contract_metrics(record: dict[str, Any]) -> dict[str, float]:
    """Score citation/provenance fields when a production result supplies them."""
    expected = record.get("expected_output", {})
    actual = record.get("actual_output", {})
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return {}
    metrics: dict[str, float] = {}
    for name in ("citation_recall", "citation_precision", "provenance_correctness"):
        if name in actual:
            metrics[name] = float(actual[name])
        elif name in expected and expected[name] == actual.get(name):
            metrics[name] = 1.0
        elif name in expected:
            metrics[name] = 0.0
    return metrics


def evaluate(path: Path) -> dict[str, Any]:
    records = _normalise_retrieval_gold(json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(records, list) or not records:
        raise ValueError("gold must be a non-empty JSON list")
    validate_gold(records)
    grouped: dict[str, list[float]] = defaultdict(list)
    retrieval_rows: list[dict[str, float]] = []
    contract_rows: list[dict[str, float]] = []
    latencies: list[float] = []
    for index, record in enumerate(records):
        if record.get("layer") not in LAYERS:
            raise ValueError(f"record {index}: unknown layer")
        if "expected" not in record or "actual" not in record:
            if (
                record.get("layer") != "retrieval"
                or "expected_ids" not in record
                or "actual_ids" not in record
            ):
                raise ValueError(
                    f"record {index}: expected/actual or retrieval id lists are required"
                )
        grouped[record["layer"]].append(score(record))
        if record["layer"] == "retrieval":
            retrieval_rows.append(retrieval_metrics(record))
        contract_rows.append(_contract_metrics(record))
        if isinstance(record.get("latency_ms"), (int, float)):
            latencies.append(float(record["latency_ms"]))
    retrieval_summary = {}
    if retrieval_rows:
        retrieval_summary = {
            key: round(sum(row[key] for row in retrieval_rows) / len(retrieval_rows), 6)
            for key in retrieval_rows[0]
        }
    contract_summary = {}
    for key in sorted({key for row in contract_rows for key in row}):
        values = [row[key] for row in contract_rows if key in row]
        contract_summary[key] = round(sum(values) / len(values), 6)
    return {
        "gold_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "records": len(records),
        "layers": {
            layer: {"n": len(values), "score": round(sum(values) / len(values), 6)}
            for layer, values in sorted(grouped.items())
        },
        "retrieval_metrics": retrieval_summary,
        "citation_provenance_metrics": contract_summary,
        "latency": _percentiles(latencies),
        "missing_layers": [layer for layer in LAYERS if layer not in grouped],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gold", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.gold), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
