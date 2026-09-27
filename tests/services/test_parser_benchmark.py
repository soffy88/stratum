from scripts.eval_parser_benchmark import (
    aggregate,
    compare_reports,
    score_markdown,
    validate_manifest,
)


def test_parser_score_uses_layout_language_and_structure_dimensions():
    case = {
        "id": "table-en",
        "source_ref": "fixture:table-en",
        "reviewer": "test-reviewer",
        "review_status": "reviewed",
        "layout": "multi_column",
        "language": "en",
        "structure_elements": ["heading", "table"],
        "required_markers": ["Results"],
        "min_chars": 10,
    }
    result = score_markdown("# Results\n\n| a | b |\n|---|---|\n", case)
    assert result["pass"] is True
    assert result["layout"] == "multi_column"
    assert result["language"] == "en"
    assert result["structure_coverage"] == 1.0
    assert result["source_ref"] == "fixture:table-en"
    assert result["reviewer"] == "test-reviewer"
    assert result["review_status"] == "reviewed"


def test_parser_aggregate_groups_dimensions():
    results = [
        {"id": "a", "layout": "single", "language": "en", "pass": True, "parser": "docling"},
        {"id": "b", "layout": "single", "language": "en", "pass": False, "parser": "pymupdf4llm"},
    ]
    report = aggregate(results)
    assert report["cases"] == 2
    assert report["pass_rate"] == 0.5
    assert report["by_dimension"]["single::en"]["passed"] == 1


def test_parser_manifest_validation_catches_duplicate_ids_and_unknown_dimensions():
    errors = validate_manifest(
        [
            {
                "id": "same",
                "path": "a.pdf",
                "layout": "single",
                "language": "en",
                "structure_elements": ["not-a-dimension"],
                "required_markers": ["ok"],
            },
            {
                "id": "same",
                "path": "b.pdf",
                "layout": "single",
                "language": "en",
                "structure_elements": [],
                "required_markers": [],
            },
        ]
    )
    assert any("duplicated" in error for error in errors)
    assert any("unsupported dimension" in error for error in errors)


def test_parser_manifest_can_require_human_provenance():
    errors = validate_manifest(
        [
            {
                "id": "case-1",
                "path": "x.pdf",
                "layout": "single_column",
                "language": "zh",
                "structure_elements": [],
                "required_markers": [],
            }
        ],
        require_provenance=True,
    )
    assert any("source_ref" in error for error in errors)
    assert any("review_status" in error for error in errors)


def test_parser_manifest_can_require_existing_files(tmp_path):
    missing = validate_manifest(
        [
            {
                "id": "case-1",
                "path": str(tmp_path / "missing.pdf"),
                "layout": "single_column",
                "language": "en",
                "structure_elements": [],
                "required_markers": [],
            }
        ],
        require_files=True,
    )
    assert any("does not point to a file" in error for error in missing)


def test_parser_manifest_rejects_invalid_optional_review_metadata():
    errors = validate_manifest(
        [
            {
                "id": "case-1",
                "path": "x.pdf",
                "layout": "single_column",
                "language": "en",
                "structure_elements": [],
                "required_markers": [],
                "review_status": "approved",
                "reviewer": "",
                "notes": 42,
            }
        ]
    )
    assert any("review_status" in error for error in errors)
    assert any("reviewer" in error for error in errors)
    assert any("notes" in error for error in errors)


def test_parser_baseline_comparison_is_tolerance_aware():
    comparison = compare_reports(
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.79},
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.8},
        tolerance=0.02,
    )
    assert comparison["regression"] is False
    assert comparison["ok"] is True
    comparison = compare_reports(
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.79},
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.8},
        tolerance=0.0,
    )
    assert comparison["regression"] is True
    assert comparison["ok"] is False


def test_parser_baseline_comparison_rejects_missing_baseline_rate():
    comparison = compare_reports(
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.9},
        {"cases": 20, "evaluation_fingerprint": "manifest-1"},
    )
    assert comparison["ok"] is False
    assert comparison["regression"] is True
    assert "baseline report pass_rate is missing or non-finite" in comparison["errors"]


def test_parser_baseline_comparison_rejects_different_case_count():
    comparison = compare_reports(
        {"cases": 20, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.9},
        {"cases": 25, "evaluation_fingerprint": "manifest-1", "pass_rate": 0.9},
    )
    assert comparison["ok"] is False
    assert "baseline report uses a different cases count" in comparison["errors"]


def test_parser_evaluation_fingerprint_is_deterministic():
    from scripts.eval_parser_benchmark import evaluation_fingerprint

    assert evaluation_fingerprint([{"id": "a", "path": "a.pdf"}]) == evaluation_fingerprint(
        [{"path": "a.pdf", "id": "a"}]
    )


def test_parser_score_exposes_missing_dimensions_and_failure_reasons():
    result = score_markdown(
        "short",
        {
            "id": "bad",
            "layout": "single",
            "language": "en",
            "structure_elements": ["table"],
            "required_markers": ["Results"],
            "min_chars": 10,
        },
    )
    assert result["pass"] is False
    assert result["missing_markers"] == ["Results"]
    assert result["missing_structure_elements"] == ["table"]
    assert set(result["failure_reasons"]) == {
        "missing_required_markers",
        "missing_structure_elements",
        "below_min_chars",
    }


def test_parser_score_rejects_passthrough_instead_of_scoring_pdf_bytes():
    result = score_markdown(
        "%PDF-1.7 binary-looking content",
        {
            "id": "passthrough",
            "layout": "unknown",
            "language": "unknown",
            "structure_elements": [],
            "required_markers": [],
            "min_chars": 0,
            "parser": "passthrough:docling:ModuleNotFoundError",
        },
    )
    assert result["pass"] is False
    assert result["failure_reasons"] == ["parser_passthrough"]
