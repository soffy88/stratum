"""Bounded projections of the P13 book synthesis (PR feat/bu2-synthesis-slim).

The stored synthesis row is the whole artefact: for the 18-chapter textbook it is
~1.7 MB, of which concept_system is ~1.3 MB. These tests pin the projection
contract — what is bounded, what is dropped, and that ``view=full`` still returns
the row unchanged so existing callers do not break.
"""

from __future__ import annotations

import json

from stratum.services.bu_v2_synthesis_view import (
    SYNTHESIS_FIELDS,
    build_synthesis_view,
    decode,
)


def _concept(cid: str, role: str, chapter: str) -> dict:
    return {
        "concept_id": cid,
        "label": f"Label {cid}",
        "role": role,
        "final_role": role,
        "confidence": 0.9,
        "definition": "d" * 300,
        "chapter_refs": [chapter],
        "prerequisites": [],
        "related_concepts": [],
    }


def _row() -> dict:
    concepts = {
        "core": [_concept(f"c{i}", "core", f"ch{i % 3}") for i in range(60)],
        "foundational": [_concept(f"f{i}", "foundational", "ch1") for i in range(10)],
        "derived": [_concept(f"d{i}", "derived", "ch2") for i in range(30)],
        "bridging": [],
        "terminal": [],
        "application": [],
    }
    claims = [
        {
            "claim_id": f"claim_{i}",
            "claim_statement": f"statement {i}",
            "is_supported": i % 4 != 0,
            "provenance": "AUTHOR_ASSERTED",
            "chapter_ids": [f"ch{i % 3}"],
            "evidence_ids": [f"ev_{i}"],
            "evidence_strengths": {f"ev_{i}": "DIRECT"},
        }
        for i in range(120)
    ]
    return {
        "id": "s1",
        "run_id": "br_1",
        "book_id": "sub_1",
        "created_at": "2026-10-13 00:00:00+00:00",
        "thesis": json.dumps(
            {
                "core_thesis": {
                    "statement": "Core thesis statement",
                    "provenance": "MODEL_INFERRED",
                },
                "conclusions": ["one"],
                "supporting_theses": ["a", "b"],
                "key_assumptions": ["k"],
                "central_questions": ["q"],
                "problem_statements": ["p"],
                "limitations": [f"lim {i}" for i in range(50)],
            }
        ),
        "problem_definition": "Problems: the problem",
        "concept_system": json.dumps(concepts),
        "argument_system": json.dumps({"major_arguments": [{"id": "a"}], "sub_arguments": []}),
        "mechanism_system": json.dumps({"mechanisms": [{"id": "m"} for _ in range(12)]}),
        "evidence_map": json.dumps(
            {
                "entries": claims,
                "evidence_coverage": 0.95,
                "contradiction_count": 0,
                "model_inference_ratio": 0.1,
                "unsupported_claim_count": 3,
            }
        ),
        "author_model": json.dumps({"worldview": ["centers on calculus"]}),
        "chapter_roles": json.dumps(
            {
                "assignments": [
                    {"chapter_id": f"ch{i}", "roles": ["FOUNDATION"], "confidence": 0.7}
                    for i in range(3)
                ]
            }
        ),
        "unresolved_questions": json.dumps([f"q{i}" for i in range(100)]),
        "contradictions": json.dumps({"contradictions": []}),
        "limitations": json.dumps([f"l{i}" for i in range(100)]),
        "synthesis_evidence": json.dumps({"concepts": [], "evidence": []}),
    }


def _size(payload) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str))


def test_summary_is_bounded_against_a_full_row():
    """The default view must not carry the row: this is the whole point."""
    row = _row()
    full = _size({k: v for k, v in row.items()})
    summary = build_synthesis_view(row, view="summary")
    assert _size(summary) < 200_000
    # And it must be a large fraction smaller than the row it came from.
    assert _size(summary) < full / 5


def test_summary_carries_counts_core_thesis_and_roles():
    s = build_synthesis_view(_row(), view="summary")
    assert s["view"] == "summary"
    assert set(s["available_views"]) == {"full", "summary", "concepts", "claims"}
    assert s["counts"]["concepts"] == 100
    assert s["counts"]["claims"] == 120
    assert s["counts"]["mechanisms"] == 12
    assert s["counts"]["arithmetic_arguments"] == {"major_arguments": 1, "sub_arguments": 0}
    assert s["thesis"]["core_thesis"] == "Core thesis statement"
    assert s["thesis"]["counts"]["supporting_theses"] == 2
    assert s["thesis"]["counts"]["limitations"] == 50
    assert s["claims_summary"]["unsupported_claim_count"] == 3
    assert s["chapters"]["chapter_count"] == 3
    assert s["concept_roles"] == {"core": 60, "foundational": 10, "derived": 30}
    assert s["unresolved_questions"]["count"] == 100
    assert s["core_concepts"]


def test_summary_core_concepts_are_id_label_only():
    """No definitions in the summary: that is what the concepts view is for."""
    s = build_synthesis_view(_row(), view="summary")
    for c in s["core_concepts"]:
        assert set(c) == {"concept_id", "label", "role", "chapter_refs"}


def test_summary_caps_core_concepts_at_limit():
    s = build_synthesis_view(_row(), view="summary", limit=5)
    assert len(s["core_concepts"]) == 5
    # Role order is core first, so the retained ones are the core concepts.
    assert all(c["role"] == "core" for c in s["core_concepts"])


def test_concepts_view_pages_and_reports_totals():
    row = _row()
    first = build_synthesis_view(row, view="concepts", limit=10, offset=0)
    assert first["total"] == 100
    assert len(first["concepts"]) == 10
    assert first["has_more"] is True
    second = build_synthesis_view(row, view="concepts", limit=10, offset=10)
    assert second["concepts"][0]["concept_id"] != first["concepts"][0]["concept_id"]
    last = build_synthesis_view(row, view="concepts", limit=10, offset=95)
    assert len(last["concepts"]) == 5
    assert last["has_more"] is False


def test_concept_roles_precede_derived():
    """Core and foundational come first: a reader wants the spine, not the tail."""
    # 60 core + 10 foundational + 30 derived: a 65-item window covers core and
    # foundational entirely, and derived only starts after both are exhausted.
    s = build_synthesis_view(_row(), view="concepts", limit=65, offset=0)
    roles = [c["role"] for c in s["concepts"]]
    assert roles == ["core"] * 60 + ["foundational"] * 5


def test_concept_roles_precede_derived_after_core_exhausted():
    """With core exhausted the next role starts, and derived is always last."""
    s = build_synthesis_view(_row(), view="concepts", limit=15, offset=60)
    roles = [c["role"] for c in s["concepts"]]
    assert roles == ["foundational"] * 10 + ["derived"] * 5
    # The very last page of a full walk-through is derived, never core.
    s_all = build_synthesis_view(_row(), view="concepts", limit=1000)
    assert s_all["concepts"][-1]["role"] == "derived"


def test_concepts_deduplicate_by_concept_id():
    row = _row()
    cs = json.loads(row["concept_system"])
    cs["terminal"] = [cs["derived"][0]]  # same id, different role
    row["concept_system"] = json.dumps(cs)
    s = build_synthesis_view(row, view="concepts", limit=500)
    ids = [c["concept_id"] for c in s["concepts"]]
    assert len(ids) == len(set(ids)) == 100


def test_claims_view_puts_supported_first():
    s = build_synthesis_view(_row(), view="claims", limit=120)
    supported = [c["is_supported"] for c in s["claims"]]
    # The unsupported ones (every 4th) are pushed to the end.
    assert supported[-30:] == [False] * 30
    assert s["total"] == 120


def test_claims_view_pages():
    s = build_synthesis_view(_row(), view="claims", limit=10, offset=100)
    assert len(s["claims"]) == 10
    assert s["has_more"] is True


def test_chapter_filter_narrows_both_item_views():
    row = _row()
    c = build_synthesis_view(row, view="concepts", limit=500, chapter="ch1")
    assert c["total"] < 100
    assert all("ch1" in x["chapter_refs"] for x in c["concepts"])
    cl = build_synthesis_view(row, view="claims", limit=500, chapter="ch2")
    assert cl["total"] < 120
    assert all("ch2" in x["chapter_ids"] for x in cl["claims"])


def test_full_view_returns_the_row_unchanged():
    """Backward compatibility: the pre-PR response was the raw row."""
    row = _row()
    full = build_synthesis_view(row, view="full")
    for f in SYNTHESIS_FIELDS:
        assert full[f] == row[f]
    assert full["created_at"] == str(row["created_at"])
    assert full["view"] == "full"


def test_unknown_view_falls_back_to_summary():
    assert build_synthesis_view(_row(), view="nonsense")["view"] == "summary"
    assert build_synthesis_view(_row(), view="")["view"] == "summary"


def test_decode_handles_text_dict_list_and_junk():
    assert decode('{"a": 1}') == {"a": 1}
    assert decode('"[\\"a\\"]"') == ["a"]
    assert decode({"a": 1}) == {"a": 1}
    assert decode([1, 2]) == [1, 2]
    assert decode(None) is None
    assert decode("not json") == "not json"


def test_survives_an_empty_row():
    """A run whose synthesis is empty must not 500 the page."""
    row = {"run_id": "br_x", "book_id": "s_x"}
    for view in ("summary", "concepts", "claims"):
        out = build_synthesis_view(row, view=view)
        assert out["view"] == view
    assert build_synthesis_view(row, view="summary")["counts"]["concepts"] == 0


def test_survives_non_string_parameters():
    """A direct handler call passes FastAPI's ``Query`` objects, not values."""
    row = _row()
    out = build_synthesis_view(row, view=object(), limit=object(), offset=object())
    assert out["view"] == "summary"
    assert len(out["core_concepts"]) == 50


def test_survives_malformed_json_fields():
    row = _row()
    row["concept_system"] = "not json"
    row["evidence_map"] = "{broken"
    row["thesis"] = "[["
    s = build_synthesis_view(row, view="summary")
    assert s["counts"]["concepts"] == 0
    assert s["counts"]["claims"] == 0
    assert s["thesis"]["core_thesis"] == ""
