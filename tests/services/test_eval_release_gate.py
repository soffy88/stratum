from scripts.check_eval_release_gate import check_reports


def _retrieval_report(**overrides):
    report = {
        "queries_total": 2,
        "evaluation_fingerprint": "gold-1",
        "error_rate": 0.0,
        "metrics": {"recall": 1.0, "precision": 1.0, "hit_rate": 1.0, "mrr": 1.0},
        "baseline_comparison": {"ok": True},
        "provenance": {"required": False, "unreviewed_queries": 2},
    }
    report.update(overrides)
    return report


def _parser_report(**overrides):
    report = {
        "cases": 2,
        "evaluation_fingerprint": "manifest-1",
        "pass_rate": 1.0,
        "by_dimension": {
            "single_column::en": {
                "pass_rate": 1.0,
                "marker_coverage": 1.0,
                "structure_coverage": 1.0,
            }
        },
        "baseline_comparison": {"regression": False, "ok": True},
        "provenance": {"required": False, "unreviewed_cases": 2},
    }
    report.update(overrides)
    return report


def test_eval_gate_requires_realistic_dataset_sizes_and_clean_retrieval():
    errors = check_reports(
        {"queries_total": 3, "error_rate": 0.0},
        {"cases": 2, "pass_rate": 1.0},
    )
    assert any("retrieval report has 3" in error for error in errors)
    assert any("parser report has 2" in error for error in errors)


def test_eval_gate_accepts_explicitly_small_local_fixture_without_regression():
    errors = check_reports(
        _retrieval_report(),
        _parser_report(),
        min_retrieval_queries=2,
        min_parser_cases=2,
        require_provenance=False,
    )
    assert errors == []


def test_eval_gate_rejects_incomplete_metric_report():
    errors = check_reports(
        _retrieval_report(metrics={"recall": 1.0}),
        _parser_report(by_dimension={}),
        min_retrieval_queries=2,
        min_parser_cases=2,
        require_provenance=False,
    )
    assert "retrieval metric precision is missing or non-finite" in errors
    assert "parser report is missing by_dimension results" in errors


def test_eval_gate_requires_retrieval_and_parser_baselines():
    errors = check_reports(
        _retrieval_report(baseline_comparison={}),
        _parser_report(baseline_comparison={}),
        min_retrieval_queries=2,
        min_parser_cases=2,
        require_provenance=False,
    )
    assert "retrieval report is missing a successful baseline comparison" in errors
    assert "parser report is missing a non-regressing baseline comparison" in errors


def test_eval_gate_rejects_non_finite_or_out_of_range_metrics():
    errors = check_reports(
        _retrieval_report(
            metrics={"recall": float("nan"), "precision": 1.2, "hit_rate": 0.5, "mrr": 0.5}
        ),
        _parser_report(
            pass_rate=float("inf"),
            by_dimension={
                "single_column::en": {
                    "pass_rate": 1.0,
                    "marker_coverage": -0.1,
                    "structure_coverage": 1.0,
                }
            },
        ),
        min_retrieval_queries=2,
        min_parser_cases=2,
        require_provenance=False,
    )
    assert "retrieval metric recall is missing or non-finite" in errors
    assert "retrieval metric precision is outside [0,1]" in errors
    assert "parser by_dimension results are incomplete or outside [0,1]" in errors


def test_eval_gate_fails_closed_on_malformed_numeric_fields():
    errors = check_reports(
        _retrieval_report(queries_total="not-a-number", error_rate="not-a-rate"),
        _parser_report(cases="not-a-number", pass_rate="not-a-rate"),
        min_retrieval_queries=2,
        min_parser_cases=2,
        require_provenance=False,
    )
    assert "retrieval queries_total must be a non-negative integer" in errors
    assert "parser cases must be a non-negative integer" in errors
    assert "retrieval error rate invalid is outside [0,1]" in errors
    assert "parser pass_rate is outside [0,1]" in errors


def test_eval_gate_rejects_non_object_reports_without_traceback():
    assert check_reports([], {}) == ["retrieval report must be a JSON object"]
    assert check_reports({}, []) == ["parser report must be a JSON object"]


def test_eval_gate_rejects_non_object_provenance_without_traceback():
    errors = check_reports(
        _retrieval_report(provenance=[]),
        _parser_report(provenance=[]),
        min_retrieval_queries=2,
        min_parser_cases=2,
    )
    assert "retrieval report provenance must be a JSON object" in errors
    assert "parser report provenance must be a JSON object" in errors
