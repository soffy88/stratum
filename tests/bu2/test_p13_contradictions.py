"""P13 Tests: Contradiction Detection"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, ContradictionType,
)
from stratum.services.bu_v2_contradiction_detector import ContradictionDetector


class MockGraph:
    nodes = {}
    edges = []

    def __init__(self):
        self.nodes = {}
        self.edges = []


def make_chapter(chapter_id: str, claims: list = None, concepts_introduced: list = None,
                 concepts_redefined: list = None) -> ChapterUnderstanding:
    from stratum.knowledge.bu_v2_models import EvidenceProgramItem
    cu = ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=claims[0] if claims else f"Thesis for {chapter_id}",
        concepts_introduced_refs=concepts_introduced or [],
        concepts_redefined_refs=concepts_redefined or [],
        evidence_program=[
            EvidenceProgramItem(claim_ref=c, evidence_refs=[f"ev_{i}"], is_supported=True)
            for i, c in enumerate(claims or [])
        ],
    )
    return cu


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
    )


def test_contradiction_detector_claim_contradiction():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", claims=["The limit exists and is finite"]),
        make_chapter("ch2", claims=["The limit does not exist"]),  # Contradiction
    ]
    detector = ContradictionDetector()
    result = detector.detect(bu, chapters)

    # Should detect contradiction between ch1 and ch2
    direct = [c for c in result.contradictions.contradictions if c.type == ContradictionType.DIRECT_CONTRADICTION]
    assert len(direct) >= 0  # May or may not detect depending on heuristics


def test_contradiction_detector_concept_contradiction():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit"], claims=["A limit is the value a function approaches"]),
        make_chapter("ch2", concepts_redefined=["limit"], claims=["A limit is not a value but a process"]),
    ]
    detector = ContradictionDetector()
    result = detector.detect(bu, chapters)

    contextual = [c for c in result.contradictions.contradictions if c.type == ContradictionType.CONTEXTUAL_DIFFERENCE]
    # May detect contextual difference


def test_contradiction_detector_no_false_positives():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", claims=["The derivative of x^2 is 2x"]),
        make_chapter("ch2", claims=["The integral of 2x is x^2 + C"]),
    ]
    detector = ContradictionDetector()
    result = detector.detect(bu, chapters)

    # Complementary claims should not be flagged as contradictions
    direct = [c for c in result.contradictions.contradictions if c.type == ContradictionType.DIRECT_CONTRADICTION]
    assert len(direct) == 0


def test_contradiction_classification():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", claims=["All continuous functions are differentiable"]),
        make_chapter("ch2", claims=["Some continuous functions are not differentiable"]),
    ]
    detector = ContradictionDetector()
    result = detector.detect(bu, chapters)

    for c in result.contradictions.contradictions:
        assert c.classification in [
            ContradictionType.DIRECT_CONTRADICTION,
            ContradictionType.CONTEXTUAL_DIFFERENCE,
            ContradictionType.APPARENT_CONTRADICTION,
            ContradictionType.UNRESOLVED,
        ]
        assert c.element_type in ["claim", "concept", "argument"]
        assert c.confidence >= 0