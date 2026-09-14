import json

import pytest

from scripts.check_evaluation_regression import compare
from scripts.evaluate_layered_gold import evaluate


def _record(**overrides):
    record = {
        "query_id": "q1",
        "layer": "retrieval",
        "owner_id": "user-a",
        "source_ids": ["source-a"],
        "provenance": {"source_ref": "source-a"},
        "expected_output": {"source_ids": ["source-a"]},
        "expected_ids": ["source-a"],
        "actual_ids": ["source-a"],
    }
    record.update(overrides)
    return record


def test_layered_evaluation_requires_human_gold_envelope(tmp_path):
    path = tmp_path / "gold.json"
    path.write_text(json.dumps([_record()]), encoding="utf-8")

    result = evaluate(path)

    assert result["retrieval_metrics"]["recall_at_5"] == 1.0
    assert result["retrieval_metrics"]["recall_at_10"] == 1.0
    assert result["latency"] == {"p50_ms": 0.0, "p95_ms": 0.0}


def test_synthetic_only_gold_is_rejected(tmp_path):
    path = tmp_path / "gold.json"
    path.write_text(json.dumps([_record(gold_origin="synthetic")]), encoding="utf-8")

    with pytest.raises(ValueError, match="synthetic-only"):
        evaluate(path)


def test_regression_gate_fails_quality_and_leakage(tmp_path):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"metrics": {"recall_at_10": 1.0}}), encoding="utf-8")
    candidate.write_text(
        json.dumps({"metrics": {"recall_at_10": 0.9, "security_leakage": 1}}),
        encoding="utf-8",
    )

    result = compare(baseline, candidate)

    assert result["quality_regression"] is True
    assert "recall_at_10" in result["regressions"]
    assert "security_leakage" in result["regressions"]
