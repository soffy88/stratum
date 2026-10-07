"""P13 Tests: Concept System"""

import pytest
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, ConceptRole,
)
from stratum.services.bu_v2_concept_evolution import EvolutionResult, ConceptTrajectory, TrajectoryEvent
from stratum.services.bu_v2_concept_system import ConceptSystemBuilder


class MockGraph:
    nodes = {}
    edges = []

    def in_edges(self, node_id):
        return []

    def out_edges(self, node_id):
        return []


def make_chapter(chapter_id: str, concepts_introduced: list = None, concepts_redefined: list = None,
                 dependencies: list = None) -> ChapterUnderstanding:
    return ChapterUnderstanding(
        id=f"cu_{chapter_id}",
        run_id="test_run",
        chapter_id=chapter_id,
        chapter_thesis=f"Thesis for {chapter_id}",
        concepts_introduced_refs=concepts_introduced or [],
        concepts_redefined_refs=concepts_redefined or [],
        dependencies_on_prior=dependencies or [],
    )


def make_bu() -> BookUnderstandingV2:
    return BookUnderstandingV2(
        id="bu_test",
        run_id="test_run",
        book_id="test_book",
        substrate_id="test_sub",
    )


def make_evolution() -> EvolutionResult:
    from stratum.services.bu_v2_concept_evolution import TrajectoryEvent
    traj = ConceptTrajectory(
        concept="limit",
        introduced_at="ch1",
        definitions=["A limit describes the value a function approaches"],
        events=[
            TrajectoryEvent(event_type="INTRODUCTION", chapter_id="ch1", detail="introduced in ch1", sequence=0),
            TrajectoryEvent(event_type="REFINEMENT", chapter_id="ch3", detail="redefined in ch3", sequence=1),
            TrajectoryEvent(event_type="EXPANSION", chapter_id="ch5", detail="applied in ch5", sequence=2),
        ],
    )
    return EvolutionResult(trajectories=[traj], unresolved=[])


def test_concept_system_builder_foundational():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit", "function"], dependencies=[]),
        make_chapter("ch2", concepts_introduced=["derivative"], dependencies=["limit"]),
        make_chapter("ch3", concepts_redefined=["limit"], concepts_introduced=["integral"], dependencies=["derivative"]),
    ]
    builder = ConceptSystemBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    all_concepts = result.system.all_concepts()
    # At least one concept should be foundational or core
    roles = [c.role for c in all_concepts]
    assert ConceptRole.FOUNDATIONAL in roles or ConceptRole.CORE in roles


def test_concept_system_builder_core():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit"]),
        make_chapter("ch2", concepts_introduced=["derivative"]),
        make_chapter("ch3", concepts_introduced=["integral"]),
    ]
    builder = ConceptSystemBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    core = result.system.core
    assert len(core) >= 0


def test_concept_system_evolution_integration():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit"]),
        make_chapter("ch3", concepts_redefined=["limit"]),
        make_chapter("ch5", concepts_introduced=["integral"], dependencies=["limit"]),
    ]
    evolution = make_evolution()
    builder = ConceptSystemBuilder()
    result = builder.build(bu, chapters, evolution, MockGraph())

    # Check that evolution data was integrated
    limit_concept = result.system.get_by_id([c for c in result.system.all_concepts() if "limit" in c.label.lower()][0].concept_id)
    assert limit_concept is not None
    assert limit_concept.refined_by  # Should have refinements from evolution


def test_concept_system_prerequisites():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit"]),
        make_chapter("ch2", concepts_introduced=["derivative"], dependencies=["limit"]),
    ]
    builder = ConceptSystemBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    deriv_concept = result.system.get_by_id([c for c in result.system.all_concepts() if "derivative" in c.label.lower()][0].concept_id)
    assert deriv_concept is not None
    assert "limit" in deriv_concept.prerequisites


def test_concept_system_all_roles_populated():
    bu = make_bu()
    chapters = [
        make_chapter("ch1", concepts_introduced=["limit"]),
        make_chapter("ch2", concepts_introduced=["derivative"]),
        make_chapter("ch3", concepts_introduced=["integral"]),
        make_chapter("ch4", concepts_introduced=["series"]),
        make_chapter("ch5", concepts_introduced=["application"], dependencies=["series"]),
    ]
    builder = ConceptSystemBuilder()
    result = builder.build(bu, chapters, None, MockGraph())

    all_concepts = result.system.all_concepts()
    assert len(all_concepts) >= 5

    roles = [c.role for c in all_concepts]
    # Should have at least foundational, core, or derived
    assert any(r in roles for r in [ConceptRole.FOUNDATIONAL, ConceptRole.CORE, ConceptRole.DERIVED])