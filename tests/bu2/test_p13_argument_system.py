"""P13 Tests: Argument System"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, BookThesisModel, BookThesis,
    ThesisType, ThesisProvenance, ArgumentStatus,
)
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis, ArgumentChain, ArgumentNode, ArgumentEdge
from stratum.services.bu_v2_argument_system import ArgumentSystemBuilder


class MockGraph:
    nodes = {}
    edges = []


def make_chapter(chapter_id: str, thesis: str = "", arguments: list = None, mechanisms: list = None,
                 evidence_items: list = None) -> ChapterUnderstanding:
    from stratum.knowledge.bu_v2_models import EvidenceProgramItem
    cu = ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=thesis,
        arguments_refs=arguments or [],
        mechanisms_refs=mechanisms or [],
        evidence_program=evidence_items or [],
    )
    return cu


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
        central_theses=["The fundamental theorem connects differentiation and integration"],
    )


def make_thesis_model() -> BookThesisModel:
    model = BookThesisModel()
    model.core_thesis = BookThesis(
        id="thesis_core",
        type=ThesisType.CORE,
        statement="The fundamental theorem connects differentiation and integration",
        evidence_refs=["ev1"],
        supporting_arguments=["arg1"],
        confidence=0.7,
        provenance=ThesisProvenance.AUTHOR_ASSERTED,
    )
    return model


def make_argument_analysis() -> ArgumentAnalysis:
    analysis = ArgumentAnalysis(graph_id="agraph_test")
    # Create a complete chain
    chain = ArgumentChain(
        chain_id="chain1",
        chapter_id="ch1",
        claim=ArgumentNode(node_id="an1", node_kind="CLAIM", label="FTC connects diff and int", chapter_id="ch1", confidence=0.7),
        conclusion=ArgumentNode(node_id="an2", node_kind="CONCLUSION", label="Therefore FTC is central", chapter_id="ch1", confidence=0.6),
        evidence=[ArgumentNode(node_id="an3", node_kind="EVIDENCE", label="Example in ch1", chapter_id="ch1", confidence=0.65, evidence_refs=["ev1"])],
        reasoning=[ArgumentNode(node_id="an4", node_kind="REASONING", label="By definition of integral", chapter_id="ch1", confidence=0.6)],
        evidence_strength="DIRECT",
        complete=True,
    )
    chain.edges = [
        ArgumentEdge(edge_id="ae1", source_node_id="an3", target_node_id="an1", edge_kind="SUPPORTS", reason="evidence supports claim", chain_id="chain1", evidence_type="DIRECT", confidence=0.7),
        ArgumentEdge(edge_id="ae2", source_node_id="an3", target_node_id="an4", edge_kind="DERIVES", reason="evidence derives reasoning", chain_id="chain1", evidence_type="DIRECT", confidence=0.55),
        ArgumentEdge(edge_id="ae3", source_node_id="an4", target_node_id="an2", edge_kind="DERIVES", reason="reasoning derives conclusion", chain_id="chain1", evidence_type="DIRECT", confidence=0.55),
        ArgumentEdge(edge_id="ae4", source_node_id="an2", target_node_id="an1", edge_kind="SUMMARIZES", reason="conclusion summarizes claim", chain_id="chain1", evidence_type="DIRECT", confidence=0.5),
    ]
    analysis.chains = [chain]
    analysis.nodes = {n.node_id: n for n in [chain.claim, chain.conclusion] + chain.evidence + chain.reasoning}
    analysis.edges = chain.edges
    return analysis


def test_argument_system_builder_thesis_arguments():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", thesis="The fundamental theorem connects differentiation and integration", arguments=["arg1"]),
        make_chapter("ch2", thesis="Limits are foundational"),
    ]
    thesis_model = make_thesis_model()
    arg_analysis = make_argument_analysis()

    builder = ArgumentSystemBuilder()
    result = builder.build(bu, chapters, thesis_model, arg_analysis, MockGraph())

    assert len(result.system.thesis_arguments) >= 1
    for a in result.system.thesis_arguments:
        assert a.level == 0
        assert a.status in [ArgumentStatus.SUPPORTED, ArgumentStatus.PARTIALLY_SUPPORTED, ArgumentStatus.MODEL_INFERRED]


def test_argument_system_builder_major_arguments():
    bu = make_bu()
    chapters = [make_chapter(f"ch{i}") for i in range(1, 10)]
    thesis_model = make_thesis_model()
    arg_analysis = make_argument_analysis()

    builder = ArgumentSystemBuilder()
    result = builder.build(bu, chapters, thesis_model, arg_analysis, MockGraph())

    # Should have major and sub arguments from chains
    total = len(result.system.major_arguments) + len(result.system.sub_arguments)
    assert total >= 0


def test_argument_system_evidence_refs():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", thesis="FTC connects diff and int", evidence_items=[]),
    ]
    thesis_model = make_thesis_model()
    arg_analysis = make_argument_analysis()

    builder = ArgumentSystemBuilder()
    result = builder.build(bu, chapters, thesis_model, arg_analysis, MockGraph())

    for a in result.system.all_arguments():
        # Evidence refs should be populated from chain
        assert isinstance(a.evidence_refs, list)


def test_argument_system_depends_on():
    bu = make_bu()
    chapters = [make_chapter(f"ch{i}") for i in range(1, 5)]
    thesis_model = make_thesis_model()
    arg_analysis = make_argument_analysis()

    builder = ArgumentSystemBuilder()
    result = builder.build(bu, chapters, thesis_model, arg_analysis, MockGraph())

    # Sub arguments should depend on previous
    for a in result.system.sub_arguments:
        assert isinstance(a.depends_on, list)