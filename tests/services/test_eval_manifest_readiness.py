from pathlib import Path

from scripts.check_eval_manifest_readiness import build_readiness_report


def test_manifest_readiness_distinguishes_count_and_review_completeness():
    existing_path = str(Path(__file__))
    report = build_readiness_report(
        [
            {"query": f"q-{i}", "relevant_substrate_ids": [f"s-{i}"], "review_status": "candidate"}
            for i in range(50)
        ],
        [
            {
                "id": f"p-{i}",
                "path": existing_path,
                "layout": "unknown",
                "language": "unknown",
                "structure_elements": [],
                "required_markers": [],
                "review_status": "reviewed",
            }
            for i in range(20)
        ],
    )

    assert report["retrieval"]["threshold_met"] is True
    assert report["retrieval"]["provenance_complete"] is False
    assert report["parser"]["ready"] is True
    assert report["parser"]["files_complete"] is True
    assert report["ready"] is False


def test_manifest_readiness_requires_both_sides():
    report = build_readiness_report([], [])
    assert report["metric_results_available"] is False
    assert report["retrieval"]["ready"] is False
    assert report["parser"]["ready"] is False


def test_manifest_readiness_reports_missing_parser_files():
    report = build_readiness_report(
        [{"query": "q", "relevant_substrate_ids": ["s"], "review_status": "reviewed"}],
        [
            {
                "id": "p",
                "path": "/missing.pdf",
                "layout": "single",
                "language": "en",
                "structure_elements": [],
                "required_markers": [],
                "review_status": "reviewed",
            }
        ],
        min_retrieval_queries=1,
        min_parser_cases=1,
    )
    assert report["parser"]["files_checked"] is True
    assert report["parser"]["files_missing"] == 1
    assert report["parser"]["ready"] is False
