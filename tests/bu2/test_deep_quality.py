"""Deep quality tests — spec §10.

Q8-Q11 must do the work P11's Q5 could not: detect that chapters are isolated,
that claims are asserted rather than argued, and that concepts never change.

The negative cases are the substance here. A quality model that cannot detect a
missing thing is not measuring anything.
"""

from __future__ import annotations

from stratum.knowledge.bu_v2_models import (
    ChapterDelta,
    ChapterUnderstanding,
    EvidenceProgramItem,
)
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalyzer
from stratum.services.bu_v2_concept_evolution import ConceptEvolutionBuilder
from stratum.services.bu_v2_deep_quality import DeepQualityEvaluator
from stratum.services.bu_v2_dependency_builder import DependencyBuilder

FILLER = "The chapter develops the idea with worked examples. " * 100


def cu(n, intro=(), redef=(), thesis="", mech=("m",), programs=1):
    thesis = thesis or f"thesis {n}"
    return ChapterUnderstanding(
        id=f"cu{n}", run_id="r", chapter_id=f"ch{n}", chapter_thesis=thesis,
        concepts_introduced_refs=list(intro), concepts_redefined_refs=list(redef),
        mechanisms_refs=list(mech), qualifications=["a stated limit"],
        evidence_program=[
            EvidenceProgramItem(claim_ref=f"c{i}", evidence_refs=[f"ev{i}"], is_supported=True)
            for i in range(programs)
        ],
    )


def deep(chapters, text=None, deltas=None, chapter_count=None):
    dep = DependencyBuilder().build(chapters, run_id="r", book_id="b", chapter_text=text or {})
    evo = ConceptEvolutionBuilder().build(chapters, run_id="r", book_id="b", deltas=deltas or [])
    arg = ArgumentAnalyzer().analyze(chapters, run_id="r", book_id="b")
    n = chapter_count if chapter_count is not None else len(chapters)
    return DeepQualityEvaluator().evaluate(
        book_id="b", run_id="r", graph=dep.graph, evolution=evo, argument=arg,
        chapter_count=n, pipeline_status="PASS",
    )


def score(report, key):
    return next(d for d in report.dimensions if d.key == key).score


# ── the four dimensions exist ────────────────────────────────────────────────


def test_four_dimensions_are_scored():
    r = deep([cu(1), cu(2)])
    assert [d.key for d in r.dimensions] == ["Q8", "Q9", "Q10", "Q11"]
    assert all(0.0 <= d.score <= 1.0 for d in r.dimensions)


# ── Q10: isolated chapters are detected ──────────────────────────────────────


def test_isolated_chapters_score_zero_on_coherence():
    r = deep([cu(i) for i in range(1, 5)], text={f"ch{i}": FILLER for i in range(1, 5)})
    # Even with the sequence fallback, only 2 of 4 chapters participate.
    assert score(r, "Q10") < 1.0


def test_coherence_reports_how_many_chapters_are_connected():
    text = {f"ch{i}": FILLER for i in range(1, 5)}
    text["ch1"] = "we rely on Chapter 2 throughout. " + FILLER
    r = deep([cu(i) for i in range(1, 5)], text=text)
    q10 = next(d for d in r.dimensions if d.key == "Q10")
    assert "chapters connected" in q10.detail
    assert q10.findings, "a thin graph must say so"


def test_well_connected_chapters_score_higher():
    thin = deep([cu(i) for i in range(1, 5)], text={f"ch{i}": FILLER for i in range(1, 5)})
    rich_text = {f"ch{i}": FILLER for i in range(1, 5)}
    for i in range(1, 5):
        rich_text[f"ch{i}"] = (
            f"we depend on Chapter {i + 1} and Chapter {i - 1} here. " if 1 < i < 4
            else f"see Chapter {i + 1} which we rely on. " + FILLER
        )
    rich = deep([cu(i) for i in range(1, 5)], text=rich_text)
    assert score(rich, "Q10") > score(thin, "Q10")


def test_directly_evidenced_relations_beat_derived_ones():
    stated = {f"ch{i}": FILLER for i in range(1, 4)}
    stated["ch1"] = "this depends on Chapter 2. " + FILLER
    stated["ch2"] = "this depends on Chapter 1. " + FILLER
    r = deep([cu(i) for i in range(1, 3)], text=stated)
    q10 = next(d for d in r.dimensions if d.key == "Q10")
    assert "directly evidenced" in q10.detail


# ── Q8: asserted is not argued ───────────────────────────────────────────────


def test_claims_without_conclusions_score_low_on_reasoning():
    bare = deep([cu(i, mech=(), programs=1) for i in range(1, 4)])
    argued = deep([cu(i, mech=("m",), programs=2) for i in range(1, 4)])
    assert score(argued, "Q8") > score(bare, "Q8")


def test_no_chains_scores_zero_on_reasoning():
    r = deep([ChapterUnderstanding(id="cu1", run_id="r", chapter_id="ch1")])
    assert score(r, "Q8") == 0.0
    assert any("advances nothing" in f for f in r.limitations)


# ── Q9: static concepts are detected ─────────────────────────────────────────


def test_static_concepts_score_low_on_evolution():
    r = deep([cu(1, intro=["limit"]), cu(2, intro=["continuity"])])
    assert score(r, "Q9") < 0.5


def test_evolving_concepts_score_higher():
    evolving = deep(
        [cu(1, intro=["limit"]), cu(4, intro=["integral"], redef=["limit"])],
        deltas=[ChapterDelta(id="d", run_id="r", chapter_id="ch4", revised_concepts_refs=["limit"])],
    )
    static = deep([cu(1, intro=["limit"]), cu(4, intro=["integral"])])
    assert score(evolving, "Q9") > score(static, "Q9")


def test_no_concepts_scores_zero_on_evolution():
    r = deep([cu(1), cu(2)])
    assert score(r, "Q9") == 0.0


# ── Q11: author model ────────────────────────────────────────────────────────


def test_backward_only_references_read_as_cumulative():
    text = {f"ch{i}": FILLER for i in range(1, 4)}
    text["ch3"] = "as established in Chapter 2, we proceed. " + FILLER
    r = deep([cu(i) for i in range(1, 4)], text=text)
    q11 = next(d for d in r.dimensions if d.key == "Q11")
    assert "backward" in q11.detail


def test_forward_references_indicate_planning():
    text = {f"ch{i}": FILLER for i in range(1, 4)}
    text["ch1"] = "we defer this until Chapter 3, which builds on it. " + FILLER
    r = deep([cu(i) for i in range(1, 4)], text=text)
    q11 = next(d for d in r.dimensions if d.key == "Q11")
    assert q11.score > 0


def test_no_graph_scores_zero_on_author_model():
    r = deep([cu(1)], text={}, chapter_count=1)
    assert score(r, "Q11") == 0.0
    assert any("why the book is ordered" in f for f in r.limitations)


# ── §10/§11: quality never gates ─────────────────────────────────────────────


def test_pipeline_status_is_carried_and_independent():
    r = deep([cu(1)])
    assert r.pipeline_status == "PASS"
    assert "independent of quality" in r.render()


def test_low_deep_quality_does_not_change_a_verdict():
    from stratum.services.bu_v2_verifier import BUVerifier
    from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
    from stratum.services.bu_v2_provider import StaticProvider

    chapters = [cu(i, intro=[f"c{i}"]) for i in range(1, 3)]
    bu = BookIntegrator(
        provider=StaticProvider(
            {"genre": "g", "governing_questions": ["q"], "central_theses": ["t"]}
        )
    ).integrate(
        IntegrationInput(run_id="r", book_id="b", substrate_id="s", chapters=chapters, deltas=[], evidence_by_chapter={})
    )
    weak = deep(chapters, text={f"ch{i}": FILLER for i in range(1, 3)})
    assert weak.deep_level in ("C", "D")
    # A low quality understanding must still verify.
    assert BUVerifier().verify(bu, chapter_count=2, evidence_count=4, failed_chapters=0).outcome.value == "PASS"


def test_counts_are_reported_for_every_artefact():
    r = deep([cu(i) for i in range(1, 4)])
    for key in ("nodes", "edges", "cross_chapter_edges", "trajectories", "argument_chains", "unresolved"):
        assert key in r.counts


def test_render_names_what_is_not_shown():
    out = deep([ChapterUnderstanding(id="cu1", run_id="r", chapter_id="ch1")]).render()
    assert "Q8 Reasoning" in out and "Q9 Concept Evolution" in out
    assert "Q10 Cross-Chapter" in out and "Q11 Author Model" in out


def test_p12_gates_are_reachable_from_the_run_bundle():
    """Regression: main() called evaluate_p12_gates with no import in scope.

    A 50-minute book run completed and then died in the reporting step with a
    NameError. The gate list is now attached during execute() and read from the
    bundle, so the JSON path has nothing left to resolve.
    """
    from stratum.services.bu_v2_entrypoint import BU2Runner, RunResult
    from stratum.services.bu_v2_quality_report import evaluate_p12_gates
    from stratum.services.bu_v2_producer import Chapter

    runner = BU2Runner(provider=__import__(
        "stratum.services.bu_v2_provider", fromlist=["StaticProvider"]
    ).StaticProvider({"chapter_question": "q", "chapter_goal": "g", "chapter_thesis": "t"}))

    class Loader:
        def load(self, sid):
            body = "OVERVIEW x\n\nwe rely on Chapter 2 here. " * 200
            return ("T", "", [
                Chapter(chapter_id="ch1", number=1, title="1. A", text=body, start=0, end=len(body)),
                Chapter(chapter_id="ch2", number=2, title="2. B", text=body, start=0, end=len(body)),
            ])

    runner.loader = Loader()
    result = runner.execute("bk1")

    gates = evaluate_p12_gates(result, structure=result.structure)
    assert len(gates) == 7, "§17 defines seven P12 gates"
    assert result.report_bundle is not None
    p12 = [g for g in result.report_bundle.gates if g.gate.startswith("p12_")]
    assert len(p12) == 7, "every P12 gate must be attached to the bundle the JSON reads"
    # And the payload helper the CLI serialises must not raise.
    from stratum.services.bu_v2_entrypoint import _p12_payload
    assert _p12_payload(result) is not None


def test_back_matter_is_not_counted_as_a_chapter():
    """§13's denominator is chapters, not everything the loader emitted.

    An appendix is not a chapter. When it leaked into the count, the required
    edge threshold rose for a reason that has nothing to do with the author's
    reasoning.
    """
    from stratum.services.bu_v2_quality_report import numbered_chapter_ids

    class FakeResult:
        structure = {"chapters": [
            {"chapter_id": "ch1", "kind": "chapter"},
            {"chapter_id": "ch2", "kind": "chapter"},
            {"chapter_id": "ch17", "kind": "back_matter"},
            {"chapter_id": "ch18", "kind": "back_matter"},
        ]}
        chapters = [
            type("C", (), {"chapter_id": i})() for i in ("ch1", "ch2", "ch17", "ch18")
        ]

    ids = numbered_chapter_ids(FakeResult(), FakeResult.structure)
    assert ids == {"ch1", "ch2"}, f"back matter leaked into the denominator: {ids}"


def test_front_matter_is_also_excluded():
    from stratum.services.bu_v2_quality_report import numbered_chapter_ids

    class FakeResult:
        structure = {"chapters": [
            {"chapter_id": "ch0", "kind": "front_matter"},
            {"chapter_id": "ch1", "kind": "chapter"},
        ]}
        chapters = [type("C", (), {"chapter_id": i})() for i in ("ch0", "ch1")]

    assert numbered_chapter_ids(FakeResult(), FakeResult.structure) == {"ch1"}


def test_document_order_alone_does_not_make_a_book_coherent():
    """Q10 must not be satisfiable by adjacency.

    The sequence fallback emits one edge per adjacent chapter, so every book
    with two or more chapters produces a connected graph if adjacency counts.
    A shelf of unrelated essays would score as coherent, and the dimension
    would measure the existence of a book rather than its reasoning.
    """
    chapters = [cu(i) for i in range(1, 5)]
    text = {f"ch{i}": FILLER for i in range(1, 5)}
    dep = DependencyBuilder().build(chapters, run_id="r", book_id="b", chapter_text=text)
    assert dep.graph.edges, "the fallback must still emit edges for this test to mean anything"
    assert all(e.status == "uncertain" for e in dep.graph.edges), (
        "with no author reference, every edge should be the weak fallback"
    )
    r = deep(chapters, text=text)
    q10 = next(d for d in r.dimensions if d.key == "Q10")
    assert score(r, "Q10") == 0.0, f"adjacency alone scored {score(r, 'Q10')}"
    assert any("document order" in f for f in q10.findings)


def test_the_adjacency_fallback_is_still_reported_not_hidden():
    """Excluding it from the score must not exclude it from the record."""
    chapters = [cu(i) for i in range(1, 4)]
    text = {f"ch{i}": FILLER for i in range(1, 4)}
    dep = DependencyBuilder().build(chapters, run_id="r", book_id="b", chapter_text=text)
    r = deep(chapters, text=text)
    q10 = next(d for d in r.dimensions if d.key == "Q10")
    assert dep.cross_chapter_count > 0, "the fallback should still produce cross-chapter edges"
    assert "document order" in q10.detail
    assert r.counts["cross_chapter_edges"] >= 1


def test_gate_2_is_not_clearable_by_document_order():
    """§13 asks for effective relations; the gate must agree with Q10.

    The sequence fallback connects every book with 2+ chapters, so a gate
    that counts it passes on adjacency alone. This pins the asserted-only
    rule: a book with no author-stated relation fails p12_2 even though the
    graph is non-empty.
    """
    from stratum.services.bu_v2_quality_report import evaluate_p12_gates

    chapters = [cu(i) for i in range(1, 4)]
    text = {f"ch{i}": FILLER for i in range(1, 4)}
    dep = DependencyBuilder().build(chapters, run_id="r", book_id="b", chapter_text=text)
    assert dep.cross_chapter_count > 0, "fallback must fire for this test to mean anything"
    assert dep.asserted_cross_chapter_count == 0

    class FakeResult:
        p12 = {
            "dependency": dep,
            "evolution": None,
            "argument": None,
            "deep_quality": None,
        }
        structure = None

    FakeResult.chapters = chapters
    gates = evaluate_p12_gates(FakeResult(), structure=None)
    g2 = next(g for g in gates if g.gate == "p12_2_cross_chapter_dependency")
    assert not g2.passed, f"adjacency alone cleared the gate: {g2.detail}"
    assert "document order" in g2.detail


def test_gate_2_passes_on_asserted_relations():
    """The positive side: author-stated dependencies clear the gate."""
    from stratum.services.bu_v2_quality_report import evaluate_p12_gates

    chapters = [cu(i) for i in range(1, 5)]
    text = {f"ch{i}": FILLER for i in range(1, 5)}
    text["ch1"] = "we defer this until Chapter 3, which builds on it. " + FILLER
    text["ch2"] = "as shown before in Chapter 1, we extend it. " + FILLER
    dep = DependencyBuilder().build(chapters, run_id="r", book_id="b", chapter_text=text)
    assert dep.asserted_cross_chapter_count >= 2

    class FakeResult:
        p12 = {
            "dependency": dep,
            "evolution": None,
            "argument": None,
            "deep_quality": None,
        }
        structure = None

    FakeResult.chapters = chapters
    gates = evaluate_p12_gates(FakeResult(), structure=None)
    g2 = next(g for g in gates if g.gate == "p12_2_cross_chapter_dependency")
    assert g2.passed, f"asserted relations should clear the gate: {g2.detail}"


def test_structure_kinds_fallback_excludes_back_matter_in_real_runs():
    """The pipeline stores only metadata on result.structure.

    numbered_chapter_ids must still exclude back matter via
    result.structure_kinds, or §13's denominator silently grows in every real
    run while the unit tests (which pass a full structure dict) stay green.
    """
    from stratum.services.bu_v2_quality_report import numbered_chapter_ids

    class FakeResult:
        structure = {"chapter_count": 2}  # metadata only, as execute() stores
        structure_kinds = {"ch1": "chapter", "ch2": "chapter", "bm1": "back_matter"}
        chapters = [
            type("C", (), {"chapter_id": i})() for i in ("ch1", "ch2", "bm1")
        ]

    assert numbered_chapter_ids(FakeResult(), FakeResult.structure) == {"ch1", "ch2"}
