"""Regression tests for the BU2 v1 router (PR bu2-wire)."""

from __future__ import annotations

import asyncio
import inspect
import re

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
    ):
        assert p in paths


def test_quality_gates_splits_six_dimension(monkeypatch):
    calls = []

    def fake_query(sql, params=None, limit=100):
        calls.append(sql)
        if "book_understandings_v2" in sql:
            return [{"id": "bu1", "substrate_id": "s", "book_id": "b",
                     "reasoning_graph_id": None, "argument_graph_id": None}]
        return [
            {"gate_number": 1, "gate_name": "H1_no_empty_chapter", "status": "PASS",
             "score": 1.0, "detail": "", "evidence": "{}", "checked_at": "t"},
            {"gate_number": 8, "gate_name": "six_dimension_score", "status": "PASS",
             "score": 9.9, "detail": "", "evidence": '{"dimensions": {"depth": 10}}',
             "checked_at": "t"},
        ]

    monkeypatch.setattr(bu, "query", fake_query)
    out = asyncio.run(bu.get_quality_gates("run", "u"))
    assert out["all_passed"] is True
    assert len(out["hard_gates"]) == 1
    assert out["six_dimension"]["evidence"] == {"dimensions": {"depth": 10}}
