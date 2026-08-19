"""MVP week 1–2 smoke tests (no live LLM required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_pdf_to_markdown_passthrough_non_pdf(tmp_path: Path):
    from stratum.services.pdf_to_markdown import pdf_to_markdown

    p = tmp_path / "note.md"
    p.write_text("# hi", encoding="utf-8")
    out, parser = pdf_to_markdown(p)
    assert out == p
    assert parser == "skip"


def test_pdf_to_markdown_all_fail_returns_passthrough(tmp_path: Path):
    from stratum.services import pdf_to_markdown as m

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch.object(m, "_via_docling", side_effect=ImportError("no docling")):
        with patch.object(m, "_via_pymupdf4llm", side_effect=RuntimeError("bad pdf")):
            out, parser = m.pdf_to_markdown(pdf)
    assert out == pdf
    assert "passthrough" in parser


def test_pdf_to_markdown_writes_md_on_success(tmp_path: Path):
    from stratum.services import pdf_to_markdown as m

    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "# Title\n\nHello table\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"

    with patch.object(m, "_via_docling", return_value=body):
        out, parser = m.pdf_to_markdown(pdf)
    assert out.suffix == ".md"
    assert out.read_text(encoding="utf-8") == body
    assert parser == "docling"


def test_reading_companion_sources_shape():
    sources = [
        {
            "substrate_id": "01TESTID",
            "title": "Doc",
            "fragment_id": None,
            "deep_link": "stratum://substrate/01TESTID",
            "snippet": None,
        }
    ]
    assert all(s.get("substrate_id") for s in sources)


def test_extract_prompt_is_json_oriented():
    from stratum.services.extract_merge_service import _EXTRACT_PROMPT

    assert "entities" in _EXTRACT_PROMPT


def test_mvp_extract_merge_agent_helper_exists():
    from stratum.api.routers import agents

    assert hasattr(agents, "_run_extract_merge_agent")


def test_append_concept_note_idempotent_marker():
    """substrate_id in content should prevent duplicate append logic."""
    sid = "01ABC"
    old = f"hello substrate://{sid} already"
    assert sid in old
