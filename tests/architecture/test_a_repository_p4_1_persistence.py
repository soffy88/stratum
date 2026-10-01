"""A Repository P4.1 — KU durable persistence.

Contract tests for the durability writer (migration 074):
- schema: both tables, FKs, unique constraints, indexes
- authority: the writer reaches nothing outside the A chain
- transaction: a unit and its event are written together or not at all
- replay: persisting twice writes nothing the second time
- crash recovery: a failure between the two writes leaves nothing behind
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "074_a_ku_freeze_persistence.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p4_1_persistence.json"

from stratum.knowledge.a_repository import pilot_corpus as C  # noqa: E402
from stratum.knowledge.a_repository.persistence import (  # noqa: E402
    IMPLEMENTED_EVENT_TYPES,
    PERSISTENCE_VERSION,
    EventType,
    FreezeTransaction,
    InMemorySink,
    KUDurableWriter,
    PersistencePrecondition,
    PersistenceStatus,
    PersistenceViolation,
    event_hash,
    event_id,
    persisted_unit_id,
)
from stratum.knowledge.a_repository.ku_freeze_runner import (  # noqa: E402
    build_freeze_baseline,
)
from stratum.knowledge.a_repository.ku_persistence_runner import (  # noqa: E402
    ALLOWED_REFERENCES,
    REQUIRED_CHAIN,
    REQUIRED_MIGRATION,
    artifact,
    authority_gate,
    build_persistence,
    recovery_gate,
    report,
    schema_gate,
    transaction_gate,
)
from stratum.knowledge.a_repository.verification import (  # noqa: E402
    VerificationStatus,
)


@pytest.fixture
def durable():
    result = build_persistence()
    return {"result": result, "writer": result["writer"],
            "sink": result["sink"],
            "report": report(result, list(REQUIRED_CHAIN))}


def _first_verification_id(result) -> str:
    return sorted(result["freeze"].store._unit_by_verification)[0]


# ── schema ───────────────────────────────────────────────────────────────────

def test_074_declares_knowledge_unit_and_ku_freeze_event():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS stratum.knowledge_unit" not in sql, \
        "074 must not recreate knowledge_unit"
    assert "CREATE TABLE IF NOT EXISTS stratum.ku_freeze_event" in sql


def test_073_already_satisfies_the_canonical_schema():
    """Audited before 074 was written: no ALTER of knowledge_unit is
    needed, so 074 must not attempt one."""
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TABLE" not in sql
    assert "DROP " not in sql


def test_074_declares_every_event_column():
    sql = MIGRATION.read_text(encoding="utf-8")
    for column in ("id TEXT PRIMARY KEY",
                   "knowledge_unit_id TEXT NOT NULL",
                   "event_type TEXT NOT NULL",
                   "from_status TEXT",
                   "to_status TEXT NOT NULL",
                   "event_hash TEXT NOT NULL",
                   "created_at TIMESTAMP NOT NULL"):
        assert column in sql, f"074 missing column: {column}"


def test_074_event_foreign_key_restricts():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert re.search(
        r"knowledge_unit_id TEXT NOT NULL\s*"
        r"REFERENCES stratum\.knowledge_unit\(id\)\s*ON DELETE RESTRICT", sql)


def test_074_event_types_are_the_closed_vocabulary():
    sql = MIGRATION.read_text(encoding="utf-8")
    listed = set(re.findall(r"'([A-Z_]+)'",
                            sql.split("event_type IN (")[1].split(")")[0]))
    assert listed == {e.value for e in EventType}
    assert listed == {"CREATED", "FROZEN", "SUPERSEDED"}


def test_074_status_vocabulary_matches_the_persistence_lifecycle():
    sql = MIGRATION.read_text(encoding="utf-8")
    listed = set(re.findall(r"'([A-Z_]+)'",
                            sql.split("to_status IN (")[1].split(")")[0]))
    assert listed == {s.value for s in PersistenceStatus}


def test_074_has_the_unique_constraints_and_indexes():
    sql = MIGRATION.read_text(encoding="utf-8")
    for constraint in ("ku_freeze_event_uniq", "ku_freeze_event_hash_uniq"):
        assert f"CONSTRAINT {constraint} UNIQUE" in sql
    for index in ("idx_ku_freeze_event_unit", "idx_ku_freeze_event_type",
                  "idx_ku_freeze_event_created_at",
                  "idx_knowledge_unit_frozen_at",
                  "idx_knowledge_unit_freeze_version"):
        assert f"CREATE INDEX IF NOT EXISTS {index}" in sql


def test_074_backfills_nothing():
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    assert "INSERT INTO" not in statements


def test_074_references_only_knowledge_unit():
    sql = MIGRATION.read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", sql))
    assert referenced <= ALLOWED_REFERENCES


def test_074_superseded_is_defined_but_not_emitted():
    """Reserved for a revision stage that does not exist yet."""
    assert "SUPERSEDED" in {e.value for e in EventType}
    assert EventType.SUPERSEDED not in IMPLEMENTED_EVENT_TYPES


def test_074_is_additive_over_the_whole_chain():
    names = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert names[-1] == REQUIRED_MIGRATION
    for earlier in REQUIRED_CHAIN[:-1]:
        assert earlier in names


# ── authority ────────────────────────────────────────────────────────────────

def test_074_names_no_external_authority():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for token in ("knowledge_claims", "b_repository", "c_repository", "bu2",
                  "learning_object"):
        assert token not in sql


def test_074_performs_no_merge_or_correction():
    statements = re.sub(r"--.*", "", MIGRATION.read_text(encoding="utf-8"))
    for statement in ("UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert statement not in statements, f"074 contains {statement}"


def test_writer_modifies_nothing_upstream(durable):
    """The writer is a reader for candidates, verifications and evidence."""
    result = durable["result"]
    store = result["base"]["pipeline"].store
    snapshot = {
        "candidates": {k: (v.content, v.classification, v.status)
                       for k, v in store.ku_candidates.items()},
        "evidence": {k: v.content_span for k, v in store.evidence.items()},
        "verifications": {k: (v.verification_status, v.verification_score)
                          for k, v in result["verification"]
                          .store.verifications.items()},
    }
    durable["writer"].persist_verified(result["base"]["reading_run_id"])
    assert {k: (v.content, v.classification, v.status)
            for k, v in store.ku_candidates.items()} == snapshot["candidates"]
    assert {k: v.content_span for k, v in store.evidence.items()} \
        == snapshot["evidence"]
    assert {k: (v.verification_status, v.verification_score)
            for k, v in result["verification"].store.verifications.items()} \
        == snapshot["verifications"]


def test_authority_gate_passes():
    assert authority_gate() == "PASS"


# ── identity ─────────────────────────────────────────────────────────────────

def test_persisted_id_is_content_derived():
    value = persisted_unit_id("kc_1", "kv_1", "ch_1")
    assert value == persisted_unit_id("kc_1", "kv_1", "ch_1")
    assert value != persisted_unit_id("kc_2", "kv_1", "ch_1")
    assert value != persisted_unit_id("kc_1", "kv_2", "ch_1")
    assert value != persisted_unit_id("kc_1", "kv_1", "ch_2")


def test_persisted_id_is_never_a_uuid_sequence_or_timestamp(durable):
    import uuid
    for unit in durable["sink"].units.values():
        assert unit.id.startswith("ku_")
        assert not re.match(r"^\d+$", unit.id)
        assert len(unit.id.split("_")[1]) == 12
        with pytest.raises(ValueError):
            uuid.UUID(unit.id)
    del uuid


def test_event_id_and_hash_are_deterministic():
    assert event_id("ku_x", "FROZEN") == event_id("ku_x", "FROZEN")
    assert event_id("ku_x", "FROZEN") != event_id("ku_y", "FROZEN")
    a = event_hash("ku_x", "FROZEN", "FREEZE_PENDING", "FROZEN")
    b = event_hash("ku_x", "FROZEN", "FREEZE_PENDING", "FROZEN")
    c = event_hash("ku_x", "FROZEN", None, "FROZEN")
    assert a == b
    assert a != c


def test_same_freeze_yields_the_same_event_fingerprint(durable):
    """Persisting into a fresh store reproduces every fingerprint."""
    second = build_persistence()
    assert {u.id for u in durable["sink"].units.values()} \
        == {u.id for u in second["sink"].units.values()}
    assert {e.event_hash for e in durable["sink"].events.values()} \
        == {e.event_hash for e in second["sink"].events.values()}


# ── preconditions ────────────────────────────────────────────────────────────

def test_only_verified_units_are_persisted(durable):
    result = durable["result"]
    verification = result["verification"]
    rejected = [v.id for v in verification.store.verifications.values()
                if v.verification_status == VerificationStatus.REJECTED.value]
    for verification_id in rejected:
        with pytest.raises(PersistencePrecondition):
            durable["writer"].persist(verification_id)


def test_a_persistence_refusal_writes_nothing(durable):
    result = durable["result"]
    before_units = durable["writer"].unit_count()
    before_events = durable["writer"].event_count()
    rejected = next(v.id for v in result["verification"]
                    .store.verifications.values()
                    if v.verification_status == VerificationStatus.REJECTED.value)
    with pytest.raises(PersistencePrecondition):
        durable["writer"].persist(rejected)
    assert durable["writer"].unit_count() == before_units
    assert durable["writer"].event_count() == before_events


def test_every_persisted_unit_meets_the_evidence_chain(durable):
    result = durable["result"]
    store = result["base"]["pipeline"].store
    for unit in durable["sink"].units.values():
        candidate = store.ku_candidates[unit.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        assert evidence.source_version_id == unit.source_version_id
        assert evidence.source_version_id in store.source_versions
        assert unit.canonical_text in evidence.content_span


# ── transaction ──────────────────────────────────────────────────────────────

def test_a_unit_always_has_its_event(durable):
    writer = durable["writer"]
    assert writer.orphan_events() == []
    for unit in durable["sink"].units.values():
        events = [e for e in durable["sink"].events.values()
                  if e.knowledge_unit_id == unit.id]
        assert len(events) == 1
        assert events[0].event_type == EventType.FROZEN.value


def test_the_event_records_the_freeze_transition(durable):
    for event in durable["sink"].events.values():
        assert event.from_status == PersistenceStatus.FREEZE_PENDING.value
        assert event.to_status == PersistenceStatus.FROZEN.value


def test_transaction_gate_passes(durable):
    assert transaction_gate(durable["result"]) == "PASS"


def test_transaction_rolls_back_as_a_whole():
    sink = InMemorySink()
    with pytest.raises(RuntimeError):
        with FreezeTransaction(sink) as tx:
            tx.write("knowledge_unit", {"id": "ku_1"})
            tx.write("ku_freeze_event", {"id": "kfe_1"})
            raise RuntimeError("boom")
    assert sink.units == {}
    assert sink.events == {}
    assert sink.rollbacks == 1


def test_failed_persistence_is_reported_not_raised():
    """A failed attempt is an outcome, not an exception.

    The caller still has ten units to process after one of them dies, so
    persist() returns the verdict rather than propagating.
    """
    upstream = build_freeze_baseline()
    sink = InMemorySink(fail_after=1)
    writer = KUDurableWriter(upstream["base"]["pipeline"],
                             upstream["verification"],
                             upstream["freeze"], sink)
    outcome = writer.persist(_first_verification_id(upstream))
    assert outcome.status == PersistenceStatus.FAILED.value
    assert outcome.unit is None
    assert outcome.events == []
    assert outcome.written_unit is False
    assert outcome.written_events == 0
    assert outcome.failure


# ── crash recovery ───────────────────────────────────────────────────────────

def test_failure_between_the_two_writes_leaves_nothing():
    """Crash after the unit insert, before the event insert."""
    upstream = build_freeze_baseline()
    sink = InMemorySink(fail_after=1)
    writer = KUDurableWriter(upstream["base"]["pipeline"],
                             upstream["verification"],
                             upstream["freeze"], sink)
    outcome = writer.persist(_first_verification_id(upstream))

    assert outcome.status == PersistenceStatus.FAILED.value
    assert outcome.written_unit is False
    assert sink.units == {}, "a half-written unit survived the rollback"
    assert sink.events == {}
    assert sink.commits == 0
    assert sink.rollbacks >= 1


def test_recovery_gate_passes():
    assert recovery_gate() == "PASS"


def test_a_failed_unit_does_not_block_the_others():
    upstream = build_freeze_baseline()
    sink = InMemorySink(fail_after=1)
    writer = KUDurableWriter(upstream["base"]["pipeline"],
                             upstream["verification"],
                             upstream["freeze"], sink)
    results = writer.persist_verified(upstream["base"]["reading_run_id"])
    assert all(r.status == PersistenceStatus.FAILED.value for r in results)
    assert sink.units == {}
    # A retry with a healthy sink writes all ten.
    healthy = InMemorySink()
    retry = KUDurableWriter(upstream["base"]["pipeline"],
                            upstream["verification"],
                            upstream["freeze"], healthy)
    assert len(retry.persist_verified(
        upstream["base"]["reading_run_id"])) == 10
    assert healthy.units


# ── replay ───────────────────────────────────────────────────────────────────

def test_persisting_twice_writes_nothing_the_second_time(durable):
    writer = durable["writer"]
    before_units, before_events = writer.unit_count(), writer.event_count()
    second = writer.persist_verified(durable["result"]["base"]["reading_run_id"])
    assert writer.unit_count() == before_units
    assert writer.event_count() == before_events
    assert sum(r.written_unit for r in second) == 0
    assert sum(r.written_events for r in second) == 0


def test_replay_creates_no_duplicate_unit_or_event(durable):
    writer = durable["writer"]
    assert writer.duplicate_units() == []
    assert writer.duplicate_events() == []
    writer.persist_verified(durable["result"]["base"]["reading_run_id"])
    assert writer.duplicate_units() == []
    assert writer.duplicate_events() == []


def test_counts_match_the_acceptance_numbers(durable):
    assert durable["writer"].unit_count() == 10
    assert durable["writer"].event_count() == 10
    assert durable["report"]["failed_attempts"] == 0


# ── durability ───────────────────────────────────────────────────────────────

def test_reload_sees_the_same_ids_and_provenance(durable):
    reloaded = durable["writer"].reload()
    assert len(reloaded) == 10
    for unit in reloaded.values():
        original = durable["sink"].units[unit.id]
        assert original.id == unit.id
        assert original.content_hash == unit.content_hash
        assert original.canonical_text == unit.canonical_text
        assert original.source_version_id == unit.source_version_id


def test_a_second_process_reads_identical_ids():
    """A later run, built from scratch, produces the same durable ids."""
    first = build_persistence()["sink"]
    second = build_persistence()["sink"]
    assert {u.id for u in first.units.values()} \
        == {u.id for u in second.units.values()}
    assert {e.id for e in first.events.values()} \
        == {e.id for e in second.events.values()}


def test_traceability_is_complete(durable):
    trace = durable["writer"].traceability()
    assert trace["units"] == 10
    assert trace["trace_complete"] == 10
    assert trace["percent"] == 100.0
    assert trace["unique_ids"] == 10


# ── immutability ─────────────────────────────────────────────────────────────

def test_a_persisted_unit_cannot_be_updated(durable):
    unit = next(iter(durable["sink"].units.values()))
    with pytest.raises(PersistenceViolation):
        durable["writer"].update_unit(unit.id, statement="改写")
    assert durable["sink"].units[unit.id].statement == unit.statement


def test_a_persisted_unit_cannot_be_deleted(durable):
    unit = next(iter(durable["sink"].units.values()))
    with pytest.raises(PersistenceViolation):
        durable["writer"].delete_unit(unit.id)
    assert unit.id in durable["sink"].units


def test_a_freeze_event_cannot_be_deleted(durable):
    event = next(iter(durable["sink"].events.values()))
    with pytest.raises(PersistenceViolation):
        durable["writer"].delete_event(event.id)
    assert event.id in durable["sink"].events


# ── gates and artifact ───────────────────────────────────────────────────────

def test_schema_gate_is_not_executed_without_a_ledger():
    assert schema_gate(None) == "NOT_EXECUTED"


def test_schema_gate_passes_on_the_full_chain():
    assert schema_gate(list(REQUIRED_CHAIN)) == "PASS"


def test_schema_gate_fails_without_074():
    assert schema_gate(list(REQUIRED_CHAIN[:-1])) == "FAIL"


def test_all_five_gates_pass(durable):
    doc = artifact(durable["result"], list(REQUIRED_CHAIN))
    assert doc["gate_results"] == {
        "schema": "PASS", "transaction": "PASS", "replay": "PASS",
        "authority": "PASS", "recovery": "PASS"}


def test_artifact_shape(durable):
    doc = artifact(durable["result"], list(REQUIRED_CHAIN))
    assert doc["task"] == "A_P4_1_KU_DURABLE_WRITER"
    assert doc["book"].startswith("利率史")
    assert doc["input_verified"] == 10
    assert doc["persisted"] == 10
    assert doc["events"] == 10
    assert doc["duplicates"] == 0
    assert doc["traceability"] == "100%"
    assert doc["replay"] == "PASS"
    assert doc["authority"] == "A_REPOSITORY"
    assert doc["persistence_version"] == PERSISTENCE_VERSION
    assert doc["event_types"] == [EventType.FROZEN.value]


def test_committed_artifact_matches_the_runner(durable):
    import json
    assert ARTIFACT.exists(), "p4_1_persistence.json is missing"
    on_disk = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    produced = artifact(durable["result"], on_disk["ledger"])
    for field in ("input_verified", "persisted", "events", "duplicates",
                  "traceability", "replay", "authority", "event_types",
                  "persistence_version", "units"):
        assert on_disk[field] == produced[field], f"artifact drifted: {field}"


# ── regression boundary ──────────────────────────────────────────────────────

def test_earlier_migrations_are_untouched_by_this_stage():
    for name in ("070_a_repository_foundation.sql",
                 "071_a_evidence_quality.sql",
                 "072_a_ku_verification.sql",
                 "073_a_knowledge_unit_freeze.sql"):
        text = (MIGRATIONS / name).read_text(encoding="utf-8")
        assert "ku_freeze_event" not in text, f"{name} was edited by P4.1"


def test_p2_and_p3_logic_are_untouched():
    quality = (PKG / "quality.py").read_text(encoding="utf-8")
    verification = (PKG / "verification.py").read_text(encoding="utf-8")
    assert "def classify" in quality
    assert PERSISTENCE_VERSION not in quality
    assert PERSISTENCE_VERSION not in verification


def test_first_book_is_the_frozen_pilot(durable):
    summary = report(durable["result"], list(REQUIRED_CHAIN))
    assert summary["book"].startswith("利率史")
    assert summary["run_id"] == "arr_d0d1473d79fc"
    assert C.BOOK_TITLE == "利率史（第四版）"

# ── the durable SQL script ───────────────────────────────────────────────────

def test_sql_script_is_one_transaction(durable):
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    assert script.startswith("BEGIN;")
    assert script.rstrip().endswith("COMMIT;")
    assert script.count("BEGIN;") == 1
    assert script.count("COMMIT;") == 1


def test_sql_script_writes_the_whole_ancestry(durable):
    """A knowledge unit cannot be written without its parents, and every
    stage before P4.1 ran in memory."""
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    for table in ("book_source", "source_version", "reading_run",
                  "reading_evidence", "evidence_quality", "ku_candidate",
                  "ku_verification", "knowledge_unit", "ku_freeze_event"):
        assert f"INSERT INTO {table} " in script, f"{table} missing from SQL"
    assert script.count("INSERT INTO knowledge_unit ") == 10
    assert script.count("INSERT INTO ku_freeze_event ") == 10


def test_every_statement_is_idempotent(durable):
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    inserts = [l for l in script.splitlines() if l.startswith("INSERT INTO")]
    assert inserts
    for line in inserts:
        assert "ON CONFLICT" in line and "DO NOTHING" in line, \
            f"statement is not replay-safe: {line[:80]}"


def test_sql_script_orders_parents_before_children(durable):
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    order = ["book_source", "source_version", "reading_run",
             "reading_evidence", "ku_candidate", "ku_verification",
             "knowledge_unit", "ku_freeze_event"]
    positions = [script.index(f"INSERT INTO {t} ") for t in order]
    assert positions == sorted(positions), "a child is written before its parent"


def test_sql_script_sets_frozen_at_for_a_frozen_unit(durable):
    """073 refuses a FROZEN row with a null frozen_at; the writer found
    that out against a real database."""
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    unit_lines = [l for l in script.splitlines()
                  if l.startswith("INSERT INTO knowledge_unit ")]
    assert unit_lines
    for line in unit_lines:
        assert line.rstrip().endswith("DO NOTHING;")
        assert "NOW()" in line, "a FROZEN row must carry frozen_at"


def test_sql_script_emits_enum_values_not_reprs(durable):
    from stratum.knowledge.a_repository.ku_persistence_runner import write_sql
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = write_sql(durable["result"], f"{tmp}/freeze.sql")
        script = open(target, encoding="utf-8").read()
    assert "KIClassification" not in script
    assert "VerificationStatus" not in script


def test_sql_escapes_quotes(durable):
    from stratum.knowledge.a_repository.persistence import _literal
    assert _literal("it's") == "'it''s'"
    assert _literal(None) == "NULL"
    assert _literal(True) == "TRUE"
    assert _literal(1.5) == "1.5"
