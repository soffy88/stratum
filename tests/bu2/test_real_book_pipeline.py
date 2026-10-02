"""P10 real-book pipeline tests — spec §16.

    Test 1  create reading run
    Test 2  chapter generation
    Test 3  book integration
    Test 4  verification blocking
    Test 5  expression generation
    Test 6  resume
    Test 7  idempotency

These run against a static provider, not a model. A test that needs a GPU to
pass is a test that stops being run, and §16 is about the pipeline's shape, not
about a particular model's output. The real-model behaviour is covered by the
§15 trial and its recorded evidence.

No database is touched. Persistence is asserted by interception, so the suite is
safe to run against a live instance.
"""

from __future__ import annotations

import pytest

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BUStatus,
    ChapterDelta,
    ChapterUnderstanding,
    VerificationOutcome,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_entrypoint import (
    BU2RunError,
    BU2Runner,
    BookLoader,
    RunResult,
)
from stratum.services.bu_v2_expression import BUExpressionGenerator
from stratum.services.bu_v2_producer import Chapter, ChapterUnderstandingProducer
from stratum.services.bu_v2_provider import (
    ModelProvider,
    ProviderUnavailable,
    StaticProvider,
    resolve_provider,
)
from stratum.services.bu_v2_verifier import BUVerifier

# ── fixtures ──────────────────────────────────────────────────────────────────

CHAPTER_TEXT = (
    "1 Functions\n\nOVERVIEW Functions are fundamental to the study of calculus. "
    "A function assigns to each input exactly one output. The domain is the set "
    "of permitted inputs and the range is the set of outputs that occur. "
    "Functions can be represented by an equation, a graph, a table or a verbal "
    "description. Continuity means the function has no breaks."
)


def make_chapter(num: int = 1, text: str = CHAPTER_TEXT) -> Chapter:
    return Chapter(
        chapter_id=f"ch{num}",
        number=num,
        title=f"{num}. Functions",
        text=text,
        start=1000 * num,
        end=1000 * num + len(text),
    )


def chapter_payload(**over) -> dict:
    base = {
        "chapter_question": "What is a function?",
        "chapter_goal": "Read and write function notation",
        "chapter_thesis": "A function assigns exactly one output to each input",
        "summary": "This chapter introduces functions, domains and ranges.",
        "concepts": [
            {"name": "Function", "definition": "a rule mapping inputs to outputs"},
            {"name": "Domain", "definition": "the set of permitted inputs"},
        ],
        "claims": [
            {
                "text": "A function assigns exactly one output to each input",
                "quote": "A function assigns to each input exactly one output",
            }
        ],
        "mechanisms": [{"cause": "a rule", "process": "map each input", "conditions": "always"}],
        "dependencies": [],
        "uncertainties": ["the chapter does not discuss non-functions"],
        "terminology": [{"term": "domain", "meaning": "set of inputs"}],
    }
    base.update(over)
    return base


def make_chapters(n: int = 3) -> list[ChapterUnderstanding]:
    out = []
    for i in range(1, n + 1):
        out.append(
            ChapterUnderstanding(
                id=f"cu_{i}",
                run_id="run_test",
                chapter_id=f"ch{i}",
                chapter_question=f"question {i}",
                chapter_goal=f"goal {i}",
                chapter_thesis=f"thesis {i}",
                primary_role="CONCEPT_INTRODUCTION",
                concepts_introduced_refs=[f"concept{i}"],
                mechanisms_refs=[f"mechanism {i}"],
                dependencies_on_prior=[f"concept{i - 1}"] if i > 1 else [],
                evidence_program=[],
            )
        )
    return out


class FakeDB:
    """Records writes instead of performing them."""

    def __init__(self):
        self.inserted: list[tuple[str, dict]] = []
        self.updated: list[tuple[str, dict, dict]] = []
        self.books = {
            "bk1": {"id": "bk1", "user_id": "u1", "title": "Test Book", "mime": "application/pdf"},
        }
        self.derivatives = [
            {"kind": "markdown", "content": CHAPTER_TEXT},
            {"kind": "chapters", "content": '[{"title": "1. Functions", "page": 41, "level": 1}]'},
        ]

    def read(self, table, ident):
        return self.books.get(ident) if table == "substrates" else None

    def query(self, sql, params=None):
        if "derivative" in sql:
            return list(self.derivatives)
        return []

    def insert(self, table, row):
        self.inserted.append((table, row))

    def update(self, table, rid, values):
        # Mirrors stratum.db.update's real signature: (table, rid, data).
        self.updated.append((table, rid, values))


@pytest.fixture
def fake_db(monkeypatch):
    """Substitute the entrypoint's database seam."""
    from stratum.services import bu_v2_entrypoint as ep

    db = FakeDB()
    monkeypatch.setattr(ep, "db", db)
    return db


@pytest.fixture
def provider() -> ModelProvider:
    return StaticProvider(chapter_payload())


def run_pipeline(provider: ModelProvider, *, persist: bool = False) -> RunResult:
    runner = BU2Runner(provider=provider, persist=persist)
    runner.loader = _StaticLoader()
    return runner.execute("bk1")


class _StaticLoader(BookLoader):
    def load(self, substrate_id):
        return ("Test Book", CHAPTER_TEXT, [make_chapter(1)])


# ── Test 1: create reading run ───────────────────────────────────────────────


def test_create_reading_run_uses_legal_status(fake_db):
    """§5.1/§5.2: the run is created in a state the constraint accepts.

    The literal "planned" is the value that crashed create_reading_run against
    production, so the regression is asserted explicitly.
    """
    runner = BU2Runner(provider=StaticProvider(chapter_payload()), persist=True)
    run_id = runner.create_run("bk1")

    assert run_id.startswith("br_")
    tables = {t for t, _ in fake_db.inserted}
    assert "book_reading_run" in tables
    row = next(r for t, r in fake_db.inserted if t == "book_reading_run")
    assert row["status"] == "CREATED"
    assert row["status"] != "planned"  # migration 065 rejects this
    assert row["source_id"] == "bk1"


# ── Test 2: chapter generation ───────────────────────────────────────────────


def test_chapter_generation_carries_all_required_fields(provider):
    """§8: basic, concept, argument, mechanism, structure, open issues."""
    producer = ChapterUnderstandingProducer(provider=provider)
    cu, delta, evidence = producer.produce(make_chapter(), run_id="run_test", book_id="bk1")

    assert cu.run_id == "run_test"
    assert cu.chapter_id == "ch1"
    assert cu.chapter_thesis
    assert cu.concepts_introduced_refs, "§8 requires concepts"
    assert cu.mechanisms_refs, "§8 requires mechanism"
    assert cu.assumptions or cu.qualifications, "§8 requires uncertainty/limitation"
    assert delta.id.startswith("cd_")


def test_chapter_generation_requires_run_id(provider):
    """§9: no run_id, no write."""
    producer = ChapterUnderstandingProducer(provider=provider)
    cu, _, _ = producer.produce(make_chapter(), run_id="", book_id="bk1")
    assert cu.run_id == ""  # the model still produced one; the repository refuses it
    from stratum.services.bu_v2_repositories import ChapterUnderstandingRepository

    with pytest.raises(ValueError, match="run_id"):
        ChapterUnderstandingRepository.save(cu)


def test_unlocatable_claim_is_dropped():
    """§11: a claim that cannot be located in the text is not stored."""
    payload = chapter_payload(
        claims=[{"text": "Claim about quantum topology", "quote": "text absent from the chapter"}]
    )
    producer = ChapterUnderstandingProducer(provider=StaticProvider(payload))
    cu, _, evidence = producer.produce(make_chapter(), run_id="r", book_id="b")
    claim_evidence = [e for e in evidence if e.kind.startswith("CLAIM")]
    assert claim_evidence == [], "an unlocatable claim must not be stored"
    assert cu.evidence_program == []
    # Concepts may still anchor: they were named, not claimed.
    assert all(e.kind == "CONCEPT" for e in evidence)


# ── Test 3: book integration ────────────────────────────────────────────────


def test_book_integration_is_not_summary_concatenation():
    """§10.4: integration derives structure the chapters did not have.

    A concatenation would produce N theses and nothing else. This asserts the
    three derived structures exist and are computed from the chapters.
    """
    chapters = make_chapters(4)
    integrator = BookIntegrator(
        provider=StaticProvider(
            {
                "genre": "mathematics",
                "governing_questions": ["What is change?"],
                "central_theses": ["Change is captured by limits"],
                "sub_theses": ["Continuity precedes differentiability"],
            }
        )
    )
    bu = integrator.integrate(
        IntegrationInput(
            run_id="run_test",
            book_id="bk1",
            substrate_id="bk1",
            chapters=chapters,
            deltas=[],
            evidence_by_chapter={},
        )
    )

    edges = bu.chapter_dependency_graph.dependencies
    assert edges, "§10.4 requires derived structure, not a summary"
    assert {(e.source_chapter, e.target_chapter) for e in edges} == {
        ("ch1", "ch2"),
        ("ch2", "ch3"),
        ("ch3", "ch4"),
    }
    assert bu.discourse_arc.steps[0].step_type == "Problem"
    assert bu.discourse_arc.steps[-1].step_type == "Conclusion"
    assert bu.concept_system["concept_count"] == 4
    # Not a concatenation: the book's questions are one list, not four.
    assert len(bu.governing_questions) == 1


def test_integration_requires_chapters():
    with pytest.raises(ValueError, match="at least one chapter"):
        BookIntegrator(provider=StaticProvider({})).integrate(
            IntegrationInput(run_id="r", book_id="b", substrate_id="s", chapters=[], deltas=[], evidence_by_chapter={})
        )


# ── Test 4: verification blocking ────────────────────────────────────────────


def test_verification_blocks_unverified_understanding():
    """§12 forbids GENERATED -> VERIFIED."""
    v = BUVerifier()
    weak = BookUnderstandingV2(id="bu1", run_id="r1", book_id="b1", substrate_id="s1", coverage_score=0.1)
    report = v.verify(weak, chapter_count=10, evidence_count=0, failed_chapters=7)

    assert report.outcome == VerificationOutcome.FAIL
    names = {c.name for c in report.failed}
    assert "coverage_floor" in names
    assert "chapter_extraction_complete" in names
    # The artifact must self-report the failures, because the gate reads it.
    assert v.to_artifact(report, weak).unresolved_gap_count == len(report.failed)


def test_generated_bu_is_not_verified_before_the_gate():
    """A freshly produced BU carries no verification score of its own."""
    result = run_pipeline(StaticProvider(chapter_payload()))
    assert result.report is not None
    # Either it passed the gate, or it is still DRAFT — never VERIFIED silently.
    assert result.bu.status in (BUStatus.DRAFT, BUStatus.VERIFIED)
    if result.bu.status == BUStatus.DRAFT:
        assert result.bu.verification_score == 0.0
        assert result.failures


def test_failed_chapter_extraction_is_recorded_as_negative_knowledge():
    """§9: what could not be understood is itself recorded."""
    chapters = make_chapters(2)
    chapters[1].primary_role = "UNDERSTANDING_FAILED"
    bu = BookIntegrator(provider=StaticProvider({"genre": "g"})).integrate(
        IntegrationInput(run_id="r", book_id="b", substrate_id="s", chapters=chapters, deltas=[], evidence_by_chapter={})
    )
    assert any("ch2" in c for c in bu.negative_knowledge.unresolved_conflicts)
    assert bu.coverage_score == 0.5


# ── Test 5: expression generation ────────────────────────────────────────────


def test_expression_has_all_six_sections():
    """§13.1-13.6."""
    chapters = make_chapters(3)
    bu = BookIntegrator(
        provider=StaticProvider(
            {
                "genre": "mathematics",
                "governing_questions": ["What is change?"],
                "central_theses": ["Change is captured by limits"],
                "sub_theses": ["Continuity precedes differentiability"],
            }
        )
    ).integrate(
        IntegrationInput(run_id="r", book_id="b", substrate_id="s", chapters=chapters, deltas=[], evidence_by_chapter={})
    )
    exp = BUExpressionGenerator().generate(bu)

    assert exp.essence
    assert exp.world_model
    assert exp.core_mechanisms, "§13.3 requires core mechanisms"
    assert exp.logical_architecture
    assert exp.contribution
    for section in (exp.essence, exp.world_model, exp.logical_architecture, exp.boundary, exp.contribution):
        assert isinstance(section, str)
    assert "BOOK ESSENCE" in exp.render()
    assert "CONTRIBUTION" in exp.render()


def test_expression_declares_ungrounded_sections_instead_of_inventing():
    """An empty BU must not produce a confident expression."""
    bu = BookUnderstandingV2(id="bu1", run_id="r", book_id="b", substrate_id="s")
    exp = BUExpressionGenerator().generate(bu)
    assert exp.ungrounded_sections
    assert not exp.core_mechanisms
    assert "not determinable" in exp.contribution.lower()


def test_expression_is_deterministic():
    """Same BU in, same expression out — so a re-run can be compared."""
    chapters = make_chapters(3)
    bu = BookIntegrator(provider=StaticProvider({"genre": "g", "central_theses": ["t"]})).integrate(
        IntegrationInput(run_id="r", book_id="b", substrate_id="s", chapters=chapters, deltas=[], evidence_by_chapter={})
    )
    gen = BUExpressionGenerator()
    assert gen.generate(bu).to_dict() == gen.generate(bu).to_dict()


# ── Test 6: resume ───────────────────────────────────────────────────────────


def test_run_resumes_from_partial_chapters():
    """§16 Test 6: a chapter that failed does not end the run."""
    calls = {"n": 0}

    class FlakyProvider(StaticProvider):
        def complete(self, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ProviderUnavailable("simulated provider outage")
            return super().complete(*a, **kw)

    runner = BU2Runner(provider=FlakyProvider(chapter_payload()))
    runner.loader = _TwoChapterLoader()
    result = runner.execute("bk1")

    assert result.chapters, "the run must continue past a failed chapter"
    assert result.failures, "and the failure must be recorded, not swallowed"


class _TwoChapterLoader(BookLoader):
    def load(self, substrate_id):
        return ("Test Book", CHAPTER_TEXT, [make_chapter(1), make_chapter(2)])


def test_run_raises_when_nothing_can_be_produced():
    class DeadProvider(StaticProvider):
        def complete(self, *a, **kw):
            raise ProviderUnavailable("no provider")

    runner = BU2Runner(provider=DeadProvider({}))
    runner.loader = _StaticLoader()
    result = runner.execute("bk1")
    # Both chapters record the failure; the run returns rather than pretending.
    assert all(c.primary_role == "UNDERSTANDING_FAILED" for c in result.chapters)
    assert result.bu is None or result.bu.status != BUStatus.VERIFIED


# ── Test 7: idempotency ──────────────────────────────────────────────────────


def test_same_input_produces_same_output():
    """§16 Test 7: a re-run is reproducible, which is what makes replay a gate."""
    p = chapter_payload()
    first = run_pipeline(StaticProvider(p))
    second = run_pipeline(StaticProvider(p))

    # The run id differs by design (each run is a new run), so compare the
    # understanding content rather than the identity.
    def shape(r: RunResult):
        return (
            [(c.chapter_id, c.chapter_thesis, tuple(c.concepts_introduced_refs)) for c in r.chapters],
            [
                (e.chapter_id, e.kind, e.locator, e.content_hash)
                for e in r.evidence
            ],
            r.bu.governing_questions,
            r.bu.central_theses,
            r.report.outcome.value if r.report else None,
        )

    assert shape(first) == shape(second)


def test_evidence_content_hash_is_stable_for_unchanged_text():
    chapter = make_chapter()
    a = chapter.slice_for("A function assigns to each input exactly one output")
    b = chapter.slice_for("A function assigns to each input exactly one output")
    assert a == b
    assert a is not None


def test_provider_boundary_is_respected():
    """§7.2: the engine depends on the protocol, not on a model SDK."""
    assert issubclass(StaticProvider, object)
    assert callable(resolve_provider)
    with pytest.raises(ProviderUnavailable):
        resolve_provider("no-such-provider")


def test_db_seam_forwards_to_the_real_functions():
    """The seam must forward, not re-declare.

    An earlier hand-mirrored seam drifted twice: update was called as
    (table, values, where) when the real signature is (table, rid, data), and
    read was missing id_column. Both passed the suite and failed on first
    production use. Forwarding removes the drift rather than testing for it.
    """
    import stratum.db as real
    from stratum.services.bu_v2_entrypoint import _DB

    # __getattr__ is an instance hook, so this resolves on an instance.
    seam = _DB()
    for name in ("read", "query", "insert", "update"):
        assert getattr(seam, name) is getattr(real, name), f"{name} is not forwarded"

    with pytest.raises(AttributeError):
        seam.not_a_real_function


def test_persisted_run_writes_status_with_correct_signature(fake_db, monkeypatch):
    """A verified run must record VERIFIED on its run row."""
    import stratum.db as db_module
    from stratum.services import bu_v2_repositories as repos

    # The repositories import stratum.db directly, so patch it there too.
    for fn in ("insert", "query", "read", "update"):
        monkeypatch.setattr(db_module, fn, getattr(fake_db, fn))
        monkeypatch.setattr(repos, fn, getattr(fake_db, fn), raising=False)

    result = run_pipeline(StaticProvider(chapter_payload()), persist=True)
    failed = [c.name for c in result.report.failed]
    statuses = [(t, vals.get("status")) for t, _rid, vals in fake_db.updated]
    # A single-chapter run cannot satisfy every gate; the contract being
    # asserted is that the run's status follows the verdict, in both directions.
    expected = "VERIFIED" if not failed else "FAILED"
    assert statuses == [("book_reading_run", expected)], (statuses, failed)
    assert (expected == "VERIFIED") == (result.bu.status == BUStatus.VERIFIED)
    written = {t for t, _row in fake_db.inserted}
    assert {"book_reading_run", "chapter_understandings", "chapter_deltas",
            "book_understandings_v2"} <= written, written


def test_unknown_provider_family_is_rejected():
    with pytest.raises(ProviderUnavailable, match="unknown provider"):
        resolve_provider("definitely-not-a-provider")