"""Release contracts for the frozen P2 qualification evidence."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
GOLD_SHA256 = "f858ef5f567b10e4c05ebb47bb9445f95356158a130f485e4ec4b5815676bfea"


def _read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_quality_baseline_is_bound_to_immutable_human_gold():
    gold = ROOT / "gold_retrieval_verified_v1.json"
    baseline = _read("evals/baselines/retrieval-baseline-v1.json")

    assert hashlib.sha256(gold.read_bytes()).hexdigest() == GOLD_SHA256
    assert baseline["gold_sha256"] == GOLD_SHA256
    assert baseline["gold_count"] == 100
    assert baseline["gold_type"] == "HUMAN_VERIFIED_RETRIEVAL"


def test_capacity_baseline_records_sampling_and_index_proof():
    baseline = _read("evals/baselines/retrieval-capacity-baseline-v1.json")

    assert baseline["dataset"] == "SYNTHETIC_CAPACITY_DATA"
    assert baseline["statistical_sufficiency"]["p99_minimum_samples"] == 100
    assert baseline["dataset_generator"] == "scripts/benchmark_vector_hybrid_capacity.py"
    assert baseline["dataset_generator_sha256"]
    assert baseline["query_plan_proof"]["python_full_table_scan"] is False
    assert baseline["vector_index_type"] == "IVFFlat"
    assert baseline["saturation"]["first_observed_concurrency"] == 8

    for scale in ("10000", "100000", "1000000"):
        for mode in ("vector", "hybrid", "final"):
            result = baseline["results"][scale][mode]
            assert result["sample_count"] == 20
            assert result["p99_ms"] == "INSUFFICIENT_SAMPLE_SIZE"

    for mode in ("vector", "hybrid", "final"):
        for row in baseline["concurrency_1m"][mode].values():
            assert row["p99_ms"] == "INSUFFICIENT_SAMPLE_SIZE"


def test_query_plan_and_timing_evidence_are_checksum_bound():
    plans = _read("evals/evidence/p2-query-plans-v1.json")
    timing = _read("evals/evidence/p2-component-timing-v1.json")

    assert plans["gold_sha256"] == GOLD_SHA256
    assert plans["plans"]["1000000"]["vector"]["index_used"] is True
    assert plans["python_full_table_scan"] is False
    assert timing["gold_sha256"] == GOLD_SHA256
    assert timing["scope_consistent"] is False
    assert timing["single_request_dominant_component"] == "EMBEDDING"
