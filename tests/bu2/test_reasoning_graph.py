"""Reasoning graph tests — spec §5, §15.

The vocabularies of §5.2 are constrained, and so is everything §15 demands:

  no edge without a reason            (enforced in the model AND by NOT NULL)
  no relation invented without support
  no silent drop                       (everything unresolved is recorded)
  no global concept identity           (§2.1: book-scoped only)
"""

from __future__ import annotations

import pytest

from stratum.services.bu_v2_reasoning_graph import (
    EDGE_TYPES,
    EVIDENCE_STRENGTH_RANK,
    NODE_TYPES,
    BookReasoningGraph,
    ReasoningEdge,
    ReasoningNode,
    UnresolvedRelation,
    node_id,
)


def graph() -> BookReasoningGraph:
    g = BookReasoningGraph(graph_id="g1", run_id="r1", book_id="b1")
    g.add_node(ReasoningNode("n1", "CHAPTER", "1. Functions", chapter_id="ch1"))
    g.add_node(ReasoningNode("n2", "CHAPTER", "2. Limits", chapter_id="ch2"))
    return g


# ── §5.2 vocabularies ────────────────────────────────────────────────────────


@pytest.mark.parametrize("node_type", sorted(NODE_TYPES))
def test_every_allowed_node_type_is_accepted(node_type):
    g = BookReasoningGraph(graph_id="g", run_id="r", book_id="b")
    g.add_node(ReasoningNode("n", node_type, "label"))
    assert len(g.nodes) == 1


def test_unknown_node_type_is_refused():
    with pytest.raises(ValueError, match="unknown node type"):
        ReasoningNode("n", "SUMMARY_SECTION", "label")


@pytest.mark.parametrize("relation", sorted(EDGE_TYPES))
def test_every_allowed_relation_is_accepted(relation):
    g = graph()
    g.add_edge(
        ReasoningEdge("e", "n1", "n2", relation, reason="stated in the text")
    )
    assert len(g.edges) == 1


def test_unknown_relation_is_refused():
    with pytest.raises(ValueError, match="unknown relation"):
        ReasoningEdge("e", "n1", "n2", "RELATED_TO", reason="because")


# ── §6: no edge without a reason ─────────────────────────────────────────────


def test_edge_without_reason_is_refused_by_the_model():
    with pytest.raises(ValueError, match="requires a reason"):
        ReasoningEdge("e", "n1", "n2", "DEPENDS_ON", reason="   ")


def test_edge_without_reason_is_refused_by_the_database():
    """The model refusing is convenience; the NOT NULL column is the guarantee."""
    pytest.importorskip("psycopg2")
    import inspect

    from stratum.db import run_pg_migrations

    sql = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "src/stratum/db/pg_migrations/068_bu2_p12_reasoning_graph.sql"
    ).read_text()
    assert "reason         TEXT NOT NULL" in sql


def test_every_stored_edge_has_a_reason():
    g = graph()
    g.add_edge(ReasoningEdge("e", "n1", "n2", "DEPENDS_ON", reason="text says so"))
    assert all(e.reason.strip() for e in g.edges)


# ── §15: no silent drops ─────────────────────────────────────────────────────


def test_edge_to_missing_node_is_recorded_not_dropped():
    g = graph()
    g.add_edge(ReasoningEdge("e", "n1", "n_missing", "DEPENDS_ON", reason="x"))
    assert g.edges == [], "an edge with an unknown endpoint must not be created"
    assert len(g.unresolved) == 1
    u = g.unresolved[0]
    assert "n_missing" in u.reason
    assert u.fallback


def test_unresolved_requires_reason_and_fallback():
    with pytest.raises(ValueError, match="reason"):
        UnresolvedRelation(kind="edge", subject="s", reason="", source="test")
    u = UnresolvedRelation(kind="edge", subject="s", reason="no evidence", source="test")
    assert u.fallback, "a record must say what happened instead"


def test_duplicate_edge_keeps_the_better_supported_claim():
    g = graph()
    g.add_edge(ReasoningEdge("e1", "n1", "n2", "DEPENDS_ON", reason="weak", confidence=0.3))
    g.add_edge(ReasoningEdge("e2", "n1", "n2", "DEPENDS_ON", reason="strong", confidence=0.9))
    assert len(g.edges) == 1
    assert g.edges[0].confidence == 0.9


def test_uncertain_edge_is_capped():
    """§15's example shape: an uncertain relation is never dressed up."""
    e = ReasoningEdge("e", "n1", "n2", "DEPENDS_ON", reason="maybe", confidence=0.9, status="uncertain")
    assert e.confidence <= 0.4


# ── §11: evidence strength ───────────────────────────────────────────────────


def test_all_five_evidence_strengths_exist():
    assert set(EVIDENCE_STRENGTH_RANK) == {
        "DIRECT", "DEFINITION", "EXAMPLE", "DERIVED", "MODEL_INFERENCE"
    }


def test_unknown_evidence_strength_is_refused():
    with pytest.raises(ValueError, match="unknown evidence_type"):
        ReasoningEdge("e", "n1", "n2", "SUPPORTS", reason="r", evidence_type="VERY_STRONG")


def test_direct_edge_ratio_distinguishes_evidence_kinds():
    g = graph()
    g.add_edge(ReasoningEdge("e1", "n1", "n2", "DEPENDS_ON", reason="quoted", evidence_type="DIRECT"))
    g.add_edge(ReasoningEdge("e2", "n2", "n1", "SUPPORTS", reason="inferred", evidence_type="MODEL_INFERENCE"))
    assert g.direct_edge_ratio == 0.5


# ── §2.1: book-scoped, not a knowledge base ──────────────────────────────────


def test_graph_carries_no_global_concept_identity():
    g = graph()
    g.add_node(ReasoningNode("n3", "CONCEPT", "limit", chapter_id="ch2"))
    concept = g.nodes["n3"]
    assert concept.chapter_id == "ch2", "a concept node must be scoped to a chapter"
    blob = repr(g.to_dict())
    for banned in ("rf.", "refined_concept", "canonical_concept_id"):
        assert banned not in blob


def test_cross_chapter_edges_ignore_intra_chapter():
    g = graph()
    g.add_node(ReasoningNode("n3", "CONCEPT", "limit", chapter_id="ch1"))
    g.add_edge(ReasoningEdge("a", "n3", "n1", "DEPENDS_ON", reason="same chapter", confidence=0.8))
    g.add_edge(ReasoningEdge("b", "n2", "n1", "DEPENDS_ON", reason="across chapters", confidence=0.8))
    assert len(g.cross_chapter_edges()) == 1


def test_node_ids_are_stable_across_runs():
    a = node_id("e", "ch1", "ch2", "DEPENDS_ON")
    b = node_id("e", "ch1", "ch2", "DEPENDS_ON")
    assert a == b


def test_stats_counts_everything():
    g = graph()
    g.add_node(ReasoningNode("n3", "CONCEPT", "limit", chapter_id="ch2"))
    g.add_edge(ReasoningEdge("e", "n2", "n1", "DEPENDS_ON", reason="r", evidence_type="DIRECT"))
    s = g.stats()
    assert s["node_count"] == 3
    assert s["edge_count"] == 1
    assert s["edges_by_type"] == {"DEPENDS_ON": 1}
    assert s["direct_edge_ratio"] == 1.0


def test_confidence_is_clamped():
    n = ReasoningNode("n", "CHAPTER", "x", confidence=5.0)
    assert n.confidence == 1.0
    n2 = ReasoningNode("n2", "CHAPTER", "x", confidence=-3.0)
    assert n2.confidence == 0.0
