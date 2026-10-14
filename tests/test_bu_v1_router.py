"""Regression tests for the BU2 v1 router (PR bu2-wire)."""

from __future__ import annotations

import asyncio
import inspect
import re
import json


from stratum.api.routers import bu


def test_no_array_length_on_jsonb():
    src = inspect.getsource(bu)
    assert not re.search(r"(?<!jsonb_)array_length\(cu\.evidence_program_json", src)
    assert "jsonb_array_length(cu.evidence_program_json)" in src


def test_j_decodes_text_and_double_encoded_json():
    assert bu._j('["a"]') == ["a"]
    assert bu._j('"[\\"a\\"]"') == ["a"]
    assert bu._j(None, []) == []
    assert bu._j({"x": 1}) == {"x": 1}
    assert bu._j("not json") == "not json"


def test_claims_from_program_marks_unsupported_as_inference():
    program = [
        {"claim_ref": "A", "is_supported": True, "evidence_refs": ["ev1"]},
        {"claim_ref": "B", "is_supported": False, "evidence_refs": []},
        {"claim_ref": "C"},
        "junk",
    ]
    claims = bu._claims_from_program(program)
    assert [c["claim"] for c in claims] == ["A", "B", "C"]
    assert claims[0]["presented_as"] == "SOURCE"
    assert claims[1]["presented_as"] == "MODEL_INFERENCE"
    assert claims[2]["is_supported"] is None
    assert bu._claims_from_program({"entries": program[:1]})[0]["claim"] == "A"
    assert bu._claims_from_program(None) == []


def test_bu2_artifact_routes_registered():
    paths = {r.path for r in bu.router.routes}
    for p in (
        "/api/v1/bu/{run_id}/quality-gates",
        "/api/v1/bu/{run_id}/evidence",
        "/api/v1/bu/{run_id}/arguments",
        "/api/v1/bu/{run_id}/graph",
        "/api/v1/bu/{run_id}/concept-evolution",
        "/api/v1/bu/{run_id}/synthesis",
    ):
        assert p in paths


_SYNTH_ROW = {
    "id": "s1",
    "run_id": "br_1",
    # Must match the substrate_id the ownership check compares against.
    "book_id": "b",
    "created_at": "2026-10-13 00:00:00+00:00",
    "thesis": '{"core_thesis": {"statement": "Core"}}',
    "problem_definition": "Problems: p",
    "concept_system": '{"core": [{"concept_id": "c1", "label": "Limit", "chapter_refs": ["ch1"]}]}',
    "argument_system": '{"major_arguments": []}',
    "mechanism_system": '{"mechanisms": []}',
    "evidence_map": '{"entries": [{"claim_id": "cl1", "claim_statement": "A", '
    '"is_supported": true, "chapter_ids": ["ch1"], "evidence_ids": ["ev1"]}]}',
    "author_model": "{}",
    "chapter_roles": '{"assignments": []}',
    "unresolved_questions": "[]",
    "contradictions": "{}",
    "limitations": "[]",
    "synthesis_evidence": "{}",
}


def _patch_synth(monkeypatch):
    def fake_query(sql, params=None, limit=100):
        if "book_understandings_v2" in sql:
            return [{"id": "bu1", "substrate_id": "s", "book_id": "b"}]
        return [dict(_SYNTH_ROW)]

    monkeypatch.setattr(bu, "query", fake_query)


def test_synthesis_defaults_to_a_bounded_summary(monkeypatch):
    """The row is ~1.7 MB; the default response must not be."""
    _patch_synth(monkeypatch)
    out = asyncio.run(bu.get_synthesis("run", "u"))
    assert out["view"] == "summary"
    assert out["counts"]["concepts"] == 1
    assert out["counts"]["claims"] == 1
    assert "concept_system" not in out
    assert "evidence_map" not in out
    assert len(json.dumps(out, default=str)) < 200_000


def test_synthesis_full_view_preserves_the_old_response(monkeypatch):
    _patch_synth(monkeypatch)
    out = asyncio.run(bu.get_synthesis("run", "u", view="full"))
    assert out["concept_system"] == _SYNTH_ROW["concept_system"]
    assert out["evidence_map"] == _SYNTH_ROW["evidence_map"]
    assert out["created_at"] == _SYNTH_ROW["created_at"]
    assert out["run_id"] == "br_1"


def test_synthesis_concepts_and_claims_pages(monkeypatch):
    _patch_synth(monkeypatch)
    concepts = asyncio.run(bu.get_synthesis("run", "u", view="concepts", limit=10, offset=0))
    assert concepts["total"] == 1
    assert concepts["concepts"][0]["concept_id"] == "c1"
    claims = asyncio.run(bu.get_synthesis("run", "u", view="claims", limit=10, offset=0))
    assert claims["claims"][0]["is_supported"] is True
    # ?chapter= narrows both item views.
    empty = asyncio.run(bu.get_synthesis("run", "u", view="concepts", chapter="ch9"))
    assert empty["total"] == 0
    assert empty["concepts"] == []


def test_synthesis_rejects_an_unknown_view(monkeypatch):
    """A typo must not silently return the 1.7 MB row."""

    # The handler resolves an unknown view through the view module, which falls
    # back to summary, so a typo never falls through to the 1.7 MB row.
    _patch_synth(monkeypatch)
    out = asyncio.run(bu.get_synthesis("run", "u", view="everything"))
    assert out["view"] == "summary"


def test_synthesis_view_pattern_is_declared_on_the_route():
    """The OpenAPI schema must restrict view to the four known values."""
    route = next(r for r in bu.router.routes if getattr(r, "path", "").endswith("/synthesis"))
    patterns = {}
    for field in route.dependant.query_params:
        for m in field.field_info.metadata:
            if getattr(m, "pattern", None):
                patterns[field.name] = m.pattern
    assert patterns["view"] == "^(summary|full|concepts|claims)$"


def test_quality_gates_splits_six_dimension(monkeypatch):
    calls = []

    def fake_query(sql, params=None, limit=100):
        calls.append(sql)
        if "book_understandings_v2" in sql:
            return [
                {
                    "id": "bu1",
                    "substrate_id": "s",
                    "book_id": "b",
                    "reasoning_graph_id": None,
                    "argument_graph_id": None,
                }
            ]
        return [
            {
                "gate_number": 1,
                "gate_name": "H1_no_empty_chapter",
                "status": "PASS",
                "score": 1.0,
                "detail": "",
                "evidence": "{}",
                "checked_at": "t",
            },
            {
                "gate_number": 8,
                "gate_name": "six_dimension_score",
                "status": "PASS",
                "score": 9.9,
                "detail": "",
                "evidence": '{"dimensions": {"depth": 10}}',
                "checked_at": "t",
            },
        ]

    monkeypatch.setattr(bu, "query", fake_query)
    out = asyncio.run(bu.get_quality_gates("run", "u"))
    assert out["all_passed"] is True
    assert len(out["hard_gates"]) == 1
    assert out["six_dimension"]["evidence"] == {"dimensions": {"depth": 10}}


def test_learning_guide_orders_prerequisites_first(monkeypatch):
    def fake_query(sql, params=None, limit=100):
        if "book_understandings_v2" in sql:
            return [
                {
                    "id": "bu1",
                    "substrate_id": "s",
                    "book_id": "b",
                    "reasoning_graph_id": "g1",
                    "argument_graph_id": None,
                }
            ]
        if "chapter_understandings" in sql:
            return [
                {"chapter_id": "ch2", "concepts_introduced_refs": ["series"]},
                {"chapter_id": "ch1", "concepts_introduced_refs": ["sequence"]},
            ]
        if "reasoning_node" in sql:
            return [
                {
                    "id": "n2",
                    "node_type": "CONCEPT",
                    "label": "series",
                    "chapter_id": "ch2",
                    "metadata": "{}",
                },
                {
                    "id": "n1",
                    "node_type": "CONCEPT",
                    "label": "sequence",
                    "chapter_id": "ch1",
                    "metadata": None,
                },
            ]
        if "reasoning_edge" in sql:
            return [{"source_node_id": "n2", "target_node_id": "n1", "relation_type": "DEPENDS_ON"}]
        return []

    monkeypatch.setattr(bu, "query", fake_query)
    out = asyncio.run(bu.get_learning_guide("run", "u", 500, 0))
    assert [s["concept"] for s in out["steps"]] == ["sequence", "series"]
    assert out["steps"][1]["requires"] == ["sequence"]
    assert out["chapter_order"] == ["ch1", "ch2"]
