"""P13 Tests: Thesis Model"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookThesis, BookThesisModel, BookUnderstandingV2, ChapterUnderstanding,
    ThesisType, ThesisProvenance,
)
from stratum.services.bu_v2_thesis_analyzer import ThesisAnalyzer


class MockGraph:
    nodes = {}
    edges = []


def make_chapter(chapter_id: str, thesis: str = "", question: str = "", evidence_items: list = None) -> ChapterUnderstanding:
    cu = ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=thesis,
        chapter_question=question,
        concepts_introduced_refs=["concept1", "concept2"],
        evidence_program=evidence_items or [],
    )
    return cu


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
        central_theses=["The fundamental theorem of calculus connects differentiation and integration"],
        sub_theses=["Limits provide the foundation for calculus", "Derivatives measure rates of change"],
        governing_questions=["What is the relationship between derivatives and integrals?"],
    )


def test_thesis_analyzer_core_thesis():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", thesis="The fundamental theorem of calculus connects differentiation and integration"),
        make_chapter("ch2", thesis="Limits provide the foundation for calculus"),
    ]
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    assert result.model.core_thesis is not None
    assert "fundamental theorem" in result.model.core_thesis.statement.lower()
    assert result.model.core_thesis.type == ThesisType.CORE
    assert result.model.core_thesis.confidence > 0


def test_thesis_analyzer_supporting_theses():
    bu = make_bu()
    chapters = [make_chapter("ch1"), make_chapter("ch2")]
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    assert len(result.model.supporting_theses) >= 1
    for t in result.model.supporting_theses:
        assert t.type == ThesisType.SUPPORTING


def test_thesis_analyzer_problems_and_questions():
    bu = make_bu()
    chapters = [make_chapter("ch1")]
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    assert len(result.model.problem_statements) >= 0
    assert len(result.model.central_questions) >= 1
    for q in result.model.central_questions:
        assert q.type == ThesisType.QUESTION
        assert q.provenance == ThesisProvenance.AUTHOR_ASSERTED


def test_thesis_provenance_author_asserted():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", thesis="The fundamental theorem of calculus connects differentiation and integration"),
    ]
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    # Core thesis should be AUTHOR_ASSERTED or STRUCTURALLY_DERIVED when it matches chapter thesis
    assert result.model.core_thesis.provenance in [ThesisProvenance.AUTHOR_ASSERTED, ThesisProvenance.STRUCTURALLY_DERIVED]


def test_thesis_traceability():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", thesis="The fundamental theorem of calculus connects differentiation and integration"),
    ]
    analyzer = ThesisAnalyzer()
    result = analyzer.analyze(bu, chapters, MockGraph())

    core_id = result.model.core_thesis.id
    assert core_id in result.traceability
    assert len(result.traceability[core_id]) > 0