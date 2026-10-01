"""A Repository P5.2 — relation candidate.

Contract tests for the relation layer (migration 079):

- Schema        table, FK completeness, RESTRICT only, hash unique,
                closed vocabulary, same-source keys, self-relation
- Evidence      both sides present and non-empty, traceability to the book
- Lifecycle     generated->supported, generated->rejected, nothing terminal moves
- Replay        same input same hash, re-running appends nothing
- Isolation     same source enforced, declared order holds
- Authority     no BU2, no B, no C; frozen ku_relation untouched; no judgement
- Pilot         declared rows are never mistaken for extracted ones

The §15/§TEST CONTRACT checklist lives at the bottom as one gate, so the
ordering review-then-apply stays a fact rather than a habit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "079_a_relation_candidate.sql"
FROZEN_RELATION_MIGRATION = MIGRATIONS / "075_a_ku_evolution.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_2_relation.json"

from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    artifact_drift,
    external_imports,
)
from stratum.knowledge.a_repository.relation import (  # noqa: E402
    DEFERRED_TYPES,
    EXTRACTOR_VERSION,
    LEGAL_STATUS_TRANSITIONS,
    PILOT_DECLARED_VERSION,
    RELATION_BANNED_FIELDS,
    RELATION_COLUMNS,
    RELATION_INSERT_COLUMNS,
    RELATION_TABLES,
    RELATION_TYPES,
    RelationCandidate,
    RelationPrecondition,
    RelationSink,
    RelationStatus,
    RelationViolation,
    RelationWriter,
    banned_field_report,
    emit_relation_sql,
    precedes_in_book,
    relation_hash,
    relation_id,
    transition,
)
from stratum.knowledge.a_repository.relation_runner import (  # noqa: E402
    ALLOWED_FK_TARGETS,
    FROZEN_TABLE_INDEX,
    PILOT_RELATION,
    REQUIRED_MIGRATION,
    UNTOUCHABLE_TABLES,
    acceptance,
    authority_gate,
    banned_field_gate,
    baseline_mutation_gate,
    build_relation,
    column_parity_gate,
    constraint_gate,
    contamination_counts,
    double_side_gate,
    final_report,
    fk_verb_gate,
    frozen_index_gate,
    gate_results,
    hash_stability_gate,
    idempotency_gate,
    isolation_schema_gate,
    ku_relation_untouched_gate,
    negative_gate,
    null_status_gate,
    order_gate,
    report,
    same_source_gate,
    schema_gate,
    trace_gate,
    vocabulary_gate,
    write_sql,
)


@pytest.fixture(scope="module")
def relation():
    return build_relation()


@pytest.fixture(scope="module")
def writer(relation):
    return relation["writer"]


def _fresh() -> Dict:
    return build_relation()


def _clean() -> str:
    return re.sub(r"--[^\n]*", "",
                  MIGRATION.read_text(encoding="utf-8"))


# ── Schema ───────────────────────────────────────────────────────────────────

def test_relation_tables_exist():
    clean = _clean()
    for table in RELATION_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean
    assert schema_gate() == "PASS"


def test_relation_fk_only_A():
    """Every foreign key lands on an A table, and every one is RESTRICT.

    CASCADE appears in A仓 only in 070-072, the extraction chain, where a
    deleted book should take its evidence with it. Every frozen artifact from
    073 on is RESTRICT. A relation is a recorded comparison, so deleting its
    book or either unit must not take it silently.
    """
    clean = _clean()
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert referenced <= ALLOWED_FK_TARGETS
    assert referenced == {"source_version", "knowledge_unit"}
    assert fk_verb_gate() == "PASS"
    verbs = re.findall(r"ON DELETE (\w+)", clean)
    assert set(verbs) == {"RESTRICT"}


def test_fk_is_complete():
    """Three foreign keys: the book, and each unit.

    A missing one is a relation that can name a unit of no book at all, which
    is exactly what the composite keys exist to prevent.
    """
    clean = _clean()
    assert "FOREIGN KEY (source_version_id)" not in clean  # inline, not named
    assert clean.count("REFERENCES stratum.source_version") == 1
    assert clean.count("REFERENCES stratum.knowledge_unit") == 2
    assert isolation_schema_gate() == "PASS"


def test_relation_type_closed():
    """PRECEDES is the only value the CHECK admits.

    The deferred types must be absent from the constraint, not merely unused,
    so raw SQL cannot smuggle CONTRASTS in later.
    """
    clean = _clean()
    assert "CHECK (relation_type IN ('PRECEDES'))" in clean
    assert vocabulary_gate() == "PASS"
    assert RELATION_TYPES == ("PRECEDES",)


def test_the_deferred_types_are_absent_not_merely_unused():
    """075 refused SAME_MEANING and TENSION; CONTRASTS is that renamed.

    So the three deferred types must not appear anywhere in 079 — not in the
    CHECK, not in a comment claiming they are deferred, not in a comment
    explaining why. Naming them in the file would leave the next reader
    deciding whether the comment was the contract.
    """
    assert vocabulary_gate() == "PASS"
    assert set(DEFERRED_TYPES) == {"SUPPORTS", "CONTRASTS", "DEPENDS_ON"}


def test_relation_hash_unique(writer):
    clean = _clean()
    assert "CONSTRAINT relation_candidate_hash_uniq UNIQUE (relation_hash)" \
        in clean
    assert constraint_gate() == "PASS"
    assert writer.duplicate_hashes() == []


def test_self_relation_blocked(writer):
    """A unit cannot precede itself. Expressible in a CHECK, so it is one."""
    clean = _clean()
    assert "CONSTRAINT relation_no_self CHECK (left_unit_id <> right_unit_id)" \
        in clean
    fresh = _fresh()
    with pytest.raises(RelationPrecondition, match="precede itself"):
        fresh["builder"].build(
            fresh["result"]["base"]["source_version_id"],
            PILOT_RELATION[0], PILOT_RELATION[0], "PRECEDES",
            PILOT_DECLARED_VERSION)
    assert writer.self_relations() == []


def test_relation_same_source_version(relation, writer):
    """Both units must be of the relation's own book.

    The review spec asked for this and measured that v1.0's single-column keys
    did not deliver it: a cross-book pair was accepted. 079 uses two composite
    foreign keys, and this reads the file to confirm the composite form is
    declared rather than trusting the comment.
    """
    clean = _clean()
    assert isolation_schema_gate() == "PASS"
    assert same_source_gate(relation) == "PASS"
    assert writer.cross_source_relations() == []
    for candidate in relation["sink"].relation_candidates.values():
        for unit_id in (candidate.left_unit_id, candidate.right_unit_id):
            unit = relation["sink"].units[unit_id]
            assert unit.source_version_id == candidate.source_version_id


def test_the_frozen_table_takes_one_index_and_nothing_else():
    """079's single change to a frozen table, authorised and bounded.

    The index is the target of the composite keys. It asserts nothing new —
    (id, source_version_id) is already unique because id is the primary key —
    and it must not have become a route to altering knowledge_unit.
    """
    clean = _clean()
    assert f"CREATE UNIQUE INDEX IF NOT EXISTS {FROZEN_TABLE_INDEX}" in clean
    assert frozen_index_gate() == "PASS"
    assert "ALTER TABLE" not in clean
    assert "CREATE TABLE IF NOT EXISTS stratum.knowledge_unit (" not in clean
    indexed = set(re.findall(r"ON stratum\.(\w+)", clean))
    assert indexed <= {"knowledge_unit", *RELATION_TABLES}


def test_079_touches_nothing_it_inherits():
    clean = _clean()
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        assert forbidden not in clean
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean


def test_status_and_evidence_are_not_null():
    """A CHECK passes on NULL, so a nullable status walks past its vocabulary.

    Measured in the P5.2 schema review: `CHECK (status IN (...))` on a nullable
    column accepted a NULL row. Same class as the array_length finding in 077.
    """
    clean = _clean()
    assert null_status_gate() == "PASS"
    body = clean.split("CREATE TABLE IF NOT EXISTS stratum."
                       "relation_candidate (")[1]
    for column in ("status", "left_evidence_ids", "right_evidence_ids"):
        fragment = next(f for f in body.split("\n")
                        if f.strip().startswith(f"{column} "))
        assert "NOT NULL" in fragment


def test_created_at_has_a_default_so_the_insert_omits_it():
    """079 declares DEFAULT now(), unlike 078 which had to write NOW().

    A NOT NULL created_at with no default fails every insert that forgets the
    column — 077 shipped that bug. With a default the insert omits the column,
    so a replay cannot carry a timestamp that disagrees with the stored row.
    """
    clean = _clean()
    assert "created_at TIMESTAMP NOT NULL DEFAULT now()" in clean
    assert column_parity_gate() == "PASS"
    assert "created_at" not in RELATION_INSERT_COLUMNS
    assert "created_at" in RELATION_COLUMNS


def test_column_parity():
    """Writer columns, schema columns and dataclass fields must agree."""
    assert column_parity_gate() == "PASS"
    fields = set(vars(RelationCandidate(id="", relation_type="",
                                       source_version_id="", left_unit_id="",
                                       right_unit_id="")))
    assert set(RELATION_COLUMNS) <= fields


def test_no_judgement_column_grew():
    """A relation records a comparison, never what it means."""
    assert not any(banned_field_report().values())
    assert banned_field_gate() == "PASS"
    for name in RELATION_BANNED_FIELDS:
        assert not hasattr(RelationCandidate, name)
        assert name not in RELATION_COLUMNS
    for banned in ("meaning", "interpretation", "explanation", "truth_score"):
        assert banned not in RELATION_COLUMNS


def test_earlier_migrations_are_untouched():
    for name in ("073_a_knowledge_unit_freeze.sql",
                 "074_a_ku_freeze_persistence.sql",
                 "075_a_ku_evolution.sql", "076_a_ku_identity.sql",
                 "077_a_condition_boundary.sql",
                 "078_a_mechanism_chain.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in RELATION_TABLES:
            assert table not in sql


# ── Evidence ─────────────────────────────────────────────────────────────────

def test_left_right_evidence_required(relation, writer):
    """Both sides carry evidence. Two CHECKs, so it is the database's job."""
    clean = _clean()
    for side in ("left", "right"):
        assert f"CHECK (cardinality({side}_evidence_ids) >= 1)" in clean
    candidate = relation["written"]
    assert candidate.left_evidence_ids
    assert candidate.right_evidence_ids
    assert double_side_gate(relation) == "PASS"
    assert writer.single_side_relations() == []


def test_empty_evidence_rejected():
    fresh = _fresh()
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.left_evidence_ids.clear())
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.right_evidence_ids.clear())


def test_single_side_relation_rejected():
    """A one-sided relation cannot be told apart from an adjacent statement."""
    fresh = _fresh()
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.right_evidence_ids.clear())
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.left_evidence_ids.clear())


def test_evidence_must_exist_and_belong_to_the_book():
    """TEXT[] carries no foreign key, so the CHECK proves non-empty only."""
    fresh = _fresh()
    with pytest.raises(RelationPrecondition):
        _write_damaged(
            fresh, lambda c: c.right_evidence_ids.append("ev_not_in_this_book"))


def test_relation_traceability(relation, writer):
    """relation -> unit -> evidence -> same book, 100%."""
    assert trace_gate(relation) == "PASS"
    assert writer.traceability_percent() == 100.0
    for candidate in relation["sink"].relation_candidates.values():
        for unit_id, evidence_ids in (
                (candidate.left_unit_id, candidate.left_evidence_ids),
                (candidate.right_unit_id, candidate.right_evidence_ids)):
            unit = relation["sink"].units[unit_id]
            assert unit.source_version_id == candidate.source_version_id
            for evidence_id in evidence_ids:
                evidence = relation["result"]["base"]["pipeline"].store.evidence[
                    evidence_id]
                assert evidence.source_version_id == candidate.source_version_id


def _write_damaged(fresh: Dict, mutate) -> None:
    """Clone the pilot relation, damage it, and try to write it.

    A distinct id and hash so the duplicate short-circuit cannot mask the
    precondition check.
    """
    from stratum.knowledge.a_repository.relation_runner import _clone
    clone = _clone(fresh["candidate"])
    mutate(clone)
    clone.id = "rlc_damaged"
    clone.relation_hash = "rlh_damaged"
    fresh["writer"].write(clone)


# ── Lifecycle ────────────────────────────────────────────────────────────────

def test_generated_supported():
    fresh = _fresh()
    candidate = fresh["written"]
    assert candidate.status == RelationStatus.GENERATED.value
    supported = fresh["writer"].support(candidate.id)
    assert supported.status == RelationStatus.SUPPORTED.value


def test_generated_rejected():
    fresh = _fresh()
    rejected = fresh["writer"].reject(fresh["written"].id)
    assert rejected.status == RelationStatus.REJECTED.value


def test_invalid_transition():
    """Both SUPPORTED and REJECTED are final.

    v0.2's arrow diagram permitted SUPPORTED -> REJECTED; that is refused here,
    matching v1.0 §9 and the rule 077/078 freeze against. A仓 corrects by
    appending a new relation under a new hash.
    """
    assert LEGAL_STATUS_TRANSITIONS[RelationStatus.SUPPORTED] == frozenset()
    assert LEGAL_STATUS_TRANSITIONS[RelationStatus.REJECTED] == frozenset()
    fresh = _fresh()
    candidate = fresh["written"]
    fresh["writer"].support(candidate.id)
    for target in (RelationStatus.GENERATED, RelationStatus.REJECTED):
        with pytest.raises(RelationViolation, match="final"):
            transition(candidate, target)
    assert candidate.status == RelationStatus.SUPPORTED.value


def test_a_rejected_relation_is_not_revived():
    fresh = _fresh()
    candidate = fresh["writer"].reject(fresh["written"].id)
    for target in (RelationStatus.GENERATED, RelationStatus.SUPPORTED):
        with pytest.raises(RelationViolation, match="final"):
            transition(candidate, target)


def test_there_is_no_verified_state():
    clean = _clean()
    assert "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" in clean
    assert {s.value for s in RelationStatus} == {"GENERATED", "SUPPORTED",
                                                 "REJECTED"}
    assert "VERIFIED" not in {s.value for s in RelationStatus}
    assert "CONFIRMED" not in {s.value for s in RelationStatus}


def test_nothing_can_be_mutated_deleted_or_given_meaning(writer, relation):
    stored = relation["written"].id
    for method in ("update_relation", "delete_relation"):
        with pytest.raises(RelationViolation):
            getattr(writer, method)(stored)
    with pytest.raises(RelationViolation):
        writer.merge_relations("rlc_a", "rlc_b")
    with pytest.raises(RelationViolation, match="VERIFIED"):
        writer.verify_relation(stored)
    with pytest.raises(RelationViolation, match="B仓"):
        writer.add_semantics(stored)
    with pytest.raises(RelationViolation, match="never touches"):
        writer.update_verification("anything")


# ── Replay ───────────────────────────────────────────────────────────────────

def test_relation_replay_no_duplicate():
    """Re-running writes nothing, and a second run is byte-identical."""
    replay = idempotency_gate
    assert gate_results(_fresh())["GATE_4_replay"] == "PASS"
    fresh = _fresh()
    assert replay(fresh) == "PASS"
    assert fresh["writer"].duplicate_hashes() == []


def test_relation_hash_stable():
    """Same input, same id and hash. Any change, a different relation.

    The extractor version is inside both, which is what stops a future
    extraction over the same two units and the same evidence from being
    swallowed as a replay of the pilot.
    """
    assert hash_stability_gate() == "PASS"
    left, right = PILOT_RELATION
    evidence = ["ev_a", "ev_b"]
    other = ["ev_c"]
    base_hash = relation_hash("PRECEDES", "sv_x", left, right, evidence, other,
                              PILOT_DECLARED_VERSION)
    # Order within one side is traversal order, not a claim.
    assert relation_hash("PRECEDES", "sv_x", left, right,
                         list(reversed(evidence)), other,
                         PILOT_DECLARED_VERSION) == base_hash
    # Direction is a claim.
    assert relation_hash("PRECEDES", "sv_x", right, left, evidence, other,
                         PILOT_DECLARED_VERSION) != base_hash
    # The extractor version is a claim.
    assert relation_hash("PRECEDES", "sv_x", left, right, evidence, other,
                         EXTRACTOR_VERSION) != base_hash
    assert relation_id("PRECEDES", "sv_x", left, right,
                       PILOT_DECLARED_VERSION).startswith("rlc_")
    assert relation_hash("PRECEDES", "sv_x", left, right, evidence, other,
                         PILOT_DECLARED_VERSION).startswith("rlh_")


def test_the_emitted_script_is_idempotent(relation):
    script = emit_relation_sql(relation["sink"].relation_candidates)
    lines = [line for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    assert lines
    for line in lines:
        assert "ON CONFLICT (relation_hash) DO NOTHING;" in line
    assert "ARRAY[" in script
    assert script.count("BEGIN;") == 1 and script.count("COMMIT;") == 1


def test_the_emitted_script_is_byte_identical_on_a_rerun(tmp_path):
    first = write_sql(_fresh(), str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── Isolation ────────────────────────────────────────────────────────────────

def test_cross_source_relation_blocked():
    """The pilot is one book, so the probe moves the relation's own book.

    Every unit then sits in a different version from the relation, which is
    exactly what both the writer gate and the composite keys check.
    """
    fresh = _fresh()
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.__setattr__(
            "source_version_id", "sv_a_different_book"))
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.__setattr__(
            "source_version_id", "sv_absent"))


def test_order_is_declared_and_holds(relation, writer):
    """left really does sit earlier in the book than right.

    A writer gate, not a CHECK: ordering needs reading_evidence and PostgreSQL
    refuses a CHECK that reads another table.
    """
    assert order_gate(relation) == "PASS"
    candidate = relation["written"]
    builder = relation["builder"]
    assert precedes_in_book(builder, candidate.left_unit_id,
                            candidate.right_unit_id)
    assert not precedes_in_book(builder, candidate.right_unit_id,
                                candidate.left_unit_id)
    assert writer.out_of_order_relations() == []


def test_an_unknown_unit_is_refused():
    fresh = _fresh()
    with pytest.raises(RelationPrecondition):
        _write_damaged(fresh, lambda c: c.__setattr__("right_unit_id",
                                                      "ku_not_a_unit"))


# ── Authority ────────────────────────────────────────────────────────────────

def test_no_BU2_dependency():
    assert authority_gate(_fresh()) == "PASS"
    clean = _clean().lower()
    for foreign in ("bu_onto", "chapter_bu", "bu_learning_state"):
        assert f"references stratum.{foreign}" not in clean
    assert contamination_counts(_fresh())["BU2_DEPENDENCY"] == 0


def test_no_B_dependency():
    assert contamination_counts(_fresh())["B_REFERENCE"] == 0
    clean = _clean().lower()
    for foreign in ("aii_refined", "refined_ku", "refined_concept"):
        assert foreign not in clean


def test_no_C_dependency():
    assert contamination_counts(_fresh())["C_REFERENCE"] == 0
    assert external_imports() == []
    source = (PKG / "relation.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    for foreign in ("learning_progress", "mastery", "learning_card"):
        assert foreign not in code


def test_the_artifact_carries_no_contamination(relation):
    payload = {"relations": [r.id
                             for r in relation["sink"].relation_candidates.values()]}
    assert artifact_drift(payload) == {}


def test_the_baseline_underneath_is_untouched(relation):
    assert baseline_mutation_gate(relation) == "PASS"


def test_the_frozen_075_relation_layer_is_untouched():
    """079 is a second layer beside ku_relation, never a replacement.

    Two vocabularies coexist by decision. This is the gate that keeps the
    decision honest: 075's table is neither created, altered nor merged, and
    neither is its vocabulary extended.
    """
    assert ku_relation_untouched_gate(_fresh()) == "PASS"
    frozen = FROZEN_RELATION_MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS stratum.ku_relation" in frozen
    for deferred in DEFERRED_TYPES:
        assert deferred not in frozen
    clean = _clean()
    assert "ku_relation" not in clean
    assert "ALTER TABLE stratum.ku_relation" not in clean


def test_the_two_layers_cannot_be_merged(writer):
    with pytest.raises(RelationViolation, match="authority"):
        writer.merge_relations("krl_9ea8c603c443", "rlc_4d5a399df2cd")


def test_verification_logic_still_untouched():
    from stratum.knowledge.a_repository.verification import (
        AVerificationPipeline)
    assert AVerificationPipeline.required_slots("FACT") == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")


# ── Pilot ────────────────────────────────────────────────────────────────────

def test_pilot_declared_separate_from_extractor(relation, writer):
    """Pilot data is not extraction evidence, and the two stay distinct."""
    pilot = writer.pilot_rows()
    extracted = writer.extracted_rows()
    assert pilot, "the pilot relation should be labelled pilot-declared"
    assert extracted == [], \
        "this stage ships no extractor; nothing may claim to be extracted"
    for relation_id_ in pilot:
        row = relation["sink"].relation_candidates[relation_id_]
        assert row.extractor_version == PILOT_DECLARED_VERSION
        assert row.extractor_version != EXTRACTOR_VERSION


def test_the_pilot_relation_is_in_reading_order_of_this_chapter(relation):
    """Declared, in reading order, over units of 利率史 chapter 1."""
    builder = relation["builder"]
    candidate = relation["written"]
    assert candidate.relation_type == "PRECEDES"
    pages = []
    for unit_id in (candidate.left_unit_id, candidate.right_unit_id):
        locator = builder.locator_of(unit_id)
        assert locator is not None
        evidence = relation["result"]["base"]["pipeline"].store.evidence[
            builder.evidence_of(unit_id)[0]]
        assert evidence.locator["chapter"] == "第一章 古代时期的信贷"
        pages.append(locator[0])
    assert pages == sorted(pages)
    assert pages[0] < pages[1], "the pilot declares left before right"


def test_the_pilot_is_not_called_an_extraction(relation):
    """The report must not imply the extractor works."""
    doc = report(relation)
    assert doc["extracted_rows"] == []
    assert doc["pilot_rows"]
    assert doc["relation_types_authorised"] == ["PRECEDES"]
    assert doc["relation_types_deferred"] == list(DEFERRED_TYPES)
    assert doc["pilot_chapter"] == "第一章 古代时期的信贷"


# ── negative ─────────────────────────────────────────────────────────────────

def test_negative_gate_refuses_every_case(relation):
    """Each forbidden shape is refused, and each one is named."""
    checks = negative_gate(relation)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    for name in ("deferred_supports", "deferred_contrasts",
                 "deferred_depends_on", "self_relation", "no_left_evidence",
                 "no_right_evidence", "cross_source", "order_reversed",
                 "supported_downgrade", "rejected_revived", "add_semantics"):
        assert name in checks


# ── the test contract ────────────────────────────────────────────────────────

def test_review_checklist():
    """The spec's checklist, as one gate so the ordering stays a fact."""
    clean = _clean()
    assert schema_gate() == "PASS"                    # additive
    assert fk_verb_gate() == "PASS"                   # RESTRICT only
    assert isolation_schema_gate() == "PASS"          # same source enforced
    assert frozen_index_gate() == "PASS"              # one index, on one table
    assert vocabulary_gate() == "PASS"                # only PRECEDES
    assert null_status_gate() == "PASS"               # no NULL past a CHECK
    assert constraint_gate() == "PASS"                # hash unique, both sides
    assert column_parity_gate() == "PASS"
    assert banned_field_gate() == "PASS"              # no judgement column
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert not {"bu_onto", "chapter_bu"} & referenced        # no FK to BU2
    assert not any(r.endswith("_onto") for r in referenced)  # no FK to B / C


def test_all_gates_pass(relation):
    gates = gate_results(relation)
    for name, value in gates.items():
        if isinstance(value, dict):
            continue
        if name == "GATE_3_traceability_percent":
            assert value == 100.0
            continue
        assert value == "PASS", f"{name}={value}"


def test_acceptance_block(relation):
    doc = acceptance(relation)
    checks = doc["checks"]
    assert doc["A_P5_2_RELATION_SCHEMA"] == "PASS"
    assert doc["A_P5_2_RELATION_IMPLEMENTATION"] == "PASS"
    assert doc["RELATION_TYPE"] == "PRECEDES_ONLY"
    assert checks["relation_persisted"] == 1
    assert checks["both_sides_evidenced"] is True
    assert checks["order_declared_and_holds"] is True
    assert checks["traceability_percent"] == 100.0
    assert checks["source_isolation"] == "PASS"
    assert checks["replay_stable"] == "PASS"
    assert checks["transaction_atomic"] == "PASS"
    assert checks["deferred_types_present"] == 0
    assert checks["self_relations"] == 0
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0
    assert checks["BU2_DEPENDENCY"] == 0
    assert checks["baseline_mutated"] == 0
    assert checks["negative_refusals"] == checks["negative_cases"]


def test_final_report_block(relation):
    """The v0.2 FINAL REPORT keys, present and honest.

    COMMIT_SHA and TAG name a commit that has not been made. They read PENDING
    rather than a guessed value, because a freeze report that invents its own
    commit id is worse than one that admits it has none.
    """
    block = final_report(relation)
    for key in ("A_P5_2_RELATION", "MIGRATION_079", "RELATION_TYPE",
                "RELATION_ROWS", "TRACEABILITY", "SOURCE_ISOLATION", "REPLAY",
                "AUTHORITY_SCAN", "B_CONTAMINATION", "C_CONTAMINATION",
                "DB_MUTATION", "BU2_MUTATION", "075_UNTOUCHED", "COMMIT_SHA",
                "TAG", "FINAL_STATUS"):
        assert key in block, key
    assert block["A_P5_2_RELATION"] == "PASS"
    assert block["MIGRATION_079"] == REQUIRED_MIGRATION
    assert block["RELATION_TYPE"] == "PRECEDES_ONLY"
    assert block["RELATION_ROWS"] == "1"
    assert block["TRACEABILITY"] == "100.0%"
    assert block["SOURCE_ISOLATION"] == "PASS"
    assert block["REPLAY"] == "PASS"
    assert block["075_UNTOUCHED"] == "PASS"
    assert block["B_CONTAMINATION"] == "0"
    assert block["C_CONTAMINATION"] == "0"
    assert block["DB_MUTATION"] == "0"
    assert block["BU2_MUTATION"] == "0"


def test_committed_artifact_matches_a_fresh_run():
    assert ARTIFACT.exists(), "run relation_runner to emit the artifact"
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = report(_fresh())
    for key in ("relation_count", "pilot_rows", "extracted_rows",
                "traceability_percent", "relation_version",
                "relation_types_authorised", "relation_types_deferred",
                "pilot_chapter"):
        assert committed[key] == fresh[key], key
    assert committed["relations"] == fresh["relations"]