from pathlib import Path

from scripts.discover_parser_candidates import discover_candidates
from scripts.eval_parser_benchmark import validate_manifest


def test_parser_candidate_discovery_is_deterministic_and_pdf_only(tmp_path: Path):
    (tmp_path / "b.pdf").write_bytes(b"pdf")
    (tmp_path / "a.pdf").write_bytes(b"pdf")
    (tmp_path / "ignore.md").write_text("not a PDF", encoding="utf-8")

    first = discover_candidates(tmp_path)
    second = discover_candidates(tmp_path)

    assert first == second
    assert [Path(case["path"]).name for case in first] == ["a.pdf", "b.pdf"]
    assert all(case["review_status"] == "candidate" for case in first)
    assert validate_manifest(first, min_cases=2) == []
    assert validate_manifest(first, min_cases=2, require_provenance=True)


def test_parser_candidate_discovery_limit_must_be_positive(tmp_path: Path):
    try:
        discover_candidates(tmp_path, limit=0)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("zero limit must be rejected")
