"""P13 Tests: Mechanism Analysis"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, ThesisProvenance,
)
from stratum.services.bu_v2_mechanism_analyzer import MechanismAnalyzer


class MockGraph:
    nodes = {}
    edges = []

    def __init__(self):
        class MockNode:
            def __init__(self):
                self.node_id = 'n1'
                self.node_type = 'MECHANISM'
                self.label = 'Limit process'
                self.chapter_id = 'ch1'
                self.confidence = 0.7
                self.metadata = {
                    'trigger': 'epsilon-delta',
                    'precondition': 'function defined',
                    'intermediate': 'approaching',
                    'outcome': 'limit value',
                    'evidence_refs': ['ev1']
                }
        self.nodes = {'n1': MockNode()}


def make_chapter(chapter_id: str, mechanisms: list = None) -> ChapterUnderstanding:
    return ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=f"Thesis for {chapter_id}",
        mechanisms_refs=mechanisms or [],
    )


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
    )


def test_mechanism_analyzer_from_chapter():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", mechanisms=["The epsilon-delta process defines limits by constraining function values"]),
        make_chapter("ch2", mechanisms=["Derivative is computed as limit of difference quotient"]),
    ]
    analyzer = MechanismAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    assert len(result.system.mechanisms) >= 2
    for m in result.system.mechanisms:
        assert m.operation
        assert m.source_chapters


def test_mechanism_analyzer_from_graph():
    bu = make_bu()
    chapters = [make_chapter("ch1")]
    graph = MockGraph()

    analyzer = MechanismAnalyzer()
    result = analyzer.analyze(bu, chapters, graph)

    # Should include graph mechanisms
    assert len(result.system.mechanisms) >= 1


def test_mechanism_provenance_author_asserted():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", mechanisms=["The limit process computes values by epsilon-delta"]),
    ]
    analyzer = MechanismAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    # Mechanisms with evidence should be AUTHOR_ASSERTED
    for m in result.system.mechanisms:
        if m.evidence_refs:
            assert m.provenance == ThesisProvenance.AUTHOR_ASSERTED


def test_mechanism_structure():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", mechanisms=["The epsilon-delta process defines limits by constraining function values"]),
    ]
    analyzer = MechanismAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    for m in result.system.mechanisms:
        assert m.id
        assert m.trigger
        assert m.operation
        # outcome may be empty if not detected by heuristics
        assert isinstance(m.confidence, float)
        assert 0 <= m.confidence <= 1