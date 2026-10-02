"""A Repository P5.1 — mechanism chain.

Contract tests for the mechanism layer (migration 078):

- Schema        tables, FK verb and target, hash unique, order unique, status
- Persistence   atomic write, rollback on partial failure, replay no-duplicate
- Authority     no BU2, no B, no C dependency
- Lifecycle     generated->supported, generated->rejected, no downgrade
- Pilot         declared chains are never mistaken for extracted ones

The §14 review checklist lives at the bottom as one gate, so the ordering
"review before apply" is a fact rather than a habit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import pytest


ROOT = Path(__file__).parents[2]
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "078_a_mechanism_chain.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_1_mechanism.json"

from stratum.knowledge.a_repository.mechanism import (  # noqa: E402
    EXTRACTOR_VERSION,
    MECHANISM_BANNED_FIELDS,
    MECHANISM_COLUMNS,
    MECHANISM_TABLES,
    MECHANISM_VERSION,
    NODE_COLUMNS,
    PILOT_DECLARED_VERSION,
    LEGAL_STATUS_TRANSITIONS,
    MechanismCandidate,
    MechanismNode,
    MechanismPrecondition,
    MechanismSink,
    MechanismStatus,
    MechanismViolation,
    MechanismWriter,
    NodeRole,
    ROLE_ORDER,
    banned_field_report,
    chain_is_complete,
    emit_mechanism_sql,
    mechanism_hash,
    mechanism_id,
    node_id,
    transition,
)
from stratum.knowledge.a_repository.mechanism_runner import (  # noqa: E402
    ALLOWED_FK_TARGETS,
    PILOT_CHAIN,
    REQUIRED_MIGRATION,
    UNTOUCHABLE_TABLES,
    acceptance,
    authority_gate,
    banned_field_gate,
    baseline_mutation_gate,
    build_chain,
    column_parity_gate,
    completeness_gate,
    constraint_gate,
    contamination_counts,
    fk_verb_gate,
    gate_results,
    idempotency_gate,
    negative_gate,
    report,
    replay_gate,
    schema_gate,
    trace_gate,
    write_sql,
)
from stratum.knowledge.a_repository.projection_builder import (  # noqa: E402
    artifact_drift,
    external_imports,
)


@pytest.fixture(scope="module")
def chain():
    return build_chain()


@pytest.fixture(scope="module")
def sink(chain):
    return chain["sink"]


@pytest.fixture(scope="module")
def writer(chain):
    return chain["writer"]


def _fresh() -> Dict:
    return build_chain()


def _clean() -> str:
    return re.sub(r"--[^\n]*", "",
                  MIGRATION.read_text(encoding="utf-8"))


# ── Schema ───────────────────────────────────────────────────────────────────

def test_mechanism_tables_exist():
    clean = _clean()
    for table in MECHANISM_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean
    assert schema_gate() == "PASS"


def test_mechanism_fk_only_points_to_A():
    """Every foreign key lands on an A table, and every one is RESTRICT.

    CASCADE appears in A仓 only in 070-072, the extraction chain, where a
    deleted book should take its evidence with it. Every frozen artifact
    from 073 on is RESTRICT, and 073 states why in the migration itself. A
    mechanism chain is a frozen artifact, so CASCADE here would be the first
    in A仓 where deleting a parent silently takes its children.
    """
    clean = _clean()
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert referenced <= ALLOWED_FK_TARGETS
    assert referenced == {"source_version", "knowledge_unit",
                          "mechanism_candidate"}
    assert fk_verb_gate() == "PASS"
    actions = re.findall(r"REFERENCES\s+stratum\.\w+\(id\)\s+ON DELETE (\w+)",
                         clean)
    assert set(actions) == {"RESTRICT"}


def test_mechanism_hash_unique():
    clean = _clean()
    assert ("CONSTRAINT mechanism_candidate_hash_uniq UNIQUE (mechanism_hash)"
            in clean)
    assert constraint_gate() == "PASS"


def test_sequence_order_unique(writer):
    clean = _clean()
    flat = re.sub(r"\s+", " ", clean)
    assert ("CONSTRAINT mechanism_node_order_uniq UNIQUE (mechanism_id, "
            "sequence_order)") in flat
    # Two nodes must not share a position, or the chain order is ambiguous.
    assert writer.duplicate_orders() == []


def test_status_closed():
    clean = _clean()
    assert ("CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))"
            in clean)
    assert {s.value for s in MechanismStatus} == {"GENERATED", "SUPPORTED",
                                                   "REJECTED"}
    # VERIFIED is the success value of ku_verification; CONFIRMED would be
    # a second word for that same fact.
    assert "VERIFIED" not in {s.value for s in MechanismStatus}
    assert "CONFIRMED" not in {s.value for s in MechanismStatus}


def test_node_role_closed():
    clean = _clean()
    assert ("CHECK (node_role IN ('TRIGGER', 'TRANSITION', 'RESULT'))" in clean)
    assert {r.value for r in NodeRole} == set(ROLE_ORDER)


def test_078_touches_nothing_it_inherits():
    clean = _clean()
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        assert forbidden not in clean
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean


def test_evidence_array_uses_cardinality_not_array_length():
    """Measured while applying 077: `array_length(ARRAY[]::text[], 1)` is
    NULL and a CHECK passes on NULL, so an array_length guard accepts the
    empty array it exists to reject. cardinality() returns 0 there."""
    clean = _clean()
    assert "CHECK (cardinality(evidence_ids) >= 1)" in clean
    assert "array_length(evidence_ids" not in clean


def test_column_parity():
    """Writer columns, schema columns and dataclass fields must agree."""
    assert column_parity_gate() == "PASS"


def test_no_judgement_column_grew():
    """A mechanism records a structure, never a judgement."""
    report_map = banned_field_report()
    assert not any(report_map.values())
    assert banned_field_gate() == "PASS"
    for name in MECHANISM_BANNED_FIELDS:
        assert not hasattr(MechanismCandidate, name)
        assert not hasattr(MechanismNode, name)
        assert name not in MECHANISM_COLUMNS
        assert name not in NODE_COLUMNS


def test_the_field_names_carry_the_discipline():
    """TRIGGER / TRANSITION / RESULT are the fields; cause and effect are
    not. The names are the discipline."""
    source = (PKG / "mechanism.py").read_text(encoding="utf-8")
    for field in ("trigger_event", "transition_event", "result_event"):
        assert field in source
    assert "cause" in MECHANISM_BANNED_FIELDS


# ── Persistence ──────────────────────────────────────────────────────────────

def test_mechanism_atomic_write(chain, sink, writer):
    """One chain and all its nodes, or neither."""
    candidate = chain["candidate"]
    assert candidate.id in sink.mechanisms
    nodes = writer.nodes_of(candidate.id)
    assert [n.sequence_order for n in nodes] == [1, 2, 3]
    for node in nodes:
        assert node.id in sink.nodes
        assert node.mechanism_id == candidate.id


def test_nodes_are_written_after_their_mechanism(sink):
    """The node's foreign key has to resolve, so the order is not cosmetic."""
    script = emit_mechanism_sql(sink.mechanisms, sink.nodes)
    body = script.splitlines()
    first_mechanism = next(i for i, line in enumerate(body)
                           if "mechanism_candidate (" in line)
    first_node = next(i for i, line in enumerate(body)
                      if "mechanism_node (" in line)
    assert first_mechanism < first_node
    assert script.count("BEGIN;") == 1 and script.count("COMMIT;") == 1


def test_partial_failure_rollback():
    """A failure between the mechanism and its nodes leaves neither."""
    # Arm the fault AFTER the chain is built. Passing fail_after into the
    # sink would trip it during the P6 identity write instead, and the
    # failure would be somebody else's.
    crashed = build_chain()
    # A chain that is not already stored, or write() short-circuits on the
    # duplicate and never opens a transaction to fail.
    other = _fresh()["candidate"]
    other.id = "mec_rollback_probe"
    other.mechanism_hash = "meh_rollback_probe"
    for node in other.nodes:
        node.mechanism_id = other.id
    before = (len(crashed["sink"].mechanisms), len(crashed["sink"].nodes))
    crashed["sink"].fail_after = 1
    crashed_writer = MechanismWriter(
        crashed["result"]["base"]["pipeline"], crashed["sink"])
    with pytest.raises(MechanismViolation):
        crashed_writer.write(other)
    assert (len(crashed["sink"].mechanisms),
            len(crashed["sink"].nodes)) == before, \
        "a failed mechanism write must leave nothing behind"
    assert crashed["sink"].rollbacks >= 1


def test_no_orphan_node(chain, writer):
    assert writer.orphan_nodes() == []
    assert writer.orphan_mechanisms() == []


def test_replay_no_duplicate(chain):
    """Re-running writes nothing, and a second run is byte-identical."""
    replay = replay_gate()
    assert replay["identical_fingerprints"] == 1
    assert replay["rewrite_is_noop"] == 1
    assert replay["new_mechanism"] == 0
    assert replay["new_node"] == 0
    assert replay["duplicate_chains"] == 0
    assert idempotency_gate(chain) == "PASS"


def test_hash_is_content_derived():
    """Never a uuid, never a timestamp: the same chain always hashes the
    same, and re-ordering produces a different chain."""
    base = mechanism_id("sv_1", ["ku_a", "ku_b"], "v1")
    assert base == mechanism_id("sv_1", ["ku_a", "ku_b"], "v1")
    assert base != mechanism_id("sv_1", ["ku_b", "ku_a"], "v1")
    assert base != mechanism_id("sv_1", ["ku_a", "ku_b"], "v2")
    assert base.startswith("mec_") and len(base) == 16


def test_node_id_is_derived_and_covers_evidence():
    first = node_id("mec_x", "TRIGGER", 1, "ku_a", ["ev_1"])
    assert first == node_id("mec_x", "TRIGGER", 1, "ku_a", ["ev_1"])
    assert first != node_id("mec_x", "TRIGGER", 1, "ku_a", ["ev_2"])
    assert first.startswith("men_")


def test_order_is_part_of_the_identity():
    """Re-ordering the same nodes is a different chain, so the order is
    part of what was recorded rather than an accident of insertion."""
    forward = mechanism_hash("sv_1", ["men_a", "men_b"], "v1")
    backward = mechanism_hash("sv_1", ["men_b", "men_a"], "v1")
    assert forward != backward


def test_derivation_order_is_non_circular():
    """P6 ended up with two ids for one object. The order here is written
    down so it cannot be reshuffled."""
    source = (PKG / "mechanism.py").read_text(encoding="utf-8")
    assert "No node ids and no evidence" in source
    # mechanism_id must not depend on node ids.
    body = source.split("def mechanism_id(")[1].split("def node_id(")[0]
    assert "node_id" not in body and "mechanism_hash" not in body


def test_the_emitted_script_is_idempotent(chain):
    script = emit_mechanism_sql(chain["sink"].mechanisms, chain["sink"].nodes)
    lines = [line for line in script.splitlines()
             if line.startswith("INSERT INTO")]
    assert lines
    for line in lines:
        assert "ON CONFLICT (" in line and line.endswith("DO NOTHING;")
    assert "ARRAY[" in script


def test_the_emitted_script_names_created_at(chain):
    """A NOT NULL created_at with no default fails every insert if the
    column is omitted — 077 shipped that bug and every insert died."""
    script = emit_mechanism_sql(chain["sink"].mechanisms, chain["sink"].nodes)
    for table in MECHANISM_TABLES:
        line = next(l for l in script.splitlines()
                    if f"INSERT INTO {table} " in l)
        assert "created_at" in line
        assert "NOW()" in line


def test_the_script_is_byte_identical_on_a_rerun(chain, tmp_path):
    first = write_sql(chain, str(tmp_path / "a.sql"))
    second = write_sql(_fresh(), str(tmp_path / "b.sql"))
    assert Path(first).read_bytes() == Path(second).read_bytes()


# ── Authority ────────────────────────────────────────────────────────────────

def test_no_BU2_dependency(chain):
    assert authority_gate(chain) == "PASS"
    clean = _clean()
    for foreign in ("bu_onto", "chapter_bu", "bu_learning_state"):
        assert f"REFERENCES stratum.{foreign}" not in clean
    assert contamination_counts(chain)["BU2_DEPENDENCY"] == 0


def test_no_B_dependency(chain):
    assert contamination_counts(chain)["B_REFERENCE"] == 0
    clean = _clean().lower()
    for foreign in ("aii_refined", "refined_ku", "refined_concept"):
        assert foreign not in clean


def test_no_C_dependency(chain):
    assert contamination_counts(chain)["C_REFERENCE"] == 0
    assert external_imports() == []
    source = (PKG / "mechanism.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    for foreign in ("learning_progress", "mastery", "learning_card"):
        assert foreign not in code


def test_the_artifact_carries_no_contamination(chain):
    payload = {"mechanisms": [m.id for m in chain["sink"].mechanisms.values()],
               "nodes": [n.id for n in chain["sink"].nodes.values()]}
    assert artifact_drift(payload) == {}


def test_the_baseline_underneath_is_untouched(chain):
    assert baseline_mutation_gate(chain) == "PASS"


def test_the_chain_follows_only_its_own_book(chain, writer):
    assert writer.cross_source_nodes() == []
    mechanism = chain["candidate"]
    for node in writer.nodes_of(mechanism.id):
        unit = chain["sink"].units[node.knowledge_unit_id]
        assert unit.source_version_id == mechanism.source_version_id
        for evidence_id in node.evidence_ids:
            evidence = chain["result"]["base"]["pipeline"].store.evidence[
                evidence_id]
            assert evidence.source_version_id == mechanism.source_version_id


# ── Lifecycle ────────────────────────────────────────────────────────────────

def test_generated_to_supported(chain):
    fresh = _fresh()
    candidate = fresh["written"]
    assert candidate.status == MechanismStatus.GENERATED.value
    supported = fresh["writer"].support(candidate.id)
    assert supported.status == MechanismStatus.SUPPORTED.value


def test_generated_to_rejected(chain):
    fresh = _fresh()
    rejected = fresh["writer"].reject(fresh["written"].id)
    assert rejected.status == MechanismStatus.REJECTED.value


def test_invalid_transition_blocked(chain):
    """SUPPORTED is final. A仓 corrects by appending a new chain under a
    new hash, never by downgrading this one."""
    assert LEGAL_STATUS_TRANSITIONS[MechanismStatus.SUPPORTED] == frozenset()
    fresh = _fresh()
    candidate = fresh["written"]
    fresh["writer"].support(candidate.id)
    for target in (MechanismStatus.GENERATED, MechanismStatus.REJECTED):
        with pytest.raises(MechanismViolation, match="final"):
            transition(candidate, target)
    assert candidate.status == MechanismStatus.SUPPORTED.value


def test_a_chain_with_a_missing_role_cannot_be_supported():
    """KNOWN_LIMITATION 5: a CHECK cannot count rows in another table, so
    this is the service gate that closes it."""
    fresh = _fresh()
    candidate = fresh["written"]
    # The stored candidate carries nodes=[] on purpose — the sink's node
    # table is the single place a node lives, so there is nothing to
    # duplicate and nothing to drift. Removing a row from that table is
    # therefore how an incomplete chain is actually produced.
    assert candidate.nodes == []
    result_node = next(n for n in fresh["sink"].nodes.values()
                       if n.mechanism_id == candidate.id
                       and n.node_role == NodeRole.RESULT.value)
    del fresh["sink"].nodes[result_node.id]
    assert chain_is_complete(candidate) is False
    with pytest.raises(MechanismPrecondition, match="missing"):
        fresh["writer"].support(candidate.id)


def test_completeness_gate():
    assert completeness_gate(_fresh()) == "PASS"


def test_nothing_can_be_mutated_or_deleted(chain, writer):
    stored = chain["written"].id
    for method in ("update_mechanism", "delete_mechanism"):
        with pytest.raises(MechanismViolation):
            getattr(writer, method)(stored)
    with pytest.raises(MechanismViolation):
        writer.update_node("men_x")
    with pytest.raises(MechanismViolation):
        writer.merge_chains("mec_a", "mec_b")
    with pytest.raises(MechanismViolation, match="VERIFIED"):
        writer.verify_chain(stored)
    with pytest.raises(MechanismViolation, match="cause"):
        writer.add_cause(stored)
    with pytest.raises(MechanismViolation, match="never touches"):
        writer.update_verification("anything")


def test_negative_gate_refuses_every_case(chain):
    """Each forbidden shape is refused, and each one is named."""
    checks = negative_gate(chain)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    for name in ("empty_chain", "trigger_only", "no_evidence",
                 "cross_source", "verified_status", "empty_array",
                 "supported_downgrade"):
        assert name in checks


# ── Pilot ────────────────────────────────────────────────────────────────────

def test_pilot_declared_not_extractor(chain):
    """Pilot data is not extraction evidence, and the two must stay
    distinguishable."""
    writer: MechanismWriter = chain["writer"]
    pilot = writer.pilot_rows()
    extracted = writer.extracted_rows()
    assert pilot, "the pilot chain should be labelled pilot-declared"
    assert extracted == [], \
        "this stage ships no extractor; nothing may claim to be extracted"
    for mechanism_id in pilot:
        mechanism = chain["sink"].mechanisms[mechanism_id]
        assert mechanism.extractor_version == PILOT_DECLARED_VERSION
        assert mechanism.extractor_version != EXTRACTOR_VERSION
    assert sorted(pilot + extracted) == sorted(
        chain["sink"].mechanisms)


def test_pilot_chain_is_reading_order_of_three_frozen_units(chain, writer):
    """Declared, in reading order, over units of this chapter."""
    assert [role for _, role in PILOT_CHAIN] == list(ROLE_ORDER)
    nodes = writer.nodes_of(chain["candidate"].id)
    assert [n.sequence_order for n in nodes] == [1, 2, 3]
    pages = []
    for node in nodes:
        unit = chain["sink"].units[node.knowledge_unit_id]
        candidate_row = chain["result"]["base"]["pipeline"].store.ku_candidates[
            unit.candidate_id]
        evidence = chain["result"]["base"]["pipeline"].store.evidence[
            candidate_row.evidence_id]
        assert evidence.locator["chapter"] == "第一章 古代时期的信贷"
        pages.append(evidence.page_number)
    assert pages == sorted(pages), "the pilot declares reading order"


def test_the_pilot_chain_is_not_called_an_extraction(chain):
    """The report must not imply the extractor works."""
    doc = report(chain)
    assert doc["extracted_rows"] == []
    assert doc["pilot_rows"]
    assert doc["pilot_chapter"] == "第一章 古代时期的信贷"


# ── the §14 checklist ────────────────────────────────────────────────────────

def test_review_checklist(chain):
    """§14, as one gate so the ordering review-then-apply is a fact."""
    clean = _clean()
    assert schema_gate() == "PASS"                 # no ALTER existing A table
    assert fk_verb_gate() == "PASS"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    assert not {"bu_onto", "chapter_bu"} & referenced      # no FK to BU2
    assert not any(r.endswith("_onto") for r in referenced)  # no FK to B / C
    assert "UNIQUE (mechanism_hash)" in clean.replace("\n", " ").replace(
        "        ", "")
    assert "UNIQUE (mechanism_id, sequence_order)" in clean
    assert "CHECK (cardinality(evidence_ids) >= 1)" in clean
    assert "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" in clean
    assert column_parity_gate() == "PASS"
    assert banned_field_gate() == "PASS"


# ── gates and artifact ───────────────────────────────────────────────────────

def test_all_five_gates_pass(chain):
    gates = gate_results(chain)
    for name in ("GATE_1_schema", "GATE_1_fk_verb", "GATE_1_constraints",
                 "GATE_1_column_parity", "GATE_1_banned_fields",
                 "GATE_2_trace", "GATE_2_completeness", "GATE_3_replay",
                 "GATE_4_authority", "GATE_5_negative"):
        assert gates[name] == "PASS", f"{name}={gates[name]}"
    # The gate now reports a status, not the raw percentage. Assert both: a
    # PASS with a measurement that is not 100.0 would be a gate that lies.
    assert gates["GATE_2_traceability_percent"] == "PASS"
    assert chain["writer"].traceability_percent() == 100.0


def test_acceptance_block(chain):
    doc = acceptance(chain)
    checks = doc["checks"]
    assert doc["A_P5_1_MECHANISM_SCHEMA"] == "PASS"
    assert doc["A_P5_1_MECHANISM_IMPLEMENTATION"] == "PASS"
    assert checks["mechanism_persisted"] == 1
    assert checks["nodes_ordered"] is True
    assert checks["evidence_linked"] == 100.0
    assert checks["replay_stable"] == "PASS"
    assert checks["transaction_atomic"] == "PASS"
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0
    assert checks["BU2_DEPENDENCY"] == 0
    assert checks["baseline_mutated"] == 0
    assert checks["negative_refusals"] == checks["negative_cases"]


def test_committed_artifact_matches_a_fresh_run():
    assert ARTIFACT.exists(), "run mechanism_runner to emit the artifact"
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = report(_fresh())
    for key in ("mechanism_count", "node_count", "pilot_rows",
                "extracted_rows", "traceability_percent", "mechanism_version",
                "pilot_chapter"):
        assert committed[key] == fresh[key], key
    assert committed["chains"] == fresh["chains"]


def test_earlier_migrations_are_untouched():
    for name in ("073_a_knowledge_unit_freeze.sql",
                 "074_a_ku_freeze_persistence.sql",
                 "075_a_ku_evolution.sql", "076_a_ku_identity.sql",
                 "077_a_condition_boundary.sql"):
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        for table in MECHANISM_TABLES:
            assert table not in sql


def test_verification_logic_still_untouched():
    from stratum.knowledge.a_repository.verification import (
        AVerificationPipeline)
    assert AVerificationPipeline.required_slots("FACT") == (
        "ANCHORED", "SUBJECT", "PREDICATE", "OBJECT")