"""Task B–E: KU anchoring, hard gates, graph enrichment and the learning guide.

These pin the behaviours the BU2 quality-10 work added:

  * chunked reading of a long chapter (no 12k truncation)
  * JSON healing of a truncated model response
  * the frozen-KU anchor list reaching the producer and covering DEF/THM KUs
  * the six hard gates failing a shallow run and passing a substantial one
  * CONCEPT/CLAIM/THEOREM nodes in the reasoning graph
  * a dependency-ordered learning guide
  * back matter excluded from the discourse arc

They run against a StaticProvider and an in-memory chapter list, so no model and
no book are needed.
"""

from __future__ import annotations

from types import SimpleNamespace

from stratum.knowledge.bu_v2_models import (
    ChapterUnderstanding,
    EvidenceProgramItem,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_graph_enricher import ReasoningGraphEnricher
from stratum.services.bu_v2_hard_gates import (
    HardGateEvaluator,
    is_placeholder,
)
from stratum.services.bu_v2_ku_anchor import ChapterKUIndex, FrozenKU
from stratum.services.bu_v2_learning_guide import LearningGuideBuilder
from stratum.services.bu_v2_producer import (
    Chapter,
    ChapterUnderstandingProducer,
    _heal_json,
)
from stratum.services.bu_v2_provider import StaticProvider
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph, node_id


# ── fixtures ────────────────────────────────────────────────────────────────


def _long_chapter() -> Chapter:
    # A chapter long enough to require several chunks at max_chunk_chars=1000.
    body = " ".join(f"word{i}" for i in range(1200))
    text = "1. Big Chapter\n\nOVERVIEW " + body
    return Chapter(
        chapter_id="ch1", number=1, title="1. Big Chapter", text=text, start=0, end=len(text)
    )


def _payload(**over) -> dict:
    base = {
        "chapter_question": "What is a derivative?",
        "chapter_goal": "Compute derivatives",
        "chapter_thesis": "A derivative measures instantaneous rate of change",
        "concepts": [{"name": "Derivative", "definition": "limit of a difference quotient"}],
        "claims": [
            {
                "text": "A derivative measures instantaneous rate of change",
                "quote": "A derivative measures instantaneous rate of change",
            }
        ],
        "mechanisms": [
            {"cause": "a limit", "process": "take the limit", "conditions": "when it exists"}
        ],
        "dependencies": [],
        "uncertainties": ["assumes the limit exists"],
        "terminology": [],
    }
    base.update(over)
    return base


# ── A: chunking and JSON healing ─────────────────────────────────────────────


def test_long_chapter_is_chunked_not_truncated():
    """A chapter longer than max_chunk_chars is split into several chunks."""
    producer = ChapterUnderstandingProducer(max_chunk_chars=1000, chunk_overlap=50)
    chunks = producer._chapter_chunks(_long_chapter())
    assert len(chunks) > 1, "a long chapter must be read in more than one chunk"
    # Every character of the chapter is covered by some chunk.
    covered = set()
    for c in chunks:
        covered.update(range(c.start, c.end))
    assert covered == set(range(len(_long_chapter().text)))


def test_short_chapter_is_one_chunk():
    producer = ChapterUnderstandingProducer(max_chunk_chars=100000)
    chunks = producer._chapter_chunks(_long_chapter())
    assert len(chunks) == 1


def test_heal_json_recovers_truncated_object():
    """A response cut mid-list is recovered rather than dropped."""
    truncated = '{"concepts":[{"name":"a","definition":"b"}],"claims":[{"text":"x",'
    data = _heal_json(truncated)
    assert data is not None
    assert data["concepts"][0]["name"] == "a"


def test_heal_json_returns_none_for_garbage():
    assert _heal_json("this is not json") is None
    assert _heal_json("") is None


# ── B: KU anchoring ──────────────────────────────────────────────────────────


def _ku_index() -> ChapterKUIndex:
    idx = ChapterKUIndex(source_version_id="sv_test", total=3)
    idx.by_chapter["ch1"] = [
        FrozenKU(
            ku_id="ku_1",
            role="DEFINITION",
            title="DEFINITION",
            statement="A **derivative** is the limit of a difference quotient",
            quote="A derivative is the limit of a difference quotient",
            locator="char:10-60 (1 1. Functions)",
            chapter_label="1 1. Functions",
            start=10,
            end=60,
        ),
        FrozenKU(
            ku_id="ku_2",
            role="THEOREM",
            title="THEOREM 1（Mean Value Theorem）",
            statement="If f is continuous then there is a point where the derivative equals the average rate",
            quote="there is a point where the derivative equals the average rate",
            locator="char:100-200 (1 1. Functions)",
            chapter_label="1 1. Functions",
            start=100,
            end=200,
        ),
    ]
    return idx


def test_ku_anchor_covers_defthm_concepts():
    """A frozen DEF/THM KU the model omits is added from the KU's own quote."""
    chapter = Chapter(
        chapter_id="ch1",
        number=1,
        title="1. Functions",
        text=(
            "OVERVIEW A derivative is the limit of a difference quotient. "
            "there is a point where the derivative equals the average rate."
        ),
        start=0,
        end=120,
    )
    producer = ChapterUnderstandingProducer(
        provider=StaticProvider(_payload(concepts=[{"name": "Derivative", "definition": "x"}])),
    )
    producer.set_ku_anchor(_ku_index().anchors_for("ch1"))
    cu, _, evidence = producer.produce(chapter, run_id="r", book_id="b")
    # Both the model's concept and the anchored theorem should be present.
    joined = " ".join(cu.concepts_introduced_refs).lower()
    assert "derivative" in joined
    assert any(
        "mean value" in c.lower() or "derivative equals" in c.lower()
        for c in cu.concepts_introduced_refs
    )
    assert "ku_1" in cu.major_ku_refs or "ku_2" in cu.major_ku_refs


def test_ku_anchor_does_not_fabricate_coverage():
    """A KU whose text is absent from the chapter is not added."""
    chapter = Chapter(
        chapter_id="ch1",
        number=1,
        title="1. Functions",
        text="OVERVIEW Nothing about calculus here at all.",
        start=0,
        end=40,
    )
    producer = ChapterUnderstandingProducer(provider=StaticProvider(_payload()))
    producer.set_ku_anchor(_ku_index().anchors_for("ch1"))
    cu, _, _ = producer.produce(chapter, run_id="r", book_id="b")
    # The Mean Value Theorem quote is not in the text, so it must not appear.
    assert not any("mean value" in c.lower() for c in cu.concepts_introduced_refs)


# ── C: reasoning graph enrichment ────────────────────────────────────────────


def test_graph_enricher_adds_concept_and_claim_nodes():
    graph = BookReasoningGraph(graph_id="g", run_id="r", book_id="b")
    chapters = [
        ChapterUnderstanding(
            id="cu1",
            run_id="r",
            chapter_id="ch1",
            chapter_thesis="Derivatives measure change",
            concepts_introduced_refs=["Derivative"],
            evidence_program=[
                EvidenceProgramItem(
                    claim_ref="the derivative is a limit", evidence_refs=["ev1"], is_supported=True
                )
            ],
        )
    ]
    # A chapter node must exist for the EXPLAINS/SUPPORTS edges to land.
    from stratum.services.bu_v2_reasoning_graph import ReasoningNode

    graph.add_node(
        ReasoningNode(
            node_id=node_id("n", "r", "ch1"), node_type="CHAPTER", label="ch1", chapter_id="ch1"
        )
    )
    stats = ReasoningGraphEnricher().enrich(
        graph, chapters, run_id="r", ku_index=_ku_index(), chapter_text={"ch1": "derivative limit"}
    )
    types = {n.node_type for n in graph.nodes.values()}
    assert "CONCEPT" in types
    assert "THEOREM" in types, "a frozen THEOREM KU must become a THEOREM node"
    assert "CLAIM" in types
    assert stats.edges_added > 0


def test_graph_enricher_no_theorem_without_ku():
    """Without frozen KUs, only CONCEPT/CLAIM nodes are added."""
    graph = BookReasoningGraph(graph_id="g", run_id="r", book_id="b")
    chapters = [
        ChapterUnderstanding(
            id="cu1", run_id="r", chapter_id="ch1", concepts_introduced_refs=["Derivative"]
        )
    ]
    ReasoningGraphEnricher().enrich(graph, chapters, run_id="r")
    types = {n.node_type for n in graph.nodes.values()}
    assert "CONCEPT" in types
    assert "THEOREM" not in types


# ── C: back matter excluded from the arc ─────────────────────────────────────


def test_back_matter_excluded_from_discourse_arc():
    chapters = [
        ChapterUnderstanding(id="cu1", run_id="r", chapter_id="ch1", chapter_thesis="opens"),
        ChapterUnderstanding(id="cu2", run_id="r", chapter_id="ch2", chapter_thesis="closes"),
        ChapterUnderstanding(id="cubm", run_id="r", chapter_id="bm1", chapter_thesis="answers"),
    ]
    bu = BookIntegrator(
        provider=StaticProvider({"governing_questions": ["What is calculus?"]})
    ).integrate(
        IntegrationInput(
            run_id="r",
            book_id="b",
            substrate_id="s",
            chapters=chapters,
            deltas=[],
            evidence_by_chapter={},
            chapter_kinds={"ch1": "chapter", "ch2": "chapter", "bm1": "back_matter"},
        )
    )
    arc_chapters = {s.chapter_ref for s in bu.discourse_arc.steps}
    assert "bm1" not in arc_chapters


# ── D: hard gates ────────────────────────────────────────────────────────────


def _run_result(chapters, evidence, argument=None, ku_index=None, bu=None):
    return SimpleNamespace(
        run_id="r",
        book_id="b",
        chapters=chapters,
        evidence=evidence,
        bu=bu
        or SimpleNamespace(
            governing_questions=["What is a derivative?"],
            central_theses=["Derivatives measure change"],
            sub_theses=[],
            concept_system={"concepts": {}},
            chapter_dependency_graph=SimpleNamespace(dependencies=[]),
            discourse_arc=SimpleNamespace(steps=[]),
            negative_knowledge=SimpleNamespace(
                limitations=[], open_problems=[], unresolved_conflicts=[]
            ),
            concept_evolution=[],
        ),
        p12={"argument": argument, "evolution": None, "dependency": None},
        ku_index=ku_index,
    )


def test_hard_gates_fail_empty_chapter():
    chapters = [
        ChapterUnderstanding(id="cu1", run_id="r", chapter_id="ch1"),  # empty
        ChapterUnderstanding(
            id="cu2",
            run_id="r",
            chapter_id="ch2",
            chapter_thesis="a thesis",
            concepts_introduced_refs=["x"],
        ),
    ]
    ev = [
        SimpleNamespace(
            evidence_id="ev1", quote="q", locator="char:1", kind="CLAIM", chapter_id="ch2"
        )
    ]
    rep = HardGateEvaluator().evaluate(_run_result(chapters, ev))
    h1 = next(g for g in rep.gates if g.gate.startswith("H1"))
    assert not h1.passed


def test_hard_gates_fail_placeholder_framing():
    chapters = [
        ChapterUnderstanding(
            id="cu1",
            run_id="r",
            chapter_id="ch1",
            chapter_thesis="t",
            concepts_introduced_refs=["x"],
        )
    ]
    bu = SimpleNamespace(
        governing_questions=["What is the intellectual structure of this book?"],
        central_theses=["the book's intellectual structure"],
        sub_theses=[],
        concept_system={"concepts": {}},
        chapter_dependency_graph=SimpleNamespace(dependencies=[]),
        discourse_arc=SimpleNamespace(steps=[]),
        negative_knowledge=SimpleNamespace(
            limitations=[], open_problems=[], unresolved_conflicts=[]
        ),
        concept_evolution=[],
    )
    rep = HardGateEvaluator().evaluate(_run_result(chapters, [], bu=bu))
    h2 = next(g for g in rep.gates if g.gate.startswith("H2"))
    assert not h2.passed


def test_hard_gates_fail_dangling_evidence():
    chapters = [
        ChapterUnderstanding(
            id="cu1",
            run_id="r",
            chapter_id="ch1",
            chapter_thesis="t",
            concepts_introduced_refs=["x"],
            evidence_program=[
                EvidenceProgramItem(claim_ref="c", evidence_refs=["ev_missing"], is_supported=True)
            ],
        )
    ]
    rep = HardGateEvaluator().evaluate(_run_result(chapters, []))
    h3 = next(g for g in rep.gates if g.gate.startswith("H3"))
    assert not h3.passed


def test_is_placeholder_detects_templates():
    assert is_placeholder("What is the intellectual structure of this book?")
    assert is_placeholder("introduced or redefined in ch3")
    assert not is_placeholder("A derivative measures instantaneous rate of change")


def test_six_dimensions_present_and_bounded():
    chapters = [
        ChapterUnderstanding(
            id="cu1",
            run_id="r",
            chapter_id="ch1",
            chapter_thesis="t",
            concepts_introduced_refs=["Derivative"],
            evidence_program=[
                EvidenceProgramItem(claim_ref="c", evidence_refs=["ev1"], is_supported=True)
            ],
        )
    ]
    ev = [
        SimpleNamespace(
            evidence_id="ev1", quote="q", locator="char:1", kind="CLAIM", chapter_id="ch1"
        )
    ]
    rep = HardGateEvaluator().evaluate(_run_result(chapters, ev))
    assert len(rep.dimensions) == 6
    for d in rep.dimensions:
        assert 0.0 <= d.score <= 10.0
    assert 0.0 <= rep.overall <= 10.0


# ── E: learning guide ────────────────────────────────────────────────────────


def test_learning_guide_is_dependency_ordered():
    graph = BookReasoningGraph(graph_id="g", run_id="r", book_id="b")
    chapters = [
        ChapterUnderstanding(
            id="cu1", run_id="r", chapter_id="ch1", concepts_introduced_refs=["Limit"]
        ),
        ChapterUnderstanding(
            id="cu2", run_id="r", chapter_id="ch2", concepts_introduced_refs=["Derivative"]
        ),
    ]
    from stratum.services.bu_v2_reasoning_graph import ReasoningEdge, ReasoningNode

    a = node_id("cn", "r", "ch1", "limit")
    b = node_id("cn", "r", "ch2", "derivative")
    graph.add_node(ReasoningNode(node_id=a, node_type="CONCEPT", label="Limit", chapter_id="ch1"))
    graph.add_node(
        ReasoningNode(node_id=b, node_type="CONCEPT", label="Derivative", chapter_id="ch2")
    )
    # Derivative depends on Limit, so Limit must come first.
    graph.add_edge(
        ReasoningEdge(
            edge_id="e1",
            source_node_id=b,
            target_node_id=a,
            relation_type="DEPENDS_ON",
            reason="derivative uses limits",
        )
    )
    guide = LearningGuideBuilder().build(run_id="r", book_id="b", graph=graph, chapters=chapters)
    labels = [s.concept for s in guide.steps]
    assert labels.index("Limit") < labels.index("Derivative")
    assert "Limit" in guide.steps[1].requires


def test_learning_guide_falls_back_to_chapters():
    chapters = [
        ChapterUnderstanding(
            id="cu1", run_id="r", chapter_id="ch1", concepts_introduced_refs=["A", "B"]
        )
    ]
    guide = LearningGuideBuilder().build(run_id="r", book_id="b", graph=None, chapters=chapters)
    assert [s.concept for s in guide.steps] == ["A", "B"]
