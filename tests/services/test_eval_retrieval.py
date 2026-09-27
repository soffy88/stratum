from scripts.eval_retrieval import (
    _first_relevant_rank,
    _metric_summary,
    _trace_provenance,
    compare_reports,
    validate_golden_set,
)


def test_retrieval_eval_reports_standard_metrics():
    metrics = _metric_summary(["a", "b", "c"], {"b", "x"}, 3)
    assert metrics == {
        "recall": 0.5,
        "precision": 1 / 3,
        "hit_rate": 1.0,
        "mrr": 0.5,
    }


def test_retrieval_golden_validation_rejects_duplicates_and_empty_relevance():
    errors = validate_golden_set(
        [
            {"query": "same", "relevant_substrate_ids": ["a", "a"]},
            {"query": "same", "relevant_substrate_ids": []},
        ]
    )
    assert any("duplicated" in error for error in errors)
    assert any("contains duplicates" in error for error in errors)
    assert any("non-empty array" in error for error in errors)


def test_retrieval_baseline_comparison_reports_metric_regression():
    comparison = compare_reports(
        {
            "queries_total": 50,
            "evaluation_fingerprint": "gold-1",
            "metrics": {"recall": 0.7, "precision": 0.5, "hit_rate": 1.0, "mrr": 0.4},
        },
        {
            "queries_total": 50,
            "evaluation_fingerprint": "gold-1",
            "metrics": {"recall": 0.8, "precision": 0.5, "hit_rate": 1.0, "mrr": 0.45},
        },
    )
    assert comparison["ok"] is False
    assert set(comparison["regressions"]) == {"recall", "mrr"}
    assert abs(comparison["regressions"]["recall"] + 0.1) < 1e-9


def test_retrieval_baseline_comparison_rejects_incomplete_baseline():
    comparison = compare_reports(
        {
            "queries_total": 50,
            "evaluation_fingerprint": "gold-1",
            "metrics": {"recall": 0.7, "precision": 0.5, "hit_rate": 1.0, "mrr": 0.4},
        },
        {"queries_total": 50, "evaluation_fingerprint": "gold-1", "metrics": {"recall": 0.8}},
    )
    assert comparison["ok"] is False
    assert "baseline metric precision is missing or non-finite" in comparison["errors"]


def test_retrieval_baseline_comparison_rejects_different_query_count():
    comparison = compare_reports(
        {
            "queries_total": 50,
            "evaluation_fingerprint": "gold-1",
            "metrics": {"recall": 0.7, "precision": 0.5, "hit_rate": 1.0, "mrr": 0.4},
        },
        {
            "queries_total": 55,
            "evaluation_fingerprint": "gold-1",
            "metrics": {"recall": 0.7, "precision": 0.5, "hit_rate": 1.0, "mrr": 0.4},
        },
    )
    assert comparison["ok"] is False
    assert "baseline report uses a different queries_total" in comparison["errors"]


def test_retrieval_evaluation_fingerprint_is_deterministic():
    from scripts.eval_retrieval import evaluation_fingerprint

    assert evaluation_fingerprint(
        [{"query": "q", "relevant_substrate_ids": ["s"]}]
    ) == evaluation_fingerprint([{"relevant_substrate_ids": ["s"], "query": "q"}])


def test_retrieval_trace_reports_first_relevant_rank():
    assert _first_relevant_rank(["a", "b", "c"], {"b"}, 3) == 2
    assert _first_relevant_rank(["a", "b", "c"], {"c"}, 2) is None


def test_retrieval_trace_preserves_review_provenance():
    trace = _trace_provenance(
        {
            "query_id": "q-1",
            "source_ref": "review-sheet:7",
            "reviewer": "alice",
            "review_status": "reviewed",
        }
    )
    assert trace == {
        "query_id": "q-1",
        "source_ref": "review-sheet:7",
        "reviewer": "alice",
        "review_status": "reviewed",
    }


def test_retrieval_golden_validation_can_require_human_provenance():
    errors = validate_golden_set(
        [{"query": "q", "relevant_substrate_ids": ["s"]}],
        require_provenance=True,
    )
    assert any("source_ref" in error for error in errors)
    assert any("review_status" in error for error in errors)


def test_retrieval_golden_validation_rejects_invalid_optional_review_metadata():
    errors = validate_golden_set(
        [
            {
                "query": "q",
                "relevant_substrate_ids": ["s"],
                "review_status": "approved",
                "reviewer": "",
                "rationale": "",
            }
        ]
    )
    assert any("review_status" in error for error in errors)
    assert any("reviewer" in error for error in errors)
    assert any("rationale" in error for error in errors)
