"""P4 WorkingBU + P5 provenance/zoom behavior tests (§35, §§39-41, §§46-47)."""

import pytest

from stratum.knowledge.bu_v2_models import (
    BUStatement, BUVerificationState, ChapterDelta, ResolutionLevel,
    ResolutionNode, StatementProvenance,
)
from stratum.services.bu_provenance import (
    assign_levels, build_resolution, trace_lineage, validate_statement,
    verification_state_of_bu, zoom,
)
from stratum.services.working_bu import (
    apply_chapter_delta, init_working_bu, reconstruct_from_deltas,
)


def _delta(did="d1", run="run_1", ch="ch01"):
    return ChapterDelta(
        id=did, run_id=run, chapter_id=ch,
        new_concepts_refs=["c1"], revised_concepts_refs=["c0"],
        new_claims_refs=["cl1"], new_arguments_refs=["a1"],
        qualifies_prior_refs=["cl0"], contradicts_prior_refs=["clX"],
        revises_prior_refs=["cl0"], resolves_questions=["q0"],
        opens_questions=["q1"])


def test_apply_delta_folds_state():
    w = init_working_bu("run_1", "book_1", ["Why?"])
    w2 = apply_chapter_delta(w, _delta())
    assert w2.chapter_index == 1 and w2.version == 1
    assert "c1" in w2.concept_refs and "cl1" in w2.claim_refs
    assert "cl0" in w2.qualified_claims and "clX" in w2.contradicted_claims
    assert "q1" in w2.open_questions and "q0" in w2.resolved_questions
    assert w2.applied_delta_refs == ["d1"]
    assert w.chapter_index == 0  # input untouched (pure fold)


def test_double_apply_and_wrong_run_rejected():
    w = apply_chapter_delta(init_working_bu("run_1"), _delta())
    with pytest.raises(ValueError, match="already applied"):
        apply_chapter_delta(w, _delta())
    with pytest.raises(ValueError, match="belongs to run"):
        apply_chapter_delta(w, _delta(did="d2", run="run_2"))


def test_plain_summary_rejected_not_a_delta():
    w = init_working_bu("run_1")
    with pytest.raises(TypeError, match="not deltas"):
        apply_chapter_delta(w, {"summary": "chapter was about X"})


def test_reconstruct_deterministic_and_ordered():
    d2 = _delta(did="d2", ch="ch02", run="run_1")
    d2.new_claims_refs = ["cl2"]
    w1 = reconstruct_from_deltas("run_1", [_delta(), d2], book_id="book_1")
    w2 = reconstruct_from_deltas("run_1", [d2, _delta()], book_id="book_1")
    assert w1.claim_refs == w2.claim_refs == ["cl1", "cl2"]
    assert w1.version == 2 and w1.applied_delta_refs == ["d1", "d2"]


def test_provenance_gates():
    ok, _ = validate_statement(BUStatement(
        id="s1", statement="X.", provenance=StatementProvenance.AUTHOR_EXPLICIT,
        source_refs=["p3"]))
    assert ok
    ok2, f2 = validate_statement(BUStatement(
        id="s2", statement="X+Y.", provenance=StatementProvenance.AUTHOR_SYNTHESIZED,
        source_refs=["p3"]))
    assert not ok2 and any(">= 2" in f for f in f2)
    ok3, _ = validate_statement(BUStatement(
        id="s3", statement="X+Y.", provenance=StatementProvenance.AUTHOR_SYNTHESIZED,
        source_refs=["p3", "p9"], synthesis_trace="ch2+ch7 jointly state"))
    assert ok3
    ok4, f4 = validate_statement(BUStatement(
        id="s4", statement="Z.", provenance=StatementProvenance.STRATUM_DERIVED,
        derived_from_ku_refs=["k1"], derivation_reason="modus ponens",
        confidence=0.8))
    assert ok4
    ok5, f5 = validate_statement(BUStatement(
        id="s5", statement="Z.", provenance=StatementProvenance.STRATUM_DERIVED,
        derived_from_ku_refs=["raw:k9"], derivation_reason="r", confidence=0.5),
        raw_ku_ids=["raw:k9"])
    assert not ok5 and any("Raw KU" in f for f in f5)


def test_resolution_levels_and_zoom():
    items = [{"node_id": f"n{i}", "label": f"L{i}", "centrality": float(10 - i),
              "bu_refs": [], "ku_refs": [], "evidence_refs": []} for i in range(10)]
    nodes = assign_levels(items)
    grouped = build_resolution(nodes)
    assert grouped["ROOT"] and grouped["BRANCH"] and grouped["LEAF"]
    assert nodes[0].level == ResolutionLevel.ROOT
    assert nodes[-1].level == ResolutionLevel.LEAF
    edges = [("root", "b1"), ("b1", "l1")]
    nodes2 = [ResolutionNode(node_id="root", level=ResolutionLevel.ROOT),
              ResolutionNode(node_id="b1", level=ResolutionLevel.BRANCH),
              ResolutionNode(node_id="l1", level=ResolutionLevel.LEAF)]
    assert zoom("b1", nodes2, edges) == {"down": ["l1"], "up": ["root"]}


def test_lineage_complete_and_broken():
    idx = {"arguments": {"a1": {"next_ref": "k1"}},
           "kus": {"k1": {"next_ref": "e1"}},
           "evidence": {"e1": {"next_ref": "p3"}},
           "pages": {"p3": {}}}
    trail = trace_lineage("c1", {**idx, "claims": {"c1": {"next_ref": "a1"}}})
    assert trail["links"] == [("claim", "c1"), ("argument", "a1"), ("ku", "k1"),
                              ("evidence", "e1"), ("page", "p3")]
    assert trail["complete"] is True
    t2 = trace_lineage("k9", idx)
    assert t2["complete"] is False and t2["broken_at"] == ("claim", "k9")


def test_verification_state_no_fake_percentage():
    assert verification_state_of_bu({}, 0.0, 0) == BUVerificationState.UNVERIFIED
    assert verification_state_of_bu({"a": 1.0}, 0.5, 1) == BUVerificationState.UNVERIFIED
    assert verification_state_of_bu({"a": 1.0}, 0.95, 0) == BUVerificationState.VERIFIED
    assert verification_state_of_bu({"a": 1.0}, 0.7, 0) == BUVerificationState.QUALIFIED
    assert verification_state_of_bu({"a": 1.0}, 0.3, 0) == BUVerificationState.PARTIAL
