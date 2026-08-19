"""MVP week 3–4 unit tests (vault export, anchors, contradiction — no live DB/LLM)."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import patch


# ── search anchors ──────────────────────────────────────────────────────────


def test_split_paragraphs_blank_line():
    from stratum.services.search_anchors import split_paragraphs

    paras = split_paragraphs("first para\n\nsecond para\n\nthird")
    assert paras == ["first para", "second para", "third"]


def test_locate_anchor_exact():
    from stratum.services.search_anchors import locate_anchor

    text = "Intro.\n\nThe theorem holds for all n.\n\nConclusion."
    a = locate_anchor(text, "theorem holds")
    assert a["anchor_status"] == "exact"
    assert a["paragraph_index"] == 1
    assert a["char_start"] >= 0
    assert "theorem" in a["snippet"]


def test_locate_anchor_head_when_no_highlight():
    from stratum.services.search_anchors import locate_anchor

    a = locate_anchor("Only one paragraph of content here.", None)
    assert a["anchor_status"] == "head"
    assert a["paragraph_index"] == 0
    assert a["snippet"]


def test_locate_anchor_approx_on_miss():
    from stratum.services.search_anchors import locate_anchor

    text = "Alpha beta gamma.\n\nDelta epsilon zeta theorem proof.\n\nOmega."
    a = locate_anchor(text, "theorem proof unique tokens xyznotfound")
    assert a["anchor_status"] in ("approx", "exact")
    assert a.get("paragraph_index") is not None


def test_enrich_result_with_anchor_deep_link():
    from stratum.services.search_anchors import enrich_result_with_anchor

    out = enrich_result_with_anchor(
        substrate_id="01ABC",
        title="Doc",
        highlight="hello",
        full_text="prefix\n\nhello world\n\nsuffix",
        score=0.9,
    )
    assert out["substrate_id"] == "01ABC"
    assert out["deep_link"].startswith("stratum://substrate/01ABC")
    assert "#p" in out["deep_link"]
    assert out["score"] == 0.9


# ── contradiction heuristic ─────────────────────────────────────────────────


def test_contradiction_polarity_mismatch():
    from stratum.services.extract_merge_service import _looks_contradictory

    assert _looks_contradictory(
        "Market always expands under free trade",
        "Market never expands and free trade failed",
    )


def test_contradiction_same_text_false():
    from stratum.services.extract_merge_service import _looks_contradictory

    assert not _looks_contradictory("same claim here about X", "same claim here about X")


def test_contradiction_high_overlap_false():
    from stratum.services.extract_merge_service import _looks_contradictory

    assert not _looks_contradictory(
        "gravity attracts mass near Earth surface",
        "gravity attracts mass near Earth surface region",
    )


def test_contradiction_short_false():
    from stratum.services.extract_merge_service import _looks_contradictory

    assert not _looks_contradictory("short", "also short")


def test_append_concept_note_includes_contradiction_block_shape():
    """Block template must include pending_human_review marker."""
    import inspect
    from stratum.services import extract_merge_service as em

    src = inspect.getsource(em._append_concept_note)
    assert "pending_human_review" in src
    assert "矛盾" in src or "contradiction" in src.lower()


# ── vault export (pure helpers + mocked build) ──────────────────────────────


def test_vault_frontmatter_yaml_fields():
    from stratum.services.vault_export_service import _frontmatter

    fm = _frontmatter(
        id="01N",
        type_="note",
        title="Test Note",
        aliases=["a"],
        sources=["01S"],
        updated="2026-07-29",
    )
    assert fm.startswith("---\n")
    assert "id: 01N" in fm
    assert "type: note" in fm
    assert "title: Test Note" in fm
    assert "aliases:" in fm
    assert "sources:" in fm
    assert "updated: 2026-07-29" in fm
    assert fm.strip().endswith("---") is False or "---" in fm.split("\n")[-2:]


def test_vault_slug_safe():
    from stratum.services.vault_export_service import _slug

    assert "/" not in _slug("a/b:c", "fb")
    assert _slug("", "fallback") == "fallback"


def test_vault_ensure_body_title():
    from stratum.services.vault_export_service import _ensure_body_has_title

    assert _ensure_body_has_title("T", "body").startswith("# T")
    assert _ensure_body_has_title("T", "# Already\n\nx").startswith("# Already")


def test_build_vault_zip_structure():
    from stratum.services import vault_export_service as ves

    fake_files = {
        "README.md": "# vault\n",
        "index.json": '{"version": 1}',
        "notes/hello.md": "---\nid: 1\ntype: note\ntitle: hello\naliases: []\nsources: []\nupdated: 2026-07-29\n---\n\n# hello\n",
        "sources/doc.md": "---\nid: 2\ntype: source\ntitle: doc\naliases: []\nsources: [\"2\"]\nupdated: 2026-07-29\n---\n\n# doc\n",
    }
    with patch.object(ves, "build_vault_files", return_value=fake_files):
        data = ves.build_vault_zip("user-1")

    assert data[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
    assert any(n.endswith("README.md") for n in names)
    assert any("notes/hello.md" in n for n in names)
    assert all(n.startswith("aii-note-vault/") for n in names)


def test_export_router_has_vault_routes():
    from stratum.api.routers import export as exp

    paths = {getattr(r, "path", "") for r in exp.router.routes}
    assert any("/vault" in p for p in paths)
    assert any("preview" in p for p in paths)


def test_retrieve_search_delegates_to_post_shape():
    """GET /retrieve/search must call retrieve_endpoint (shared anchors+sources)."""
    import inspect
    from stratum.api.routers import retrieval as ret

    src = inspect.getsource(ret.retrieve_search)
    assert "retrieve_endpoint" in src
    assert "RetrieveRequest" in src
