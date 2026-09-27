from pathlib import Path

from scripts.build_parser_review_packet import build_review_packet


def test_parser_review_packet_is_deterministic_and_does_not_review_annotations(tmp_path: Path):
    source = tmp_path / "note.md"
    source.write_text("# Candidate note\n\nA short extracted body for review.", encoding="utf-8")
    cases = [
        {
            "id": "case-1",
            "path": str(source),
            "source_ref": "fixture:note",
            "review_status": "candidate",
            "layout": "unknown",
            "language": "unknown",
            "structure_elements": [],
            "required_markers": [],
        }
    ]

    first = build_review_packet(cases, preview_chars=20)
    second = build_review_packet(cases, preview_chars=20)

    assert first == second
    record = first["cases"][0]
    assert first["packet_type"] == "parser_human_review"
    assert first["annotations_unchanged"] is True
    assert record["availability"] == "present"
    assert record["sha256"]
    assert record["review_status"] == "candidate"
    assert record["layout"] == "unknown"
    assert len(record["preview"]) <= 20


def test_parser_review_packet_marks_missing_files_without_inventing_content(tmp_path: Path):
    cases = [
        {
            "id": "missing",
            "path": str(tmp_path / "missing.pdf"),
            "layout": "unknown",
            "language": "unknown",
            "structure_elements": [],
            "required_markers": [],
        }
    ]

    record = build_review_packet(cases)["cases"][0]
    assert record["availability"] == "missing"
    assert record["review_required"] is True
    assert "preview" not in record
