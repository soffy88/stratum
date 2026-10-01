"""A Repository P5 — KU lifecycle evolution.

Contract tests for the evolution service (migration 075):
- schema: four tables, closed vocabularies, no ALTER/DROP/backfill
- lifecycle: the status is the fold of the review log, never a column
- immutability: no unit row changes, none is deleted, nothing is updatable
- revision: a successor is appended, the prior row is untouched
- replay: the same inputs append nothing the second time
- authority: nothing outside the A chain, and no semantic merge
- durability: a crash between two lifecycle writes leaves nothing behind
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

import pytest


ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "075_a_ku_evolution.sql"
P44_MIGRATION = MIGRATIONS / "074_a_ku_freeze_persistence.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_ku_evolution.json"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.evolution import (  # noqa: E402
    DECLARED_RELATION_TYPES,
    EVOLUTION_VERSION,
    LEGAL_LIFECYCLE_TRANSITIONS,
    NON_TRANSITIONING_REVIEWS,
    ConfidenceBasis,
    EvolutionPrecondition,
    EvolutionSink,
    EvolutionViolation,
    KULifecycleStatus,
    KUEvolutionService,
    RelationType,
    ReviewType,
    observation_hash,
    observation_id,
    relation_hash,
    relation_id,
    review_id,
    revision_hash,
    revision_id,
)
from stratum.knowledge.a_repository.persistence import (  # noqa: E402
    EventType,
    PersistenceStatus,
)
from stratum.knowledge.a_repository.ku_evolution_runner import (  # noqa: E402
    ALLOWED_REFERENCES,
    CREATED_TABLES,
    GATE_ORDER,
    REQUIRED_CHAIN,
    REQUIRED_MIGRATION,
    _append_revised_unit,
    _fingerprint,
    _unit_id_by_key,
    apply_revisions,
    apply_reviews,
    artifact,
    authority_gate,
    build_evolution,
    build_persisted,
    durability_gate,
    evidence_gate,
    gate_results,
    idempotency_gate,
    immutability_gate,
    report,
    replay_gate,
    revision_gate,
    schema_gate,
    traceability_gate,
    unit_snapshot,
    write_sql,
)


@pytest.fixture(scope="module")
def evolved():
    """A settled P5 run, shared by the read-only assertions.

    Tests that deliberately corrupt a row build their own instance through
    `_fresh()` instead: a shared fixture that one test can leave broken
    turns every later failure into a false alarm.
    """
    result = build_evolution()
    return {"result": result, "evolution": result["evolution"],
            "upstream": result["result"], "sink": result["evolution"].sink,
            "unit_ids": result["unit_ids"], "before": result["before_snapshot"],
            "report": report(result)}


def _fresh() -> Dict:
    """A private, mutable P5 run for a test that has to break something."""
    return build_evolution()


def _foreign_evidence(result: Dict) -> str:
    """Add a second book and return one of its evidence ids.

    Needed to test the "a review must cite its own book" rule: the pilot
    corpus is one book, so without a second source version the rule has
    nothing to refuse.
    """
    upstream = result["result"]
    pipeline = upstream["base"]["pipeline"]
    source = pipeline.register("另一本书", author="nobody")
    version = pipeline.snapshot(source.id, "PDF-v1", "file-hash-other-book",
                                fmt="PDF", page_count=1)
    run = pipeline.create_reading_run(version.id)
    evidence = pipeline.extract_evidence(run.id, version.id, 1,
                                         {"logical_locator": "p1"},
                                         "另一个来源的跨度", "p1-v1")
    return evidence.id


def _prior_id(evolved) -> str:
    return evolved["result"]["revisions"][0]["prior_unit_id"]


def _revised_id(evolved) -> str:
    return evolved["result"]["revisions"][0]["revised_unit_id"]


# ── schema ───────────────────────────────────────────────────────────────────

def test_075_creates_exactly_the_four_lifecycle_tables():
    sql = MIGRATION.read_text(encoding="utf-8")
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                             re.sub(r"--.*", "", sql)))
    assert created == set(CREATED_TABLES)


def test_075_is_additive_only():
    sql = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "ALTER TABLE" not in sql
    assert "DROP " not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE " not in sql


def test_075_recreates_nothing_it_inherits():
    sql = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    for inherited in ("knowledge_unit", "ku_freeze_event", "ku_candidate",
                      "ku_verification", "reading_evidence", "source_version",
                      "reading_run"):
        assert f"CREATE TABLE IF NOT EXISTS stratum.{inherited} (" not in sql


def test_075_references_only_knowledge_unit_and_evidence():
    sql = MIGRATION.read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", sql))
    assert referenced == ALLOWED_REFERENCES


def test_075_every_foreign_key_restricts():
    sql = MIGRATION.read_text(encoding="utf-8")
    foreign_keys = re.findall(r"REFERENCES\s+stratum\.\w+\(id\)\s+"
                              r"ON DELETE (\w+)", sql)
    assert foreign_keys, "075 declares no foreign key at all"
    assert set(foreign_keys) == {"RESTRICT"}


def test_review_cannot_exist_without_evidence():
    sql = MIGRATION.read_text(encoding="utf-8")
    block = sql.split("CREATE TABLE IF NOT EXISTS stratum.ku_review_event")[1]
    block = block.split(");")[0]
    assert "evidence_id TEXT NOT NULL" in block
    assert "REFERENCES stratum.reading_evidence(id) ON DELETE RESTRICT" in block


def test_review_requires_a_non_blank_rationale():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CHECK (length(btrim(rationale)) > 0)" in sql


def test_confidence_is_bounded_by_the_schema_as_well_as_the_service():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert ("CHECK (measured_confidence >= 0.0 "
            "AND measured_confidence <= 1.0)") in sql


def test_a_unit_may_be_superseded_only_once():
    sql = MIGRATION.read_text(encoding="utf-8")
    block = sql.split("CREATE TABLE IF NOT EXISTS stratum.ku_revision")[1]
    block = block.split(");")[0]
    assert "CONSTRAINT ku_revision_prior_uniq UNIQUE (prior_unit_id)" in block
    assert "CONSTRAINT ku_revision_revised_uniq UNIQUE (revised_unit_id)" in block
    assert "CONSTRAINT ku_revision_not_self" in block


def test_relation_vocabulary_has_no_equivalence_or_merge_value():
    """The vocabulary is the design. A value meaning "these say the same
    thing" would make A仓 the repository that decided a semantic
    judgement, which is B仓's job and not A仓's."""
    sql = MIGRATION.read_text(encoding="utf-8")
    block = sql.split("CREATE TABLE IF NOT EXISTS stratum.ku_relation")[1]
    declared = set(re.findall(r"'([A-Z_]+)'", block.split("CHECK")[1]))
    assert declared == DECLARED_RELATION_TYPES
    for forbidden in ("EQUIVALENT", "SAME_CONCEPT", "DUPLICATE", "MERGED",
                      "CONTRADICTS", "CONFLICTS", "SAME_MEANING",
                      "EQUIVALENT_TO", "CONTRADICTION"):
        assert not any(forbidden in value for value in declared)


def test_relation_vocabulary_matches_the_code():
    assert DECLARED_RELATION_TYPES == {r.value for r in RelationType}


def test_relation_is_canonically_ordered_so_it_is_stored_once():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CONSTRAINT ku_relation_ordered CHECK (from_unit_id < to_unit_id)" \
        in sql


def test_lifecycle_and_review_vocabularies_are_closed():
    sql = MIGRATION.read_text(encoding="utf-8")
    statuses = set(re.findall(r"'(ACTIVE|QUARANTINED|SUPERSEDED)'", sql))
    assert statuses == {s.value for s in KULifecycleStatus}
    review_types = set(re.findall(
        r"'(CONFIRMED|CHALLENGED|QUARANTINED|RELEASED|SUPERSEDED)'", sql))
    assert review_types == {r.value for r in ReviewType}
    bases = set(re.findall(
        r"'(VERIFICATION_SCORE|REVIEW_SIGNAL|EVIDENCE_QUALITY)'", sql))
    assert bases == {b.value for b in ConfidenceBasis}


def test_075_is_additive_over_the_whole_chain():
    chain = "\n".join((MIGRATIONS / name).read_text(encoding="utf-8")
                      for name in REQUIRED_CHAIN)
    assert set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                          chain)) >= set(CREATED_TABLES)


def test_075_names_no_external_authority():
    """Structurally: every `stratum.X` is either a table 075 creates or a
    permitted reference target, so it cannot reach another repository."""
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    named = set(re.findall(r"stratum\.(\w+)", statements))
    assert named <= CREATED_TABLES | ALLOWED_REFERENCES


def test_075_performs_no_merge_dedup_or_promotion():
    source = (ROOT / "src" / "stratum" / "knowledge" / "a_repository"
              / "evolution.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    for foreign in ("INSERT INTO bu", "UPDATE stratum.bu", "concept",
                    "ku_onto", "chapter_bu"):
        assert foreign not in code


def test_074_superseded_is_now_emitted(evolved):
    """074 defined SUPERSEDED and P4.1 emitted nothing. P5 is the stage
    that fills it in, which is what its own comment reserved it for."""
    sql = P44_MIGRATION.read_text(encoding="utf-8")
    assert "'SUPERSEDED'" in sql
    assert "reserved for a later stage" in sql
    events = [e for e in evolved["sink"].events.values()
              if e.event_type == EventType.SUPERSEDED.value]
    assert len(events) == 1
    assert events[0].knowledge_unit_id == _prior_id(evolved)


def test_the_supersede_event_reports_frozen_to_frozen(evolved):
    """074 restricts to_status to FREEZE_PENDING/FROZEN/FAILED. A
    supersession does not un-freeze anything — the unit is still frozen and
    still citable — it only stops being current, so both endpoints are
    FROZEN and the event type carries the meaning."""
    event = next(e for e in evolved["sink"].events.values()
                 if e.event_type == EventType.SUPERSEDED.value)
    assert event.from_status == PersistenceStatus.FROZEN.value
    assert event.to_status == PersistenceStatus.FROZEN.value


def test_earlier_migrations_are_untouched_by_this_stage():
    for name in REQUIRED_CHAIN[:-1]:
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in CREATED_TABLES:
            assert f"stratum.{table}" not in sql


def test_p4_and_p4_1_logic_are_untouched():
    from stratum.knowledge.a_repository import freeze, persistence
    assert freeze.FREEZE_VERSION == "a-p4-v0.1"
    assert persistence.PERSISTENCE_VERSION == "a-p4-1-v0.1"
    assert persistence.IMPLEMENTED_EVENT_TYPES == (EventType.FROZEN,)


# ── GATE_1 traceability ──────────────────────────────────────────────────────

def test_every_unit_resolves_to_a_book(evolved):
    trace = evolved["evolution"].traceability()
    assert trace["units"] == len(evolved["sink"].units)
    assert trace["trace_complete"] == trace["units"]
    assert trace["percent"] == 100.0


def test_every_review_resolves_to_a_book(evolved):
    trace = evolved["evolution"].traceability()
    assert trace["reviews"] == evolved["evolution"].review_count()
    assert trace["review_percent"] == 100.0


def test_the_revised_unit_is_traceable_like_any_other(evolved):
    """A revision must not be a second-class row: it resolves through the
    same chain, and the prior unit's chain is untouched."""
    evolution = evolved["evolution"]
    for unit_id in (_prior_id(evolved), _revised_id(evolved)):
        traceable, failed = evolution._require_traceable(
            evolution.sink.units[unit_id])
        assert traceable, failed


def test_no_lifecycle_row_orphans(evolved):
    evolution = evolved["evolution"]
    assert evolution.orphan_revisions() == []
    assert evolution.orphan_reviews() == []
    assert evolution.orphan_observations() == []
    assert evolution.orphan_relations() == []


def test_traceability_gate_passes(evolved):
    assert traceability_gate(evolved["result"]) == "PASS"


def test_traceability_fails_when_a_review_cites_a_missing_evidence():
    result = _fresh()
    review = next(iter(result["evolution"].sink.reviews.values()))
    review.evidence_id = "ev_does_not_exist"
    assert traceability_gate(result) == "FAIL"


# ── GATE_2 immutability ──────────────────────────────────────────────────────

def test_no_prior_unit_row_changed(evolved):
    after = unit_snapshot(evolved["sink"])
    for unit_id, row in evolved["before"].items():
        assert after[unit_id] == row


def test_no_prior_unit_row_was_deleted(evolved):
    for unit_id in evolved["before"]:
        assert unit_id in evolved["sink"].units


def test_the_superseded_unit_keeps_its_own_text(evolved):
    """The prior unit still says what it always said. The correction lives
    in a successor, so anything that already cited the prior still resolves
    to the text it cited."""
    evolution = evolved["evolution"]
    prior = evolution.sink.units[_prior_id(evolved)]
    revised = evolution.sink.units[_revised_id(evolved)]
    assert prior.statement != revised.statement
    assert prior.canonical_text != revised.canonical_text
    assert prior.statement == "《汉谟拉比法典》（约前1800年）是最早的成文信贷法典之一"
    assert prior.canonical_text == "第一部已知最早的正式法典"


def test_the_superseded_unit_is_still_frozen(evolved):
    prior = evolved["sink"].units[_prior_id(evolved)]
    assert prior.freeze_status == PersistenceStatus.FROZEN.value


def test_a_unit_cannot_be_updated(evolved):
    with pytest.raises(EvolutionViolation):
        evolved["evolution"].update_unit(_prior_id(evolved), statement="new")


def test_a_status_cannot_be_assigned(evolved):
    with pytest.raises(EvolutionViolation, match="fold"):
        evolved["evolution"].set_status(_prior_id(evolved), "ACTIVE")


def test_nothing_in_the_lifecycle_can_be_deleted(evolved):
    evolution = evolved["evolution"]
    sink = evolved["sink"]
    for method, argument in (
            ("delete_unit", next(iter(sink.units))),
            ("delete_revision", next(iter(sink.revisions))),
            ("delete_review", next(iter(sink.reviews))),
            ("delete_observation", next(iter(sink.observations))),
            ("delete_relation", next(iter(sink.relations)))):
        with pytest.raises(EvolutionViolation):
            getattr(evolution, method)(argument)


def test_a_unit_cannot_be_superseded_by_declaration(evolved):
    with pytest.raises(EvolutionViolation, match="appending a revision"):
        evolved["evolution"].supersede(_revised_id(evolved))


def test_immutability_gate_passes(evolved):
    assert immutability_gate(evolved["result"],
                             evolved["before"]) == "PASS"


def test_immutability_gate_catches_a_changed_row():
    result = _fresh()
    unit_id = result["revisions"][0]["prior_unit_id"]
    result["evolution"].sink.units[unit_id].statement = "rewritten"
    assert immutability_gate(result, result["before_snapshot"]) == "FAIL"


def test_immutability_gate_catches_a_deleted_row():
    result = _fresh()
    del result["evolution"].sink.units[
        result["revisions"][0]["prior_unit_id"]]
    assert immutability_gate(result, result["before_snapshot"]) == "FAIL"


# ── GATE_3 revision ──────────────────────────────────────────────────────────

def test_a_revision_appends_a_new_unit(evolved):
    sink = evolved["sink"]
    assert len(sink.units) == len(evolved["before"]) + 1
    assert _revised_id(evolved) not in evolved["before"]


def test_the_successor_has_its_own_candidate_and_verification(evolved):
    sink = evolved["sink"]
    prior = sink.units[_prior_id(evolved)]
    revised = sink.units[_revised_id(evolved)]
    assert prior.candidate_id != revised.candidate_id
    assert prior.verification_id != revised.verification_id


def test_a_revision_is_appended_and_never_merged(evolved):
    evolution = evolved["evolution"]
    with pytest.raises(EvolutionViolation, match="merge"):
        evolution.merge_units(_prior_id(evolved), _revised_id(evolved))


def test_a_revision_chain_never_branches(evolved):
    """UNIQUE(prior_unit_id) gives one successor only."""
    evolution = evolved["evolution"]
    other = next(uid for uid in evolved["sink"].units
                 if uid not in (_prior_id(evolved), _revised_id(evolved)))
    ok, failed = evolution.check_revision_preconditions(
        _prior_id(evolved), other, "a second successor")
    assert not ok
    assert "PRIOR_ALREADY_SUPERSEDED" in failed


def test_a_unit_cannot_revise_itself(evolved):
    evolution = evolved["evolution"]
    ok, failed = evolution.check_revision_preconditions(
        _prior_id(evolved), _prior_id(evolved), "self")
    assert not ok
    assert "SELF_REVISION" in failed


def test_a_revision_needs_a_basis(evolved):
    evolution = evolved["evolution"]
    other = next(uid for uid in evolved["sink"].units
                 if uid not in (_prior_id(evolved), _revised_id(evolved)))
    ok, failed = evolution.check_revision_preconditions(
        _prior_id(evolved), other, "   ")
    assert not ok
    assert "NO_REVISION_BASIS" in failed


def test_a_revision_cannot_cross_source_versions(evolved):
    """A revision corrects a unit against its own book. A successor from a
    different source version is a different proposition, and calling that a
    revision would silently re-source a citation."""
    evolution = evolved["evolution"]
    foreign = dict(evolution.sink.units[_revised_id(evolved)].__dict__)
    foreign["id"] = "ku_ffffffffffff"
    foreign["source_version_id"] = "sv_some_other_book"
    evolution.sink.units[foreign["id"]] = type(
        evolution.sink.units[_revised_id(evolved)])(**foreign)
    try:
        ok, failed = evolution.check_revision_preconditions(
            _prior_id(evolved), foreign["id"], "cross-book revision")
        assert not ok
        assert "REVISION_CROSSES_SOURCE_VERSION" in failed
    finally:
        del evolution.sink.units[foreign["id"]]


def test_the_revision_is_recorded_with_its_index_and_hash(evolved):
    revision = next(iter(evolved["sink"].revisions.values()))
    assert revision.revision_index == 1
    assert revision.revision_hash == revision_hash(
        revision.prior_unit_id, revision.revised_unit_id,
        revision.revision_basis, revision.revision_index)
    assert revision.id == revision_id(revision.prior_unit_id,
                                      revision.revised_unit_id)


def test_the_prior_unit_folds_to_superseded_and_the_successor_stays_active(
        evolved):
    evolution = evolved["evolution"]
    assert evolution.status_of(_prior_id(evolved)) == \
        KULifecycleStatus.SUPERSEDED.value
    assert evolution.status_of(_revised_id(evolved)) == \
        KULifecycleStatus.ACTIVE.value


def test_revision_gate_passes(evolved):
    assert revision_gate(evolved["result"]) == "PASS"


# ── status lifecycle ─────────────────────────────────────────────────────────

def test_a_frozen_unit_is_active_until_a_review_says_otherwise(evolved):
    evolution = evolved["evolution"]
    untouched = next(uid for uid in evolved["sink"].units
                     if uid not in (_prior_id(evolved), _revised_id(evolved))
                     and not evolution.history(uid))
    assert evolution.status_of(untouched) == KULifecycleStatus.ACTIVE.value


def test_quarantine_then_release_returns_a_unit_to_active(evolved):
    unit_id = next(v["unit_id"] for v in evolved["result"]["reviews"]
                   if v["key"] == "rv_athens_released")
    history = [r.review_type for r in evolved["evolution"].history(unit_id)]
    assert history == ["QUARANTINED", "RELEASED"]
    assert evolved["evolution"].status_of(unit_id) == \
        KULifecycleStatus.ACTIVE.value
    # Both steps stay on the record: the quarantine is not erased by the
    # release.
    assert len(evolved["evolution"].history(unit_id)) == 2


def test_a_superseded_unit_is_terminal():
    assert LEGAL_LIFECYCLE_TRANSITIONS[KULifecycleStatus.SUPERSEDED] == \
        frozenset()


def test_a_superseded_unit_cannot_be_reviewed_again(evolved):
    evolution = evolved["evolution"]
    ok, failed = evolution.check_review_preconditions(
        _prior_id(evolved), "ev_anything", )
    assert not ok
    assert "UNIT_ALREADY_SUPERSEDED" in failed


def test_a_review_moves_the_fold_and_never_the_row():
    result = _fresh()
    evolution = result["evolution"]
    unit_id = result["reviews"][0]["unit_id"]
    before = dict(vars(evolution.sink.units[unit_id]))
    apply_reviews(result["result"], evolution, result["unit_ids"])
    assert dict(vars(evolution.sink.units[unit_id])) == before
    assert evolution.history(unit_id)


def test_a_signal_review_leaves_the_status_alone(evolved):
    """CONFIRMED and CHALLENGED record a finding without moving the unit."""
    evolution = evolved["evolution"]
    challenged = next(v["unit_id"] for v in evolved["result"]["reviews"]
                      if v["review_type"] == "CHALLENGED")
    assert evolution.status_of(challenged) == KULifecycleStatus.ACTIVE.value
    review = evolution.history(challenged)[0]
    assert review.from_status == review.to_status
    assert ReviewType.CHALLENGED.value in NON_TRANSITIONING_REVIEWS


def test_a_review_without_a_rationale_is_refused(evolved):
    evolution = evolved["evolution"]
    unit_id = evolved["result"]["reviews"][0]["unit_id"]
    with pytest.raises(EvolutionPrecondition, match="opinion"):
        evolution.review(unit_id, "CONFIRMED", "   ", "ev_anything")


def test_a_review_citing_another_books_evidence_is_refused():
    """A review of a unit from book X must cite book X. Anything else is a
    review of a different book that happens to name this unit."""
    result = _fresh()
    evolution = result["evolution"]
    unit_id = result["reviews"][0]["unit_id"]
    foreign = _foreign_evidence(result)
    ok, failed = evolution.check_review_preconditions(unit_id, foreign)
    assert not ok
    assert "EVIDENCE_FROM_OTHER_SOURCE" in failed
    with pytest.raises(EvolutionPrecondition):
        evolution.review(unit_id, "CONFIRMED", "依据另一本书", foreign)


def evidence_source(evolution, evidence) -> str:
    run = evolution.store.reading_runs[evidence.reading_run_id]
    return run.source_version_id


def test_a_review_of_an_unknown_unit_is_refused(evolved):
    ok, failed = evolved["evolution"].check_review_preconditions(
        "ku_nope", "ev_nope")
    assert not ok
    assert failed == ["NO_SUCH_UNIT"]


def test_the_review_ledger_is_frozen_in_the_corpus():
    """A lifecycle whose inputs live in the service is a lifecycle nobody
    can replay, so the reviews are data like the candidates are."""
    assert len(C.KU_REVIEWS) == 4
    for entry in C.KU_REVIEWS:
        assert entry["review_type"] in {r.value for r in ReviewType}
        assert entry["rationale"].strip()
        assert entry["evidence_key"] in {e["key"] for e in C.EVIDENCE}
        assert entry["unit_key"] in {c["key"] for c in C.KU_CANDIDATES}


def test_every_reviewed_unit_was_actually_frozen(evolved):
    for entry in C.KU_REVIEWS:
        unit_id = evolved["unit_ids"][entry["unit_key"]]
        assert unit_id in evolved["sink"].units
        assert evolved["sink"].units[unit_id].freeze_status == "FROZEN"


# ── confidence evolution ─────────────────────────────────────────────────────

def test_confidence_only_ever_appends(evolved):
    evolution = evolved["evolution"]
    unit_id = evolved["unit_ids"]["kc_athens_debt_crisis"]
    series = evolution.confidence_series(unit_id)
    assert [o.sequence for o in series] == [1, 2, 3]
    assert [o.basis for o in series] == ["VERIFICATION_SCORE",
                                         "REVIEW_SIGNAL", "REVIEW_SIGNAL"]


def test_a_lowered_measurement_stays_on_the_record(evolved):
    """The observation that lowered a unit is still there beside the ones
    that raised it. Nothing overwrites a measurement."""
    values = [o.measured_confidence for o in
              evolved["evolution"].confidence_series(
                  evolved["unit_ids"]["kc_athens_debt_crisis"])]
    assert values == [1.0, 0.55, 0.9]
    assert min(values) < max(values)


def test_confidence_outside_the_unit_interval_is_refused(evolved):
    evolution = evolved["evolution"]
    unit_id = evolved["unit_ids"]["kc_rome_rate_cap"]
    with pytest.raises(EvolutionPrecondition, match=r"\[0, 1\]"):
        evolution.observe_confidence(unit_id, "REVIEW_SIGNAL", 4.0)


def test_confidence_never_moves_a_unit_on_its_own():
    """A measurement is not a decision: only a review moves a unit."""
    result = _fresh()
    evolution = result["evolution"]
    unit_id = next(v["unit_id"] for v in result["reviews"]
                   if v["key"] == "rv_rome_rate_cap_confirmed")
    before = evolution.status_of(unit_id)
    evolution.observe_confidence(unit_id, "REVIEW_SIGNAL", 0.01)
    assert evolution.status_of(unit_id) == before


def test_an_observation_is_content_addressed(evolved):
    row = next(iter(evolved["sink"].observations.values()))
    assert row.id == observation_id(row.knowledge_unit_id, row.sequence,
                                    row.basis, row.measured_confidence)
    assert row.observation_hash == observation_hash(
        row.knowledge_unit_id, row.sequence, row.basis, row.measured_confidence)


def test_the_revised_unit_records_both_its_admission_and_its_revision(
        evolved):
    series = evolved["evolution"].confidence_series(_revised_id(evolved))
    assert [o.basis for o in series] == ["VERIFICATION_SCORE",
                                         "REVIEW_SIGNAL"]


# ── relation metadata ────────────────────────────────────────────────────────

def test_relations_are_derived_from_rows_not_declared(evolved):
    """A caller cannot assert that two units are related; it can only ask
    what two rows already show."""
    derived = evolved["evolution"].derive_run_relations()
    assert {r.relation_type for r in derived} == {"SHARES_EVIDENCE"}


def test_the_only_relation_types_written_are_factual(evolved):
    assert {r.relation_type for r in evolved["sink"].relations.values()} == {
        "REVISES", "SHARES_EVIDENCE"}


def test_a_revision_records_that_it_revises(evolved):
    """The pair is stored in canonical id order, so the side that happens to
    sort first is not the side that was revised — only the pair is a fact."""
    relation = next(r for r in evolved["sink"].relations.values()
                    if r.relation_type == "REVISES")
    assert {relation.from_unit_id, relation.to_unit_id} == {
        _prior_id(evolved), _revised_id(evolved)}
    assert relation.from_unit_id < relation.to_unit_id


def test_a_relation_is_stored_once_however_the_pair_is_ordered(evolved):
    prior, revised = _prior_id(evolved), _revised_id(evolved)
    assert relation_id(prior, revised, "REVISES") == \
        relation_id(revised, prior, "REVISES")
    assert relation_hash(prior, revised, "REVISES") == \
        relation_hash(revised, prior, "REVISES")


def test_the_code_and_the_schema_declare_the_same_relation_vocabulary():
    """One closed vocabulary, declared once. A value the code emits and the
    schema rejects would only surface as a failed transaction at write
    time."""
    sql = MIGRATION.read_text(encoding="utf-8")
    block = sql.split("CREATE TABLE IF NOT EXISTS stratum.ku_relation")[1]
    declared = set(re.findall(r"'([A-Z_]+)'", block.split("CHECK")[1]))
    assert declared == DECLARED_RELATION_TYPES
    assert declared == {r.value for r in RelationType}


def test_a_relation_to_a_non_durable_unit_is_refused(evolved):
    evolution = evolved["evolution"]
    with pytest.raises(EvolutionPrecondition, match="durable"):
        evolution.relate(_prior_id(evolved), "ku_not_durable", "SHARES_EVIDENCE")


def test_a_unit_is_not_related_to_itself(evolved):
    with pytest.raises(EvolutionPrecondition, match="two units"):
        evolved["evolution"].relate(_prior_id(evolved), _prior_id(evolved),
                                    "SHARES_EVIDENCE")


def test_an_undeclared_relation_type_cannot_be_recorded(evolved):
    """There is no parameter for a judgement, so the vocabulary is the only
    door — and the schema closes it as well."""
    with pytest.raises(ValueError):
        evolved["evolution"].relate(_prior_id(evolved), _revised_id(evolved),
                                    "EQUIVALENT_TO")


def test_dedup_is_refused(evolved):
    """Deciding two units say the same thing is a semantic judgement and
    belongs to B仓, which A仓 has no authority over."""
    with pytest.raises(EvolutionViolation, match="deduplicate"):
        evolved["evolution"].dedupe_units(_prior_id(evolved),
                                          _revised_id(evolved))


def test_relations_carry_no_merge_or_concept_authority(evolved):
    relations = list(evolved["sink"].relations.values())
    assert relations, "the pilot derives no relation at all"
    for relation in relations:
        assert relation.relation_type in DECLARED_RELATION_TYPES
        assert relation.from_unit_id < relation.to_unit_id


# ── GATE_4 replay ────────────────────────────────────────────────────────────

def test_the_same_inputs_produce_the_same_ids():
    replay = replay_gate()
    assert replay["identical_fingerprints"] == 1
    assert replay["same_revision_ids"]
    assert replay["same_review_ids"]
    assert replay["stable_unit_ids"]


def test_no_duplicate_rows_after_replay():
    replay = replay_gate()
    assert replay["no_duplicate_revisions"]
    assert replay["no_duplicate_reviews"]
    assert replay["no_duplicate_relations"]


def test_every_id_is_content_derived(evolved):
    """Never uuid4, never a sequence, never a timestamp: the same inputs
    must always produce the same ids."""
    for row in evolved["sink"].revisions.values():
        assert row.id == revision_id(row.prior_unit_id, row.revised_unit_id)
    for row in evolved["sink"].reviews.values():
        assert row.id == review_id(row.knowledge_unit_id, row.sequence,
                                   row.review_type)
    for row in evolved["sink"].observations.values():
        assert row.id == observation_id(row.knowledge_unit_id, row.sequence,
                                        row.basis, row.measured_confidence)
    for row in evolved["sink"].relations.values():
        assert row.id == relation_id(row.from_unit_id, row.to_unit_id,
                                     row.relation_type)


def test_replaying_the_review_ledger_appends_nothing():
    result = build_evolution()
    evolution, before = result["evolution"], _fingerprint(result["evolution"])
    apply_reviews(result["result"], evolution, result["unit_ids"])
    assert _fingerprint(evolution) == before


def test_replaying_a_revision_appends_nothing():
    result = build_evolution()
    evolution, before = result["evolution"], _fingerprint(result["evolution"])
    apply_revisions(result["result"], evolution, result["unit_ids"])
    assert _fingerprint(evolution) == before


def test_replaying_the_baseline_confidence_sweep_appends_nothing():
    result = build_evolution()
    evolution, before = result["evolution"], _fingerprint(result["evolution"])
    evolution.record_baseline_confidence()
    assert _fingerprint(evolution) == before


def test_replaying_the_derived_relations_appends_nothing():
    result = build_evolution()
    evolution, before = result["evolution"], _fingerprint(result["evolution"])
    evolution.record_derived_relations()
    assert _fingerprint(evolution) == before


def test_idempotency_gate_passes(evolved):
    assert idempotency_gate(evolved["result"]) == "PASS"


def test_a_second_process_reproduces_the_same_lifecycle():
    first = _fingerprint(build_evolution()["evolution"])
    second = _fingerprint(build_evolution()["evolution"])
    assert first == second


# ── GATE_5 authority ─────────────────────────────────────────────────────────

def test_every_review_cites_real_evidence_from_the_units_book(evolved):
    evolution = evolved["evolution"]
    for review in evolution.sink.reviews.values():
        evidence = evolution.store.evidence[review.evidence_id]
        unit = evolution.sink.units[review.knowledge_unit_id]
        assert evidence_source(evolution, evidence) == unit.source_version_id


def test_no_unit_is_written_without_its_evidence_chain(evolved):
    evolution = evolved["evolution"]
    for unit in evolution.sink.units.values():
        assert unit.canonical_text
        assert evolution._require_traceable(unit)[0]


def test_a_revision_basis_cannot_be_blank(evolved):
    for revision in evolved["sink"].revisions.values():
        assert revision.revision_basis.strip()


def test_evidence_gate_passes(evolved):
    assert evidence_gate(evolved["result"]) == "PASS"


def test_evidence_gate_fails_on_an_evidence_less_review():
    result = _fresh()
    evolution = result["evolution"]
    review = next(r for r in evolution.sink.reviews.values()
                  if r.review_type == "CHALLENGED")
    review.evidence_id = "ev_gone"
    assert evidence_gate(result) == "FAIL"


def test_evidence_gate_fails_on_an_unanchored_unit():
    result = _fresh()
    evolution = result["evolution"]
    unit_id = result["revisions"][0]["revised_unit_id"]
    evolution.sink.units[unit_id].canonical_text = ""
    assert evidence_gate(result) == "FAIL"


def test_authority_gate_passes():
    assert authority_gate() == "PASS"


def test_authority_gate_is_not_a_forbidden_name_list():
    """Checked by inspecting what the migration names, not by matching
    names — a list inside the gate would contain what it forbids."""
    source = (ROOT / "src" / "stratum" / "knowledge" / "a_repository"
              / "ku_evolution_runner.py").read_text(encoding="utf-8")
    assert "FORBIDDEN" not in source


def test_the_service_reaches_no_other_repository():
    statements = re.sub(r"--.*", "",
                        MIGRATION.read_text(encoding="utf-8"))
    named = set(re.findall(r"stratum\.(\w+)", statements))
    assert named <= CREATED_TABLES | ALLOWED_REFERENCES


def test_bu2_and_b_are_untouched():
    for name in ("063_bu2_p4_p5_chapter_and_bu.sql",
                 "064_bu2_p6_p8_p9_verification_learning.sql",
                 "065_bu2_pipeline_state.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in CREATED_TABLES:
            assert table not in sql


# ── GATE_6 durability ────────────────────────────────────────────────────────

def test_a_crash_between_lifecycle_writes_leaves_nothing():
    """Every write index of a revision is exercised: the revision, the
    review, the SUPERSEDED event, and the observations and relations."""
    entry = sorted(C.KU_REVISIONS, key=lambda e: e["key"])[0]
    for fail_after in range(1, 6):
        crashed = build_persisted()
        evolution = KUEvolutionService(crashed["base"]["pipeline"],
                                       crashed["quality"],
                                       crashed["verification"],
                                       crashed["freeze"],
                                       crashed["writer"],
                                       crashed["sink"])
        unit_ids = _unit_id_by_key(crashed)
        prior_id = unit_ids[entry["prior_unit_key"]]
        appended = _append_revised_unit(crashed, entry, prior_id)
        evolution.record_baseline_confidence()
        before = unit_snapshot(crashed["sink"])
        crashed["sink"].fail_after = fail_after
        outcome = evolution.link_revision(prior_id, appended["unit_id"],
                                          entry["basis"])
        assert outcome.status == "FAILED"
        assert crashed["sink"].revisions == {}
        assert crashed["sink"].reviews == {}
        assert crashed["sink"].relations == {}
        assert crashed["sink"].rollbacks >= 1
        # The unit rows the failed attempt was building on are unchanged, and
        # the unit it would have retired is still active.
        assert unit_snapshot(crashed["sink"]) == before
        assert evolution.status_of(prior_id) == KULifecycleStatus.ACTIVE.value


def test_a_restart_reads_back_the_same_rows():
    assert durability_gate() == "PASS"


def test_the_sink_is_transactional_over_six_tables():
    sink = EvolutionSink()
    assert sink.commits == 0 and sink.rollbacks == 0
    sink.commit([
        ("knowledge_unit", {"id": "ku_x", "candidate_id": "kc_x",
                            "verification_id": "kv_x",
                            "source_version_id": "sv_x",
                            "content_hash": "ch_x", "statement": "s",
                            "canonical_text": "c", "verification_score": 1.0,
                            "freeze_status": "FROZEN", "title": "t",
                            "evidence_count": 1}),
        ("ku_freeze_event", {"id": "kfe_x", "knowledge_unit_id": "ku_x",
                             "event_type": "SUPERSEDED",
                             "from_status": "FROZEN", "to_status": "FROZEN",
                             "event_hash": "keh_x"}),
        ("ku_revision", {"id": "krv_x", "prior_unit_id": "ku_x",
                         "revised_unit_id": "ku_y", "revision_index": 1,
                         "revision_basis": "b", "revision_hash": "kvh_x"}),
        ("ku_review_event", {"id": "kre_x", "knowledge_unit_id": "ku_x",
                             "review_type": "CONFIRMED",
                             "from_status": "ACTIVE", "to_status": "ACTIVE",
                             "rationale": "r", "evidence_id": "ev_x",
                             "review_hash": "krh_x", "sequence": 1}),
        ("ku_confidence_evolution",
         {"id": "kcx_x", "knowledge_unit_id": "ku_x", "sequence": 1,
          "measured_confidence": 0.5, "basis": "REVIEW_SIGNAL",
          "observation_hash": "kxh_x"}),
        ("ku_relation", {"id": "krl_x", "from_unit_id": "ku_x",
                         "to_unit_id": "ku_y", "relation_type": "REVISES",
                         "relation_hash": "krhh_x"})])
    assert sink.commits == 1
    assert len(sink.units) == len(sink.events) == 1
    assert len(sink.revisions) == len(sink.reviews) == 1
    assert len(sink.observations) == len(sink.relations) == 1


def test_the_sink_refuses_a_table_outside_the_lifecycle():
    sink = EvolutionSink()
    with pytest.raises(EvolutionViolation):
        sink.commit([("bu_chapter", {"id": "x"})])


def test_the_sink_discards_a_partial_transaction():
    sink = EvolutionSink(fail_after=2)
    with pytest.raises(RuntimeError):
        sink.commit([("ku_revision", {"id": "krv_x", "prior_unit_id": "a",
                                      "revised_unit_id": "b",
                                      "revision_index": 1,
                                      "revision_basis": "r",
                                      "revision_hash": "h"}),
                     ("ku_review_event", {"id": "kre_x",
                                          "knowledge_unit_id": "a",
                                          "review_type": "CONFIRMED",
                                          "from_status": "ACTIVE",
                                          "to_status": "ACTIVE",
                                          "rationale": "r",
                                          "evidence_id": "e",
                                          "review_hash": "h",
                                          "sequence": 1}),
                     ("ku_relation", {"id": "krl_x", "from_unit_id": "a",
                                      "to_unit_id": "b",
                                      "relation_type": "REVISES",
                                      "relation_hash": "h"})])
    assert sink.revisions == {} and sink.reviews == {} and sink.relations == {}
    assert sink.rollbacks == 1


def test_a_reload_sees_the_same_ids(evolved):
    reloaded = evolved["evolution"].sink.reload()
    assert sorted(reloaded["ku_revision"]) == \
        sorted(evolved["sink"].revisions)
    assert sorted(reloaded["ku_review_event"]) == \
        sorted(evolved["sink"].reviews)
    assert sorted(reloaded["knowledge_unit"]) == sorted(evolved["sink"].units)


# ── the emitted script ───────────────────────────────────────────────────────

def test_the_script_is_one_transaction(evolved, tmp_path):
    path = write_sql(evolved["result"], str(tmp_path / "evolution.sql"))
    script = Path(path).read_text(encoding="utf-8")
    assert script.count("BEGIN;") == 1
    assert script.count("COMMIT;") == 1
    assert script.index("BEGIN;") < script.index("COMMIT;")


def test_every_statement_is_idempotent(evolved, tmp_path):
    path = write_sql(evolved["result"], str(tmp_path / "evolution.sql"))
    lines = [line for line in
             Path(path).read_text(encoding="utf-8").splitlines()
             if line.startswith("INSERT INTO")]
    assert lines
    for line in lines:
        assert "ON CONFLICT (" in line and line.endswith("DO NOTHING;")


def test_the_script_writes_the_whole_ancestry(evolved, tmp_path):
    """A revised unit is a new candidate, a new verification and a new unit
    row; writing only the lifecycle would fail on its first foreign key."""
    path = write_sql(evolved["result"], str(tmp_path / "evolution.sql"))
    script = Path(path).read_text(encoding="utf-8")
    for table in ("book_source", "source_version", "reading_run",
                  "reading_evidence", "evidence_quality", "ku_candidate",
                  "ku_verification", "knowledge_unit", "ku_freeze_event",
                  "ku_revision", "ku_review_event", "ku_confidence_evolution",
                  "ku_relation"):
        assert f"INSERT INTO {table} " in script


def test_the_script_orders_parents_before_children(evolved, tmp_path):
    path = write_sql(evolved["result"], str(tmp_path / "evolution.sql"))
    script = Path(path).read_text(encoding="utf-8")
    order = [line.split("(")[0] for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    tables = [name.split()[-1] for name in order]
    for parent, child in (("book_source", "source_version"),
                          ("source_version", "reading_run"),
                          ("reading_run", "reading_evidence"),
                          ("reading_evidence", "ku_candidate"),
                          ("ku_candidate", "ku_verification"),
                          ("ku_verification", "knowledge_unit"),
                          ("knowledge_unit", "ku_freeze_event"),
                          ("knowledge_unit", "ku_revision"),
                          ("knowledge_unit", "ku_review_event"),
                          ("knowledge_unit", "ku_relation"),
                          ("knowledge_unit", "ku_confidence_evolution")):
        assert tables.index(parent) < tables.index(child), (
            f"{parent} must be written before {child}")


def test_the_script_emits_each_row_once(evolved, tmp_path):
    path = write_sql(evolved["result"], str(tmp_path / "evolution.sql"))
    lines = [line for line in
             Path(path).read_text(encoding="utf-8").splitlines()
             if line.startswith("INSERT INTO")]
    ids = [line.split("VALUES (")[1].split(",")[0] for line in lines]
    assert len(ids) == len(set(ids)), "a row is emitted more than once"


def test_the_script_escapes_quotes(tmp_path):
    """A rationale is free text, so a quote in it must not end the string."""
    from stratum.knowledge.a_repository.evolution import _literal
    assert _literal("it's a review") == "'it''s a review'"
    result = _fresh()
    evolution = result["evolution"]
    review = next(iter(evolution.sink.reviews.values()))
    review.rationale = "the reviewer wrote it's fine"
    path = write_sql(result, str(tmp_path / "quoted.sql"))
    script = Path(path).read_text(encoding="utf-8")
    assert "the reviewer wrote it''s fine" in script


def test_the_script_is_byte_identical_on_a_rerun(evolved, tmp_path):
    first = write_sql(evolved["result"], str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── the artifact ─────────────────────────────────────────────────────────────

def test_artifact_shape(evolved):
    doc = artifact(evolved["result"], list(REQUIRED_CHAIN))
    assert doc["task"] == "A_P5_KU_EVOLUTION"
    assert doc["authority"] == "A_REPOSITORY"
    assert doc["lifecycle_version"] == EVOLUTION_VERSION
    assert doc["traceability"] == "100%"
    assert doc["A_P5_KU_EVOLUTION"] == "PASS"
    for name in GATE_ORDER:
        assert doc["gate_results"][name] == "PASS"


def test_artifact_reports_the_lifecycle(evolved):
    doc = artifact(evolved["result"], list(REQUIRED_CHAIN))
    assert doc["revisions"] == 1
    assert doc["reviews"] == len(C.KU_REVIEWS) + 1
    assert doc["relation_types"] == ["REVISES", "SHARES_EVIDENCE"]
    assert doc["status_breakdown"]["SUPERSEDED"] == 1
    assert doc["persisted_units"] == 11


def test_the_report_and_the_artifact_agree(evolved):
    summary, doc = report(evolved["result"]), \
        artifact(evolved["result"], list(REQUIRED_CHAIN))
    for key in ("persisted_units", "revisions", "reviews",
                "confidence_observations", "relations", "relation_types",
                "status_breakdown"):
        assert summary[key] == doc[key], key
    # The artifact renders traceability as the headline string; the report
    # keeps the counts it was computed from.
    assert doc["traceability"] == "100%"
    assert summary["traceability"]["percent"] == 100.0


def test_committed_artifact_matches_the_runner():
    committed = __import__("json").loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = artifact(_fresh(), list(REQUIRED_CHAIN))
    for key in ("persisted_units", "revisions", "reviews",
                "confidence_observations", "relations", "relation_types",
                "status_breakdown", "traceability", "A_P5_KU_EVOLUTION",
                "lifecycle_version", "run_id"):
        assert committed[key] == fresh[key], key


def test_schema_gate_is_not_executed_without_a_ledger():
    assert schema_gate(None) == "NOT_EXECUTED"


def test_schema_gate_passes_on_the_full_chain():
    assert schema_gate(list(REQUIRED_CHAIN)) == "PASS"


def test_schema_gate_fails_without_075():
    assert schema_gate([n for n in REQUIRED_CHAIN
                        if n != REQUIRED_MIGRATION]) == "FAIL"


def test_all_six_gates_pass(evolved):
    gates = gate_results(evolved["result"], list(REQUIRED_CHAIN))
    for name in GATE_ORDER:
        assert gates[name] == "PASS", name
    assert gates["schema"] == "PASS"
    assert gates["idempotency"] == "PASS"


def test_the_first_book_is_the_frozen_pilot(evolved):
    assert C.BOOK_TITLE == "利率史（第四版）"
    assert evolved["report"]["book"] == "利率史（第四版） 第四版"


def test_the_ledger_reviews_only_units_the_corpus_actually_froze(evolved):
    reviewed = {v["unit_id"] for v in evolved["result"]["reviews"]}
    superseded = {_prior_id(evolved)}
    assert reviewed <= set(evolved["sink"].units)
    assert not (reviewed & superseded), \
        "the ledger reviews the pre-revision units, not the successors"
