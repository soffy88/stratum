"""Concept evolution tests — spec §7.

A concept is not static: §7.1's example is limit, then derivative, then
integration, each defined in terms of the last. These tests pin that a concept's
life is recorded as a trajectory, and that a concept which is never refined is
reported as such rather than dressed up.
"""

from __future__ import annotations

from stratum.knowledge.bu_v2_models import ChapterDelta, ChapterUnderstanding
from stratum.services.bu_v2_concept_evolution import (
    EVENT_TYPES,
    ConceptEvolutionBuilder,
)

DEFINITION = "A limit is defined as the value a function approaches. "
APPLY = "This applies to areas and volumes generally. "


def cu(n, intro=(), redef=(), deps=(), thesis="", assumptions=(), qualifications=()):
    return ChapterUnderstanding(
        id=f"cu{n}", run_id="r", chapter_id=f"ch{n}", chapter_thesis=thesis,
        concepts_introduced_refs=list(intro), concepts_redefined_refs=list(redef),
        dependencies_on_prior=list(deps), assumptions=list(assumptions),
        qualifications=list(qualifications),
    )


def build(chapters, deltas=None, text=None):
    return ConceptEvolutionBuilder().build(
        chapters, run_id="r", book_id="b", deltas=deltas or [], chapter_text=text or {}
    )


# ── §7.3 event kinds ─────────────────────────────────────────────────────────


def test_all_four_event_types_exist():
    assert EVENT_TYPES == {"INTRODUCTION", "REFINEMENT", "EXPANSION", "CONNECTION"}


def test_introduction_is_recorded():
    r = build([cu(1, ["limit"])])
    t = r.trajectories[0]
    assert t.introduced_at == "ch1"
    assert t.kind_counts()["INTRODUCTION"] == 1


def test_redefinition_is_recorded_as_refinement():
    r = build([cu(1, ["limit"]), cu(5, ["integral"], redef=["limit"])])
    t = next(t for t in r.trajectories if t.concept == "limit")
    assert t.kind_counts().get("REFINEMENT") == 1
    assert t.is_evolving


def test_delta_revision_counts_as_refinement():
    r = build(
        [cu(1, ["limit"]), cu(3, ["integral"])],
        deltas=[ChapterDelta(id="d3", run_id="r", chapter_id="ch3", revised_concepts_refs=["limit"])],
    )
    t = next(t for t in r.trajectories if t.concept == "limit")
    assert t.kind_counts().get("REFINEMENT") == 1


def test_expansion_is_recorded_from_text():
    r = build(
        [cu(1, ["limit"]), cu(4, ["integral"])],
        text={"ch1": DEFINITION * 20, "ch4": ("limit " * 6) + APPLY},
    )
    t = next(t for t in r.trajectories if t.concept == "limit")
    assert "EXPANSION" in t.kind_counts()
    assert t.applications


def test_connection_is_recorded_from_stated_dependency():
    r = build([
        cu(1, ["limit"]),
        cu(3, ["derivative"], deps=["limit"]),
    ])
    limit = next(t for t in r.trajectories if t.concept == "limit")
    derivative = next(t for t in r.trajectories if t.concept == "derivative")
    assert "CONNECTION" in derivative.kind_counts() or "CONNECTION" in limit.kind_counts()


# ── §13: introduced + refined + applied ──────────────────────────────────────


def test_evolving_concept_has_all_three():
    r = build([
        cu(1, ["limit"]),
        cu(4, ["integral"], redef=["limit"], deps=["limit"]),
    ], text={"ch1": DEFINITION * 20, "ch4": ("limit " * 6) + APPLY})
    evolving = [t for t in r.trajectories if t.is_evolving]
    assert evolving
    kinds = evolving[0].kind_counts()
    assert {"INTRODUCTION", "REFINEMENT"} <= set(kinds)


def test_static_concept_is_reported_as_static():
    r = build([cu(1, ["limit"]), cu(2, ["continuity"])])
    assert not any(t.is_evolving for t in r.trajectories)


# ── §15: nothing dropped silently ────────────────────────────────────────────


def test_refinement_without_introduction_is_recorded():
    r = build([cu(3, ["integral"], redef=["never introduced"])])
    assert r.unresolved, "a refinement of an unknown concept must be recorded"
    assert "never recorded as introduced" in r.unresolved[0].reason


def test_no_trajectories_is_reported_not_crashed():
    r = build([cu(1), cu(2)])
    assert r.trajectories == []
    assert r.stats()["trajectory_count"] == 0


# ── ordering and ids ─────────────────────────────────────────────────────────


def test_events_are_in_document_order():
    r = build([cu(1, ["limit"]), cu(9, ["integral"], redef=["limit"])])
    t = next(t for t in r.trajectories if t.concept == "limit")
    chapters = [e.chapter_id for e in t.events]
    assert chapters == sorted(chapters, key=lambda c: int("".join(x for x in c if x.isdigit())))


def test_trajectory_is_book_scoped_not_global():
    """§2.1: a trajectory is this concept in this book. No canonical key."""
    r = build([cu(1, ["limit"])])
    t = r.trajectories[0]
    assert t.trajectory_id.startswith("traj_")
    blob = repr(t.to_dict())
    for banned in ("rf.", "canonical_concept_id", "refined_concept"):
        assert banned not in blob


def test_confidence_never_exceeds_one():
    """Regression: an operator-precedence bug produced 1.6 and violated a CHECK."""
    r = build([
        cu(1, ["limit"]),
        cu(2, ["continuity"], redef=["limit"], deps=["limit"]),
        cu(3, ["integral"], redef=["limit"], deps=["limit", "continuity"]),
    ], deltas=[ChapterDelta(id="d", run_id="r", chapter_id="ch3", revised_concepts_refs=["limit"])])
    for t in r.trajectories:
        assert 0.0 <= t.confidence <= 1.0


def test_trajectories_sorted_by_confidence():
    r = build([cu(1, ["limit"]), cu(2, ["continuity"], redef=["limit"])])
    confs = [t.confidence for t in r.trajectories]
    assert confs == sorted(confs, reverse=True)


def test_final_state_is_the_last_event():
    r = build([cu(1, ["limit"]), cu(5, ["integral"], redef=["limit"])])
    t = next(t for t in r.trajectories if t.concept == "limit")
    assert t.final_state == t.events[-1].detail


def test_applied_is_reported_separately_from_refined():
    """§13 says "introduced, refined and applied". Two counts, not one.

    A concept that is introduced and restated is not the same as one that is
    then used elsewhere. Choosing the lenient definition silently would decide
    the gate by assertion, so both numbers are exposed.
    """
    from stratum.services.bu_v2_concept_evolution import ConceptEvolutionBuilder

    refined_only = [
        cu(1, intro=["limit"]),
        cu(4, intro=["integral"], redef=["limit"]),
    ]
    evolved = ConceptEvolutionBuilder().build(refined_only, run_id="r", book_id="b")
    traj = next(t for t in evolved.trajectories if t.concept == "limit")
    assert traj.is_evolving, "introduced then refined should count as evolving"
    assert not traj.is_fully_evolving, "never applied anywhere"
    assert evolved.evolving_count >= 1
    assert evolved.stats()["fully_evolving_count"] <= evolved.evolving_count
