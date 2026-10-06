"""Argument graph tests — spec §8.

The distinction the whole module turns on: the author *asserted* something is not
the author *argued* it. A chain needs a claim, evidence and a conclusion; two of
three is a partial argument and is recorded as such rather than promoted.
"""

from __future__ import annotations

from stratum.knowledge.bu_v2_models import ChapterUnderstanding, EvidenceProgramItem
from stratum.services.bu_v2_argument_analyzer import (
    EDGE_KINDS,
    NODE_KINDS,
    ArgumentAnalyzer,
    ArgumentEdge,
    ArgumentNode,
)


def cu(n, thesis="a thesis", mechanisms=("a mechanism",), qualifications=("a limit",),
       programs=1, supported=True):
    return ChapterUnderstanding(
        id=f"cu{n}", run_id="r", chapter_id=f"ch{n}", chapter_thesis=thesis,
        mechanisms_refs=list(mechanisms), qualifications=list(qualifications),
        assumptions=list(qualifications),
        evidence_program=[
            EvidenceProgramItem(
                claim_ref=f"claim {i}", evidence_refs=[f"ev{n}{i}"], is_supported=supported
            )
            for i in range(programs)
        ],
    )


def analyze(chapters):
    return ArgumentAnalyzer().analyze(chapters, run_id="r", book_id="b")


# ── §8 vocabularies ──────────────────────────────────────────────────────────


def test_vocabularies_match_the_spec():
    assert NODE_KINDS == {"CLAIM", "EVIDENCE", "REASONING", "CONCLUSION"}
    assert EDGE_KINDS == {"SUPPORTS", "DERIVES", "CHALLENGES", "SUMMARIZES"}


def test_unknown_node_kind_is_refused():
    try:
        ArgumentNode("n", "TOPIC", "x")
    except ValueError as exc:
        assert "unknown argument node" in str(exc)
    else:
        raise AssertionError("an unknown node kind must be refused")


def test_unknown_edge_kind_is_refused():
    try:
        ArgumentEdge("e", "a", "b", "PROVES", reason="because")
    except ValueError as exc:
        assert "unknown argument edge" in str(exc)
    else:
        raise AssertionError("an unknown edge kind must be refused")


# ── chain shape ──────────────────────────────────────────────────────────────


def test_complete_chain_has_four_node_kinds():
    a = analyze([cu(1)])
    c = a.chains[0]
    assert c.complete
    assert c.claim.node_kind == "CLAIM"
    assert c.evidence[0].node_kind == "EVIDENCE"
    assert c.reasoning[0].node_kind == "REASONING"
    assert c.conclusion is not None and c.conclusion.node_kind == "CONCLUSION"


def test_chain_carries_the_four_edges():
    a = analyze([cu(1)])
    kinds = {e.edge_kind for e in a.chains[0].edges}
    assert kinds == {"SUPPORTS", "DERIVES", "SUMMARIZES"}


def test_every_edge_has_a_reason():
    a = analyze([cu(1), cu(2)])
    assert a.edges
    assert all(e.reason.strip() for e in a.edges)


def test_chain_without_mechanism_is_incomplete_and_recorded():
    a = analyze([cu(1, mechanisms=())])
    assert not a.chains[0].complete
    assert a.unresolved
    assert "no evidenced conclusion" in a.unresolved[0].reason or "no stated qualification" in a.unresolved[0].reason


def test_chain_without_evidence_is_incomplete():
    a = analyze([cu(1, programs=0)])
    assert not a.chains[0].complete
    assert not a.chains[0].evidence


def test_unsupported_evidence_lowers_confidence():
    strong = analyze([cu(1, supported=True)]).chains[0]
    weak = analyze([cu(1, supported=False)]).chains[0]
    assert strong.evidence[0].confidence > weak.evidence[0].confidence


def test_chapter_without_a_thesis_is_recorded():
    a = analyze([ChapterUnderstanding(id="cu9", run_id="r", chapter_id="ch9")])
    assert a.chains == []
    assert a.unresolved
    assert "neither a thesis nor a question" in a.unresolved[0].reason


# ── §13: at least five reasoning chains ──────────────────────────────────────


def test_many_chapters_produce_many_chains():
    a = analyze([cu(i, thesis=f"thesis {i}") for i in range(1, 9)])
    assert len(a.chains) >= 5


# ── §2.3: not an evidence oracle ─────────────────────────────────────────────


def test_graph_makes_no_truth_claim():
    """§2.3: evidence grounds a claim, it does not certify it.

    Checked against the serialised structure, not a Python repr: a repr of a
    boolean renders as "is_supported=True", which is not a truth claim and would
    fail a naive substring search.
    """
    a = analyze([cu(1)])
    keys = {k for c in a.to_dict()["chains"] for k in c}
    keys |= set(a.stats())
    for banned in ("verified", "is_true", "correct", "accuracy", "truth"):
        assert not any(banned in k.lower() for k in keys), f"{banned} appears as a field"
    blob = repr(a.to_dict()).lower()
    for banned in ("cx.", "learning_progress", "mastery", "fsrs"):
        assert banned not in blob, f"{banned} leaks into the argument graph"


def test_chains_sorted_complete_first():
    a = analyze([cu(1), cu(2, mechanisms=())])
    assert a.chains[0].complete
    assert not a.chains[-1].complete


def test_stats_count_everything():
    a = analyze([cu(1), cu(2)])
    s = a.stats()
    assert s["chain_count"] == 2
    assert s["node_count"] == len(a.nodes)
    assert s["edge_count"] == len(a.edges)


def test_empty_input_is_safe():
    a = analyze([])
    assert a.chains == []
    assert a.stats()["chain_count"] == 0


def test_every_argument_edge_carries_evidence_refs():
    """§6 requires evidence on every edge.

    The persistence layer had a literal `[]` for argument_edge.evidence_refs
    because ArgumentEdge had no such field, so a persisted argument graph
    looked evidenced in memory and empty in the database.
    """
    chapters = [cu(1), cu(2)]
    arg = ArgumentAnalyzer().analyze(chapters, run_id="r", book_id="b")
    assert arg.edges, "fixture must produce edges for this test to mean anything"
    for e in arg.edges:
        assert e.evidence_refs, f"{e.edge_id} ({e.edge_kind}) persisted with no evidence"


def test_evidence_refs_survive_serialisation():
    chapters = [cu(1), cu(2)]
    arg = ArgumentAnalyzer().analyze(chapters, run_id="r", book_id="b")
    for e in arg.edges:
        assert e.to_dict()["evidence_refs"] == list(e.evidence_refs)
