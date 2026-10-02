"""Quality evaluator tests — spec §13.2.

    missing evidence, missing mechanism, incomplete integration

Each test removes one thing from an otherwise complete understanding and asserts
that the corresponding dimension falls. A quality model that cannot detect a
missing part is not measuring anything, so the negative cases are the substance
of this file rather than a footnote to it.

§10 and §11 are tested here too: quality must never become a verdict, and a low
quality level must never block publication.
"""

from __future__ import annotations

from stratum.knowledge.bu_v2_models import (
    ArgumentArchitecture,
    BookUnderstandingV2,
    BUStatus,
    ChapterDelta,
    ChapterUnderstanding,
    EvidenceProgramItem,
    NegativeKnowledge,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_producer import EvidenceArtifact
from stratum.services.bu_v2_provider import StaticProvider
from stratum.services.bu_v2_quality_evaluator import (
    BUQualityEvaluator,
    level_for,
    quality_context_lines,
)
from stratum.services.bu_v2_quality_report import evaluate_gates, render_gates
from stratum.services.bu_v2_verifier import BUVerifier

FRAMING = {
    "genre": "mathematics",
    "governing_questions": ["What is change?", "How is it measured?"],
    "central_theses": ["Change is captured by limits"],
    "sub_theses": ["Continuity precedes differentiability", "Rates are local"],
}


def make_chapters(n: int = 3, **kw) -> list[ChapterUnderstanding]:
    out = []
    for i in range(1, n + 1):
        out.append(
            ChapterUnderstanding(
                id=f"cu{i}",
                run_id="r",
                chapter_id=f"ch{i}",
                chapter_question=f"question {i}",
                chapter_goal=f"goal {i}",
                chapter_thesis=f"thesis {i}",
                primary_role=kw.get("role", "CONCEPT_BUILDING"),
                concepts_introduced_refs=list(kw.get("concepts", [f"concept{i}"])),
                concepts_redefined_refs=list(kw.get("redefined", [])),
                mechanisms_refs=list(kw.get("mechanisms", [f"mechanism {i}"])),
                dependencies_on_prior=list(kw.get("deps", [f"concept{i - 1}"]) if i > 1 else []),
                assumptions=list(kw.get("assumptions", ["assumes continuity"])),
                qualifications=list(kw.get("qualifications", ["approximate near the limit"])),
                evidence_program=[EvidenceProgramItem(
                    claim_ref=f"claim {i}", evidence_refs=[f"ev{i}"], is_supported=True
                )] * kw.get("programs", 2),
            )
        )
    return out


def make_evidence(n: int = 12) -> list[EvidenceArtifact]:
    return [
        EvidenceArtifact(
            evidence_id=f"ev{i}",
            run_id="r",
            chapter_id="ch1",
            kind="CLAIM",
            locator=f"char:{1000 + i}",
            quote="a located quote",
            content_hash=f"h{i}",
        )
        for i in range(n)
    ]


def integrate(chapters, **kw):
    return BookIntegrator(provider=StaticProvider(kw.get("framing", FRAMING))).integrate(
        IntegrationInput(
            run_id="r",
            book_id="b1",
            substrate_id="s1",
            chapters=chapters,
            deltas=kw.get("deltas", []),
            evidence_by_chapter={},
        )
    )


STRUCTURE_META = {"chapter_count": 3, "confidence_mean": 0.95}


def evaluate(chapters=None, evidence=None, bu=None, structure=None, status="PASS"):
    chapters = make_chapters() if chapters is None else chapters
    evidence = make_evidence() if evidence is None else evidence
    bu = integrate(chapters) if bu is None else bu
    return BUQualityEvaluator().evaluate(
        bu,
        chapters=chapters,
        evidence=evidence,
        pipeline_status=status,
        structure=STRUCTURE_META if structure is None else structure,
    )


def score_of(report, key):
    return next(d for d in report.dimensions if d.key == key).score


# ── baseline ─────────────────────────────────────────────────────────────────


def test_complete_understanding_scores_well():
    rep = evaluate()
    assert len(rep.dimensions) == 7, "§8.2 defines seven dimensions"
    assert rep.overall > 0.5
    assert rep.quality_level in ("A", "B", "C")


def test_all_seven_dimensions_are_present_and_named():
    rep = evaluate()
    keys = [d.key for d in rep.dimensions]
    assert keys == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
    names = {d.name for d in rep.dimensions}
    assert names == {
        "Structure", "Concept", "Mechanism", "Argument",
        "Integration", "Evidence", "Boundary",
    }


# ── §13.2 missing evidence ───────────────────────────────────────────────────


def test_missing_evidence_scores_zero_and_is_reported():
    rep = evaluate(evidence=[])
    assert score_of(rep, "Q6") == 0.0
    assert any("traceable" in f for f in rep.limitations)
    assert "nothing in this understanding is traceable" in " ".join(rep.limitations)


def test_evidence_without_locator_is_penalised():
    ev = make_evidence(10)
    for e in ev[5:]:
        e.locator = ""
    rep = evaluate(evidence=ev)
    assert score_of(rep, "Q6") < 0.9
    assert any("no source location" in f for f in rep.limitations)


def test_evidence_dimensions_measure_traceability_not_truth():
    """§8: not fact-versus-fiction. Two runs with identical evidence differ in
    nothing here, because truth is not an input to this model."""
    a = evaluate()
    b = evaluate(status="FAIL")
    assert score_of(a, "Q6") == score_of(b, "Q6")


# ── §13.2 missing mechanism ──────────────────────────────────────────────────


def test_missing_mechanism_is_detected():
    rep = evaluate(chapters=make_chapters(mechanisms=[]))
    assert score_of(rep, "Q3") < 0.3
    assert any("causal explanation" in f for f in rep.limitations)


def test_mechanisms_not_carried_to_book_level_is_reported():
    chapters = make_chapters(mechanisms=["m"])
    bu = integrate(chapters)
    bu.concept_system["mechanisms"] = []
    rep = evaluate(chapters=chapters, bu=bu)
    assert any("nothing was carried" in f for f in rep.limitations)


# ── §13.2 incomplete integration ─────────────────────────────────────────────


def test_no_cross_chapter_relations_reads_as_a_collection():
    """§10.4: a chapter collection is not a book model."""
    rep = evaluate(chapters=make_chapters(deps=[]))
    assert score_of(rep, "Q5") < 0.6
    assert any("collection rather than a model" in f for f in rep.limitations)


def test_cross_chapter_relations_raise_integration():
    """The dependency must name a concept an earlier chapter introduced,
    otherwise it resolves to nothing and no edge is formed."""
    with_deps = score_of(evaluate(chapters=make_chapters(deps=["concept1"])), "Q5")
    without = score_of(evaluate(chapters=make_chapters(deps=[])), "Q5")
    assert with_deps > without, f"{with_deps} should exceed {without}"


def test_unresolvable_dependency_produces_no_edge():
    """A dependency naming an unknown concept must not invent an edge."""
    chapters = make_chapters(deps=["a concept no chapter ever introduced"])
    bu = integrate(chapters)
    assert bu.chapter_dependency_graph.dependencies == []


def test_missing_book_framing_is_reported():
    chapters = make_chapters()
    bu = integrate(chapters, framing={"genre": "mathematics"})
    rep = evaluate(chapters=chapters, bu=bu)
    assert score_of(rep, "Q5") < 0.7
    assert any("book-level framing" in f for f in rep.limitations)


# ── boundary / self-knowledge ────────────────────────────────────────────────


def test_boundary_rewards_recording_own_limits():
    blind = integrate(make_chapters())
    blind.negative_knowledge = NegativeKnowledge()
    aware = integrate(make_chapters())
    assert score_of(evaluate(bu=blind), "Q7") < score_of(evaluate(bu=aware), "Q7")


def test_failed_chapter_is_recorded_as_a_conflict():
    chapters = make_chapters()
    chapters[1].primary_role = "UNDERSTANDING_FAILED"
    rep = evaluate(chapters=chapters)
    assert any("could not be understood" in f for f in rep.limitations)


# ── §10: pipeline status is not quality ──────────────────────────────────────


def test_pipeline_status_is_carried_and_never_computed():
    rep = evaluate(status="FAIL")
    assert rep.pipeline_status == "FAIL"
    # A failed pipeline with rich understanding still scores on understanding.
    assert score_of(rep, "Q1") > 0.9


def test_quality_report_states_independence():
    rep = evaluate()
    assert "independent of quality" in rep.render()


# ── §11: quality does not block publication ──────────────────────────────────


def test_quality_level_cannot_change_a_verification_outcome():
    bu = integrate(make_chapters())
    verifier = BUVerifier()
    good = verifier.verify(bu, chapter_count=3, evidence_count=12, failed_chapters=0)
    rep = evaluate(bu=bu)
    rep.quality_level = "D"  # force the worst grade
    # The verification report is a separate object and is unaffected.
    assert good.outcome.value in ("PASS", "FAIL")
    assert verifier.verify(bu, chapter_count=3, evidence_count=12, failed_chapters=0).outcome == good.outcome


def test_low_quality_still_verifies():
    """§11: a shallow but correctly produced understanding must publish."""
    chapters = make_chapters(mechanisms=[], deps=[], assumptions=[], qualifications=[])
    bu = integrate(chapters)
    report = BUVerifier().verify(bu, chapter_count=3, evidence_count=12, failed_chapters=0)
    rep = evaluate(chapters=chapters, bu=bu)
    assert rep.quality_level in ("C", "D")
    assert report.outcome.value == "PASS", "quality must not block publication"


def test_level_bands_are_ordered():
    assert level_for(0.95) == "A"
    assert level_for(0.70) == "B"
    assert level_for(0.50) == "C"
    assert level_for(0.10) == "D"


# ── §12: quality context phrasing ────────────────────────────────────────────


def test_quality_context_is_confidence_not_truth():
    rep = evaluate()
    lines = quality_context_lines(rep)
    joined = " ".join(lines).lower()
    assert "confidence" in joined
    assert "pipeline status" in joined
    for banned in ("truth score", "accuracy of the book", "correctness"):
        assert banned not in joined, f"{banned} would disguise quality as truth"


def test_quality_context_names_five_dimensions():
    lines = quality_context_lines(evaluate())
    for key in ("Q1", "Q6", "Q3", "Q5", "Q7"):
        assert any(key in l for l in lines), f"{key} missing from quality context"


# ── §9 report shape ──────────────────────────────────────────────────────────


def test_report_has_every_named_field():
    d = evaluate().to_dict()
    for field in (
        "book_id", "structure_score", "concept_score", "mechanism_score",
        "argument_score", "integration_score", "evidence_score",
        "boundary_score", "overall", "quality_level", "limitations",
    ):
        assert field in d, f"{field} missing from §9 report"
    assert d["pipeline_status"] == "PASS"


def test_render_shows_a_level_per_dimension():
    out = evaluate().render()
    for name in ("Structure", "Concept", "Mechanism", "Argument",
                 "Integration", "Evidence", "Boundary", "OVERALL"):
        assert name in out


# ── §15 gates ────────────────────────────────────────────────────────────────


def test_gates_fail_when_measurements_are_missing():
    """A gate that cannot be measured is FAIL, never skipped."""
    gates = evaluate_gates(evaluate(), structure=None, detection_ratio=None)
    assert gates[0].passed is False
    assert "unavailable" in gates[0].detail


def test_gates_report_coverage_with_both_measures():
    gates = evaluate_gates(
        evaluate(), structure=STRUCTURE_META, detection_ratio=1.0,
        coverage_ratio=0.96, content_coverage=1.0, context_used=True, chapter_count=3,
        legacy_fused=True,
    )
    coverage = next(g for g in gates if g.gate == "7_real_book_coverage")
    assert coverage.passed is True
    assert "content 100.00%" in coverage.detail


def test_render_gates_counts_honestly():
    gates = evaluate_gates(evaluate(), structure=STRUCTURE_META, detection_ratio=1.0,
                           coverage_ratio=1.0, content_coverage=1.0,
                           context_used=True, chapter_count=3, legacy_fused=True)
    out = render_gates(gates)
    assert "gates passed" in out
    assert "PASS" in out