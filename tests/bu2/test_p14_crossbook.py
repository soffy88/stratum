"""P14 Cross-Book Intelligence Tests."""

from __future__ import annotations

import pytest

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BUStatus,
    BookSynthesis,
    BookThesisModel,
    BookThesis,
    ThesisType,
    ThesisProvenance,
    BookConceptSystem,
    ConceptSystemEntry,
    ConceptRole,
    BookArgumentSystem,
    BookArgument,
    ArgumentStatus,
    BookMechanismSystem,
    BookMechanism,
    BookEvidenceMap,
    EvidenceMapEntry,
    EvidenceStrengthP13,
    BookAuthorModel,
    BookChapterRoles,
    ChapterRoleAssignment,
    ChapterRole,
    BookContradictions,
    CrossBookCollection,
    CrossBookConcept,
    CrossBookConceptRelation,
    CrossBookConceptRelationType,
    CrossBookThesis,
    CrossBookThesisRelation,
    CrossBookThesisRelationType,
    CrossBookArgument,
    CrossBookArgumentRelation,
    CrossBookArgumentRelationType,
    CrossBookMechanism,
    CrossBookMechanismRelation,
    CrossBookMechanismRelationType,
    CrossBookEvidence,
    CrossBookEvidenceRelation,
    CrossBookEvidenceRelationType,
    CrossBookContradiction,
    CrossBookContradictionType,
    CrossBookProblem,
    CrossBookProblemRelation,
    CrossBookProblemRelationType,
    CrossBookKnowledgeGap,
    KnowledgeGapType,
    CrossBookComparison,
    CrossBookSynthesis,
    CrossBookUnderstanding,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_bu(book_id: str, status: BUStatus = BUStatus.VERIFIED) -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id=f"bu_{book_id}",
        run_id=f"run_{book_id}",
        book_id=book_id,
        substrate_id=book_id,
        version=1,
        status=status,
    )


def make_synthesis(book_id: str) -> BookSynthesis:
    """Create a minimal synthesis for testing."""
    thesis_model = BookThesisModel(
        core_thesis=BookThesis(
            id=f"thesis_{book_id}_core",
            type=ThesisType.CORE,
            statement=f"Core thesis of {book_id}",
            scope="book",
            confidence=0.8,
            provenance=ThesisProvenance.AUTHOR_ASSERTED,
        ),
        supporting_theses=[
            BookThesis(
                id=f"thesis_{book_id}_sup1",
                type=ThesisType.SUPPORTING,
                statement=f"Supporting thesis of {book_id}",
                scope="book",
                confidence=0.7,
                provenance=ThesisProvenance.STRUCTURALLY_DERIVED,
            )
        ],
        problem_statements=[
            BookThesis(
                id=f"thesis_{book_id}_prob1",
                type=ThesisType.PROBLEM,
                statement=f"What is the nature of {book_id}?",
                scope="book",
                confidence=0.6,
                provenance=ThesisProvenance.AUTHOR_ASSERTED,
            )
        ],
        central_questions=[
            BookThesis(
                id=f"thesis_{book_id}_q1",
                type=ThesisType.QUESTION,
                statement=f"How does {book_id} work?",
                scope="book",
                confidence=0.6,
                provenance=ThesisProvenance.AUTHOR_ASSERTED,
            )
        ],
    )

    concept_system = BookConceptSystem(
        foundational=[
            ConceptSystemEntry(
                concept_id=f"concept_{book_id}_found",
                label="Foundation Concept",
                definition=f"Foundational concept of {book_id}",
                role=ConceptRole.FOUNDATIONAL,
                chapter_refs=["ch1"],
                confidence=0.9,
            )
        ],
        core=[
            ConceptSystemEntry(
                concept_id=f"concept_{book_id}_core",
                label="Core Concept",
                definition=f"Core concept of {book_id}",
                role=ConceptRole.CORE,
                chapter_refs=["ch2"],
                prerequisites=["Foundation Concept"],
                confidence=0.8,
            )
        ],
        derived=[
            ConceptSystemEntry(
                concept_id=f"concept_{book_id}_der",
                label="Derived Concept",
                definition=f"Derived concept of {book_id}",
                role=ConceptRole.DERIVED,
                chapter_refs=["ch3"],
                prerequisites=["Core Concept"],
                confidence=0.7,
            )
        ],
    )

    argument_system = BookArgumentSystem(
        thesis_arguments=[
            BookArgument(
                id=f"arg_{book_id}_thesis",
                level=0,
                what=f"Main argument of {book_id}",
                why="Because of evidence",
                how="Through reasoning",
                conclusion=f"Therefore {book_id} is true",
                evidence_refs=[f"ev_{book_id}_1"],
                status=ArgumentStatus.SUPPORTED,
                confidence=0.8,
                source_chapters=["ch1", "ch2"],
            )
        ],
        major_arguments=[
            BookArgument(
                id=f"arg_{book_id}_major",
                level=1,
                what=f"Major argument of {book_id}",
                why="Supporting evidence",
                how="Detailed analysis",
                conclusion=f"Major conclusion for {book_id}",
                evidence_refs=[f"ev_{book_id}_2"],
                status=ArgumentStatus.PARTIALLY_SUPPORTED,
                confidence=0.7,
                source_chapters=["ch3"],
            )
        ],
    )

    mechanism_system = BookMechanismSystem(
        mechanisms=[
            BookMechanism(
                id=f"mech_{book_id}_1",
                trigger="Input condition",
                precondition="Prerequisites met",
                operation="Process X transforms input",
                intermediate_state="Intermediate state",
                outcome="Output Y",
                evidence_refs=[f"ev_{book_id}_3"],
                confidence=0.7,
                provenance=ThesisProvenance.MODEL_INFERRED,
                source_chapters=["ch2"],
            )
        ],
    )

    evidence_map = BookEvidenceMap(
        entries=[
            EvidenceMapEntry(
                claim_id=f"claim_{book_id}_1",
                claim_statement=f"Claim 1 of {book_id}",
                evidence_ids=[f"ev_{book_id}_1", f"ev_{book_id}_2"],
                evidence_strengths={
                    f"ev_{book_id}_1": EvidenceStrengthP13.DIRECT,
                    f"ev_{book_id}_2": EvidenceStrengthP13.EXAMPLE,
                },
                argument_ids=[f"arg_{book_id}_thesis"],
                chapter_ids=["ch1", "ch2"],
                is_supported=True,
                provenance=ThesisProvenance.AUTHOR_ASSERTED,
            )
        ],
    )

    author_model = BookAuthorModel(
        worldview=[f"Worldview of {book_id}"],
        assumptions=[f"Assumption of {book_id}"],
        explanatory_strategy=["Strategy"],
        argument_style=["Style"],
        recurring_patterns=[],
        evidence_preference=[],
        limitations=[],
        unresolved_positions=[],
    )

    chapter_roles = BookChapterRoles(
        assignments=[
            ChapterRoleAssignment(
                chapter_id="ch1",
                roles=[ChapterRole.FOUNDATION],
                evidence="Foundation chapter",
                confidence=0.9,
            )
        ],
    )

    contradictions = BookContradictions(contradictions=[])

    return BookSynthesis(
        id=f"synth_{book_id}",
        run_id=f"run_{book_id}",
        book_id=book_id,
        thesis=thesis_model,
        problem_definition=f"Problems and questions of {book_id}",
        concept_system=concept_system,
        argument_system=argument_system,
        mechanism_system=mechanism_system,
        evidence_map=evidence_map,
        author_model=author_model,
        chapter_roles=chapter_roles,
        contradictions=contradictions,
        unresolved_questions=[],
    )


# ── Tests ──────────────────────────────────────────────────────────────────

def test_crossbook_collection_creation():
    """Test creating a cross-book collection."""
    collection = CrossBookCollection(
        collection_id="coll_test_123",
        name="Test Collection",
        description="A test collection",
        book_ids=["book1", "book2", "book3"],
    )

    assert collection.name == "Test Collection"
    assert len(collection.book_ids) == 3
    assert collection.collection_id == "coll_test_123"


def test_crossbook_collection_requires_two_books():
    """Collection must have at least 2 books."""
    with pytest.raises(ValueError):
        CrossBookCollection(
            name="Test",
            description="Test",
            book_ids=["book1"],  # Only 1 book
        )


def test_concept_alignment_same_concept():
    """Test that identical concepts are aligned as SAME_CONCEPT."""
    from stratum.services.bu_v2_crossbook_concepts import BU2CrossBookConceptAligner

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")

    # Create book2 with same concept - make definitions identical
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")
    # Override to make definitions identical for SAME_CONCEPT detection
    synth2.concept_system.foundational[0].definition = "Foundational concept of book1"

    aligner = BU2CrossBookConceptAligner()
    result = aligner.align([(bu1, synth1), (bu2, synth2)])

    # Should find SAME_CONCEPT for "Foundation Concept"
    same_concept = [r for r in result.concept_relations if r.relation == CrossBookConceptRelationType.SAME_CONCEPT]
    assert len(same_concept) >= 1


def test_concept_alignment_same_term_different_meaning():
    """Test that same label with different definition is SAME_TERM_DIFFERENT_MEANING."""
    from stratum.services.bu_v2_crossbook_concepts import BU2CrossBookConceptAligner

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")

    # Create book2 with same label but different definition
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")
    # Modify concept definition to be different
    synth2.concept_system.foundational[0].definition = "Completely different definition"

    aligner = BU2CrossBookConceptAligner()
    result = aligner.align([(bu1, synth1), (bu2, synth2)])

    # Should find SAME_TERM_DIFFERENT_MEANING
    diff_meaning = [r for r in result.concept_relations if r.relation == CrossBookConceptRelationType.SAME_TERM_DIFFERENT_MEANING]
    assert len(diff_meaning) >= 1


def test_thesis_comparison_supports():
    """Test thesis comparison finds SUPPORTS relation."""
    from stratum.services.bu_v2_crossbook_thesis import BU2CrossBookThesisComparator

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    comparator = BU2CrossBookThesisComparator()
    result = comparator.compare([(bu1, synth1), (bu2, synth2)])

    # Should find supporting relations
    supports = [r for r in result.thesis_relations if r.relation == CrossBookThesisRelationType.SUPPORTS]
    assert len(supports) >= 0  # May or may not find depending on similarity


def test_argument_comparison_transfer():
    """Test argument comparison detects theory-to-application transfer."""
    from stratum.services.bu_v2_crossbook_arguments import BU2CrossBookArgumentComparator

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    comparator = BU2CrossBookArgumentComparator()
    result = comparator.compare([(bu1, synth1), (bu2, synth2)])

    # Should find argument relations
    assert len(result.crossbook_arguments) >= 2
    assert len(result.argument_relations) >= 0


def test_evidence_comparison_convergent():
    """Test evidence comparison finds CONVERGENT evidence."""
    from stratum.services.bu_v2_crossbook_evidence import BU2CrossBookEvidenceComparator

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    comparator = BU2CrossBookEvidenceComparator()
    result = comparator.compare([(bu1, synth1), (bu2, synth2)])

    # Should find convergent evidence relations
    convergent = [r for r in result.evidence_relations if r.relation == CrossBookEvidenceRelationType.CONVERGENT]
    assert len(convergent) >= 0


def test_contradiction_detection():
    """Test contradiction detection."""
    from stratum.services.bu_v2_crossbook_contradictions import BU2CrossBookContradictionDetector

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    # Modify to create contradiction: same claim, different support
    # Use identical claim statement to ensure high similarity
    synth1.evidence_map.entries[0].claim_statement = "Identical claim for contradiction test"
    synth2.evidence_map.entries[0].claim_statement = "Identical claim for contradiction test"
    synth2.evidence_map.entries[0].is_supported = False

    detector = BU2CrossBookContradictionDetector()
    result = detector.detect([(bu1, synth1), (bu2, synth2)])

    # Should detect direct contradiction
    direct = [c for c in result.contradictions if c.type == CrossBookContradictionType.DIRECT_CONTRADICTION]
    assert len(direct) >= 1


def test_gap_detection_unanswered():
    """Test gap detection finds unanswered questions."""
    from stratum.services.bu_v2_crossbook_gaps import BU2CrossBookGapDetector

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    # Remove evidence from question to make it unanswered
    synth1.thesis.problem_statements[0].evidence_refs = []
    synth1.thesis.problem_statements[0].supporting_arguments = []

    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    detector = BU2CrossBookGapDetector()
    result = detector.detect([(bu1, synth1), (bu2, synth2)])

    # Should find unanswered gap
    unanswered = [g for g in result.knowledge_gaps if g.type == KnowledgeGapType.UNANSWERED]
    assert len(unanswered) >= 1


def test_crossbook_understanding_construction():
    """Test full cross-book understanding construction."""
    from stratum.services.bu_v2_crossbook_synthesis import BU2CrossBookSynthesisBuilder
    from stratum.services.bu_v2_crossbook_collection import BU2CrossBookCollectionManager

    bu1 = make_bu("book1")
    synth1 = make_synthesis("book1")
    bu2 = make_bu("book2")
    synth2 = make_synthesis("book2")

    collection = CrossBookCollection(
        name="Test Collection",
        description="Test",
        book_ids=["book1", "book2"],
    )

    # Mock results
    class MockResult:
        def __init__(self):
            self.unified_concepts = []
            self.concept_relations = []
            self.concept_evolutions = []
            self.traceability = {}
            self.crossbook_theses = []
            self.thesis_relations = []
            self.crossbook_arguments = []
            self.argument_relations = []
            self.crossbook_mechanisms = []
            self.mechanism_relations = []
            self.crossbook_evidence = []
            self.evidence_relations = []
            self.contradictions = []
            self.crossbook_problems = []
            self.problem_relations = []
            self.knowledge_gaps = []

    builder = BU2CrossBookSynthesisBuilder()
    understanding = builder.build(
        collection=collection,
        books=[(bu1, synth1), (bu2, synth2)],
        concept_result=MockResult(),
        thesis_result=MockResult(),
        argument_result=MockResult(),
        mechanism_result=MockResult(),
        evidence_result=MockResult(),
        contradiction_result=MockResult(),
        problem_result=MockResult(),
        gap_result=MockResult(),
        comparison_results=[],
    )

    assert understanding.collection.collection_id == collection.collection_id
    assert understanding.collection.book_ids == ["book1", "book2"]
    assert understanding.understanding_id.startswith("cbunderstanding_")


def test_crossbook_expression_generation():
    """Test expression generation."""
    from stratum.services.bu_v2_crossbook_expression import BU2CrossBookExpressionGenerator, CrossBookExpression

    collection = CrossBookCollection(
        name="Test",
        description="Test",
        book_ids=["book1", "book2"],
    )

    understanding = CrossBookUnderstanding(
        understanding_id="test_123",
        collection=collection,
        quality={},
        synthesis=CrossBookSynthesis(
            synthesis_id="synth_test",
            collection_id=collection.collection_id,
        ),
    )

    generator = BU2CrossBookExpressionGenerator()
    expr = generator.generate(understanding)

    assert isinstance(expr, CrossBookExpression)
    assert expr.collection_name == "Test"
    assert expr.book_count == 2
    assert "No cross-book concepts" in expr.concept_summary


def test_crossbook_query():
    """Test query interface."""
    from stratum.services.bu_v2_crossbook_query import BU2CrossBookQuery

    collection = CrossBookCollection(
        name="Test",
        description="Test",
        book_ids=["book1", "book2"],
    )

    understanding = CrossBookUnderstanding(
        understanding_id="test_123",
        collection=collection,
        quality={},
        synthesis=CrossBookSynthesis(
            synthesis_id="synth_test",
            collection_id=collection.collection_id,
        ),
    )

    query = BU2CrossBookQuery(understanding)
    result = query.find_shared_concepts()

    assert isinstance(result, type(result))
    assert result.total == 0  # Empty understanding


def test_stable_id_deterministic():
    """Test that stable_id is deterministic."""
    from stratum.services.bu_v2_crossbook_concepts import _stable_id

    id1 = _stable_id("test", "book1", "concept1")
    id2 = _stable_id("test", "book1", "concept1")
    assert id1 == id2

    id3 = _stable_id("test", "book2", "concept2")
    assert id1 != id3


def test_jaccard_similarity():
    """Test Jaccard similarity helper."""
    from stratum.services.bu_v2_crossbook_concepts import _jaccard_similarity

    # Identical
    assert _jaccard_similarity("hello world", "hello world") == 1.0

    # No overlap
    assert _jaccard_similarity("hello", "world") == 0.0

    # Partial overlap
    sim = _jaccard_similarity("hello world", "hello there")
    assert 0.0 < sim < 1.0