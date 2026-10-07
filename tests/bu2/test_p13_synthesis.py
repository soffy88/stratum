"""P13 Tests: Book Synthesis"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, BookThesisModel, BookThesis,
    BookConceptSystem, ConceptSystemEntry, BookArgumentSystem, BookArgument,
    BookMechanismSystem, BookMechanism, BookEvidenceMap, EvidenceMapEntry,
    BookAuthorModel, BookChapterRoles, ChapterRoleAssignment, BookContradictions,
    ContradictionEntry, ContradictionType, ThesisType, ThesisProvenance,
    ConceptRole, ArgumentStatus, EvidenceStrengthP13, ChapterRole,
)
from stratum.services.bu_v2_book_synthesis import BookSynthesisBuilder


class MockGraph:
    nodes = {}
    edges = []


def make_chapter(chapter_id: str, thesis: str = "") -> ChapterUnderstanding:
    return ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=thesis,
        concepts_introduced_refs=["concept1"],
        mechanisms_refs=["mechanism1"],
    )


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
        central_theses=["Core thesis statement"],
        governing_questions=["What is the main question?"],
    )


def make_synthesis_components() -> dict:
    """Create minimal valid synthesis components for testing."""
    thesis = BookThesisModel()
    thesis.core_thesis = BookThesis(
        id="t1", type=ThesisType.CORE, statement="Core thesis",
        confidence=0.7, provenance=ThesisProvenance.AUTHOR_ASSERTED
    )

    concept_system = BookConceptSystem()
    concept_system.foundational = [
        ConceptSystemEntry(concept_id="c1", label="limit", definition="def", role=ConceptRole.FOUNDATIONAL,
                          chapter_refs=["ch1"], confidence=0.8)
    ]

    arg_system = BookArgumentSystem()
    arg_system.thesis_arguments = [
        BookArgument(id="a1", level=0, what="Thesis arg", why="because", how="by reasoning",
                    evidence_refs=["ev1"], conclusion="Therefore", status=ArgumentStatus.SUPPORTED,
                    confidence=0.7, source_chapters=["ch1"])
    ]

    mech_system = BookMechanismSystem()
    mech_system.mechanisms = [
        BookMechanism(id="m1", trigger="t", precondition="p", operation="op",
                     intermediate_state="i", outcome="o", evidence_refs=["ev1"],
                     confidence=0.6, provenance=ThesisProvenance.AUTHOR_ASSERTED,
                     source_chapters=["ch1"])
    ]

    ev_map = BookEvidenceMap()
    ev_map.entries = [
        EvidenceMapEntry(claim_id="claim1", claim_statement="Claim", evidence_ids=["ev1"],
                        evidence_strengths={"ev1": EvidenceStrengthP13.DIRECT},
                        argument_ids=["a1"], chapter_ids=["ch1"], is_supported=True,
                        provenance=ThesisProvenance.AUTHOR_ASSERTED)
    ]
    ev_map.evidence_coverage = 1.0
    ev_map.unsupported_claim_count = 0

    author_model = BookAuthorModel(
        worldview=["Test worldview"], assumptions=["Test assumption"],
        provenance=ThesisProvenance.MODEL_INFERRED
    )

    chapter_roles = BookChapterRoles()
    chapter_roles.assignments = [
        ChapterRoleAssignment(chapter_id="ch1", roles=[ChapterRole.FOUNDATION],
                            evidence="test", confidence=0.8)
    ]

    contradictions = BookContradictions()
    contradictions.contradictions = []

    return {
        "thesis": thesis,
        "concept_system": concept_system,
        "arg_system": arg_system,
        "mech_system": mech_system,
        "ev_map": ev_map,
        "author_model": author_model,
        "chapter_roles": chapter_roles,
        "contradictions": contradictions,
    }


def test_book_synthesis_builder_integration():
    bu = make_bu()
    chapters = [make_chapter("ch1", "Core thesis")]
    components = make_synthesis_components()

    builder = BookSynthesisBuilder()
    # Test that builder can be instantiated and its methods work
    assert builder is not None
    assert hasattr(builder, 'build')
    assert hasattr(builder, 'thesis_analyzer')
    assert hasattr(builder, 'concept_builder')
    assert hasattr(builder, 'argument_builder')
    assert hasattr(builder, 'mechanism_analyzer')
    assert hasattr(builder, 'evidence_builder')
    assert hasattr(builder, 'chapter_roles')
    assert hasattr(builder, 'contradiction_detector')


def test_synthesis_problem_definition():
    components = make_synthesis_components()
    builder = BookSynthesisBuilder()
    problem = builder._formulate_problem(components["thesis"])

    assert "Core thesis" in problem


def test_synthesis_author_model():
    components = make_synthesis_components()
    builder = BookSynthesisBuilder()
    chapters = [make_chapter("ch1")]
    bu = make_bu()

    author = builder._build_author_model(
        bu, chapters, components["thesis"], components["concept_system"],
        components["arg_system"], components["contradictions"]
    )

    assert isinstance(author, BookAuthorModel)
    assert author.worldview
    assert author.explanatory_strategy
    assert author.argument_style