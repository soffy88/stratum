"""P13 Tests: Evidence Map"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, EvidenceStrengthP13,
    ThesisProvenance,
)
from stratum.services.bu_v2_evidence_map import EvidenceMapBuilder
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis, ArgumentChain, ArgumentNode, ArgumentEdge


class MockGraph:
    nodes = {}
    edges = []

    def out_edges(self, node_id):
        return []


def make_chapter(chapter_id: str, evidence_items: list = None) -> ChapterUnderstanding:
    from stratum.knowledge.bu_v2_models import EvidenceProgramItem
    cu = ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=f"Thesis for {chapter_id}",
        evidence_program=evidence_items or [],
        evidence_strengths={},
    )
    return cu


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
    )


def make_evidence_item(claim: str, refs: list, supported: bool) -> 'EvidenceProgramItem':
    from stratum.knowledge.bu_v2_models import EvidenceProgramItem
    return EvidenceProgramItem(
        claim_ref=claim,
        evidence_refs=refs,
        is_supported=supported,
    )


def test_evidence_map_builder_basic():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", evidence_items=[
            make_evidence_item("FTC connects diff and int", ["ev1", "ev2"], True),
            make_evidence_item("Limits are foundational", ["ev3"], False),
        ]),
        make_chapter("ch2", evidence_items=[
            make_evidence_item("Derivatives measure rates", ["ev4"], True),
        ]),
    ]
    builder = EvidenceMapBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    assert len(result.evidence_map.entries) >= 3
    for entry in result.evidence_map.entries:
        assert entry.claim_id
        assert entry.claim_statement
        assert isinstance(entry.evidence_ids, list)
        assert isinstance(entry.evidence_strengths, dict)


def test_evidence_map_coverage():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", evidence_items=[
            make_evidence_item("Claim 1", ["ev1"], True),
            make_evidence_item("Claim 2", ["ev2"], True),
            make_evidence_item("Claim 3", ["ev3"], False),
        ]),
    ]
    builder = EvidenceMapBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    em = result.evidence_map
    assert abs(em.evidence_coverage - 2/3) < 0.001  # 2 of 3 supported
    assert em.unsupported_claim_count == 1


def test_evidence_map_model_inference_ratio():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", evidence_items=[
            make_evidence_item("Supported claim", ["ev1"], True),
            make_evidence_item("Unsupported claim", [], False),
        ]),
    ]
    builder = EvidenceMapBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    em = result.evidence_map
    # Model inference ratio should be computed
    assert 0 <= em.model_inference_ratio <= 1


def test_evidence_map_argument_links():
    from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis, ArgumentChain, ArgumentNode

    bu = make_bu()
    chapters = [make_chapter("ch1", evidence_items=[
        make_evidence_item("FTC claim", ["ev1"], True),
    ])]

    arg_analysis = ArgumentAnalysis()
    chain = ArgumentChain(
        chain_id="chain1",
        chapter_id="ch1",
        claim=ArgumentNode(node_id="an1", node_kind="CLAIM", label="FTC claim", chapter_id="ch1", confidence=0.7),
        evidence=[ArgumentNode(node_id="an2", node_kind="EVIDENCE", label="ev1", chapter_id="ch1", confidence=0.6, evidence_refs=["ev1"])],
        evidence_strength="DIRECT",
        complete=True,
    )
    arg_analysis.chains = [chain]
    arg_analysis.nodes = {n.node_id: n for n in [chain.claim] + chain.evidence}

    builder = EvidenceMapBuilder()
    result = builder.build(bu, chapters, arg_analysis, MockGraph())

    # Entry should have argument_ids from chain
    entry = next((e for e in result.evidence_map.entries if "FTC" in e.claim_statement), None)
    assert entry is not None
    assert "chain1" in entry.argument_ids or len(entry.argument_ids) > 0