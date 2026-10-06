"""Dependency builder tests — spec §6.

The builder does not ask a model what depends on what. It reads the author's own
cross-references, which is why P11's single edge becomes a real graph. These tests
pin that behaviour on synthetic text where the expected answer is known exactly.
"""

from __future__ import annotations

from stratum.knowledge.bu_v2_models import ChapterUnderstanding
from stratum.services.bu_v2_dependency_builder import DependencyBuilder

FILLER = "The chapter develops the idea with worked examples. " * 200


def chapters(n: int = 4, concepts: dict[str, list[str]] | None = None) -> list[ChapterUnderstanding]:
    concepts = concepts or {}
    out = []
    for i in range(1, n + 1):
        out.append(
            ChapterUnderstanding(
                id=f"cu{i}", run_id="r", chapter_id=f"ch{i}",
                chapter_thesis=f"thesis {i}",
                concepts_introduced_refs=list(concepts.get(f"ch{i}", [])),
            )
        )
    return out


def build(chs, text, **kw):
    return DependencyBuilder().build(chs, run_id="r", book_id="b", chapter_text=text, **kw)


# ── explicit references ──────────────────────────────────────────────────────


def test_explicit_forward_reference_becomes_a_direct_edge():
    text = {
        "ch1": "We defer the general case until Chapter 3. " + FILLER,
        "ch2": "Nothing to see. " + FILLER,
        "ch3": "Here is the general case. " + FILLER,
    }
    r = build(chapters(3), text)
    assert any(e.relation_type == "DEPENDS_ON" and e.evidence_type == "DIRECT" for e in r.explicit_edges)
    assert r.cross_chapter_count >= 1


def test_reference_carries_a_quotable_reason():
    text = {"ch1": "we postpone its proof until Chapter 2. " + FILLER, "ch2": FILLER}
    r = build(chapters(2), text)
    edge = next(e for e in r.explicit_edges if e.relation_type == "DEPENDS_ON")
    assert "Chapter 2" in edge.reason
    assert "postpone" in edge.reason
    assert edge.evidence_refs, "an edge must point at a location"


def test_reference_to_itself_is_ignored():
    text = {"ch1": "as in Chapter 1, we begin. " + FILLER}
    r = build(chapters(1), text)
    assert r.cross_chapter_count == 0


def test_reference_to_a_nonexistent_chapter_asserts_nothing():
    """A reference to chapter 99, in a two-chapter book.

    No edge may reference it. The one cross-chapter edge that exists is the
    sequence fallback, which is counted separately and carries confidence 0.21.
    """
    text = {"ch1": "we return to this in Chapter 99. " + FILLER, "ch2": FILLER}
    r = build(chapters(2), text)
    assert all(e.source_node_id != e.target_node_id for e in r.graph.edges)
    assert not any("99" in e.reason for e in r.graph.edges)
    # Only the ordering fallback fired.
    assert all(e.status == "uncertain" for e in r.graph.edges)


def test_bare_reference_without_a_verb_becomes_unresolved():
    """§15: the reference exists but the clause says why not."""
    text = {"ch1": "See also the discussion in Chapter 2. " + FILLER, "ch2": FILLER}
    r = build(chapters(2), text)
    assert not any(e.evidence_type == "DIRECT" for e in r.explicit_edges)
    assert r.unresolved, "the reference must be recorded rather than asserted"
    # The record names the pair in chapter-id form, and states what was not done.
    assert "ch1" in r.unresolved[0].subject and "ch2" in r.unresolved[0].subject
    assert "no relation asserted" in r.unresolved[0].fallback


def test_backward_reference_is_found_too():
    text = {
        "ch1": "Chapter 3 already used this idea. " + FILLER,
        "ch2": FILLER,
        "ch3": "The idea. " + FILLER,
    }
    r = build(chapters(3), text)
    assert r.cross_chapter_count >= 1


# ── concept recurrence ───────────────────────────────────────────────────────


def test_recurring_concept_creates_a_derived_edge():
    chs = chapters(3, concepts={"ch1": ["limit"], "ch3": ["derivative"]})
    text = {
        "ch1": "limit " + FILLER,
        "ch2": FILLER,
        "ch3": ("limit " * 5) + FILLER,
    }
    r = build(chs, text)
    derived = [e for e in r.derived_edges if e.evidence_type == "DERIVED"]
    assert derived, "a concept used five times should link back to its origin"
    assert "introduced in chapter 1" in derived[0].reason


def test_single_mention_does_not_create_an_edge():
    chs = chapters(3, concepts={"ch1": ["limit"], "ch3": ["derivative"]})
    text = {"ch1": "limit " + FILLER, "ch2": FILLER, "ch3": "one mention of limit. " + FILLER}
    r = build(chs, text)
    assert not [e for e in r.derived_edges if "limit" in e.reason]


def test_repetition_is_capped_per_target():
    """A concept mentioned 300 times is one relation, not 300 (§13 integrity)."""
    chs = chapters(3, concepts={"ch1": ["limit"], "ch3": ["derivative"]})
    text = {"ch1": "limit " + FILLER, "ch2": FILLER, "ch3": ("limit " * 300) + FILLER}
    r = build(chs, text)
    assert len(r.derived_edges) <= 4


# ── sequence fallback ────────────────────────────────────────────────────────


def test_sequence_fallback_is_marked_uncertain_and_weak():
    r = build(chapters(3), {c: FILLER for c in ("ch1", "ch2", "ch3")})
    assert r.sequence_edges
    for e in r.sequence_edges:
        assert e.status == "uncertain"
        assert e.confidence <= 0.25
        assert "no explicit reference" in e.reason


def test_sequence_fallback_can_be_disabled():
    r = build(chapters(3), {c: FILLER for c in ("ch1", "ch2", "ch3")}, allow_sequence_fallback=False)
    assert r.cross_chapter_count == 0


def test_no_text_means_only_the_weakest_signal():
    r = DependencyBuilder().build(chapters(3), run_id="r", book_id="b")
    assert r.explicit_edges == []
    assert all(e.status == "uncertain" for e in r.sequence_edges)


# ── book-level requirements ──────────────────────────────────────────────────


def test_no_chapters_yields_no_graph():
    r = DependencyBuilder().build([], run_id="r", book_id="b", chapter_text={})
    assert r.cross_chapter_count == 0
    assert r.stats()["chapter_count"] == 0


def test_dependency_edges_are_all_cross_chapter():
    r = build(chapters(4), {c: FILLER for c in ("ch1", "ch2", "ch3", "ch4")})
    for d in r.dependencies:
        assert d.source_chapter != d.target_chapter


def test_dependency_count_meets_the_p12_threshold_on_a_realistic_book():
    """§13 asks for dependency >= chapter_count / 2."""
    chs = chapters(8)
    text = {f"ch{i}": FILLER for i in range(1, 9)}
    for i in range(1, 8):
        text[f"ch{i}"] = f"we depend on the result of Chapter {i + 1} here. " + FILLER
    r = build(chs, text)
    assert r.cross_chapter_count >= len(chs) // 2
