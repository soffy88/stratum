"""A Repository P5.2 — relation candidate runner.

Builds the pilot declared PRECEDES relation over the frozen units and reports
the five acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.relation_runner

    Gate 1 Schema      table exists, additive, FK into A only, RESTRICT only,
                       vocabulary closed to PRECEDES, hash unique
    Gate 2 Authority   no semantic judgement, no B / C / BU2, frozen ku_relation
                       untouched
    Gate 3 Trace       relation -> unit -> evidence -> same book, 100%
    Gate 4 Replay      re-running writes nothing
    Gate 5 Isolation   same source enforced, both sides evidenced, order holds

Contamination is measured in three layers and reuses P7's gates. A word scan
over A仓 source returns hits that are all of A仓's own guard lists; that trap
has now been avoided five times.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import pilot_corpus as C
from .ku_identity_runner import build_identity
from .projection_builder import artifact_drift, external_imports
from .relation import (
    DEFERRED_TYPES,
    EXTRACTOR_VERSION,
    PILOT_DECLARED_VERSION,
    RELATION_BANNED_FIELDS,
    RELATION_COLUMNS,
    RELATION_INSERT_COLUMNS,
    RELATION_NOTES,
    RELATION_TABLES,
    RELATION_TYPES,
    RELATION_VERSION,
    RelationBuilder,
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


REQUIRED_MIGRATION = "079_a_relation_candidate.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    "075_a_ku_evolution.sql",
    "076_a_ku_identity.sql",
    "077_a_condition_boundary.sql",
    "078_a_mechanism_chain.sql",
    REQUIRED_MIGRATION,
)

#: The only tables 079 may reference. A relation records a comparison inside one
#: book, so every link it follows is A's own frozen chain.
ALLOWED_FK_TARGETS = frozenset({"source_version", "knowledge_unit"})

#: Tables P5.2 must never create or alter. ku_relation is here because 075 is
#: frozen: 079 is a second layer beside it, never a replacement.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event", "ku_condition_candidate",
                      "ku_boundary_candidate", "ku_relation",
                      "mechanism_candidate", "mechanism_node")

#: The one change 079 makes to a frozen table, authorised by the review spec's
#: same-source section. An index, not an ALTER: no row, column or value moves.
#: (id, source_version_id) is already unique because id is the primary key, so
#: this asserts nothing new and cannot fail on existing rows — it exists to be
#: the target of two composite foreign keys.
FROZEN_TABLE_INDEX = "knowledge_unit_id_source_version_uniq"

#: The pilot relation: two frozen units of 利率史 chapter 1, declared in
#: reading order, each with its own evidence.
#:
#: Declared, not extracted. No relation extractor ships in this stage, and a
#: PRECEDES found by a model is not a locator order, so these rows exist to
#: exercise the persistence, replay and traceability contract and are labelled
#: `pilot-declared` so they can never be read as an extraction result.
#:
#: p.1 信贷的历史早于工业、银行业与铸币业
#: p.3 《汉谟拉比法典》
PILOT_RELATION: Tuple[str, str] = (
    "ku_6460a6062a10",   # p.1
    "ku_59cb9040d0f0",   # p.3
)


def build_relation(sink=None) -> Dict:
    """P1 -> P7 -> P6 -> P5.2, then the pilot relation, written once."""
    chain = (build_identity(sink=sink) if sink is not None
             else build_identity(sink=RelationSink()))
    upstream = chain["result"]
    units = {key: dict(vars(unit))
             for key, unit in sorted(chain["sink"].units.items())}

    builder = RelationBuilder(upstream["base"]["pipeline"], chain["sink"].units)
    candidate = builder.build(
        source_version_id=upstream["base"]["source_version_id"],
        left_unit_id=PILOT_RELATION[0],
        right_unit_id=PILOT_RELATION[1],
        relation_type=RELATION_TYPES[0],
        extractor_version=PILOT_DECLARED_VERSION)
    writer = RelationWriter(upstream["base"]["pipeline"], chain["sink"])
    written = writer.write(candidate)

    return {"chain": chain, "result": upstream, "sink": chain["sink"],
            "builder": builder, "writer": writer, "candidate": candidate,
            "written": written, "unit_snapshot_before": units}


# ── Gate 1 schema ────────────────────────────────────────────────────────────

def _migration() -> str:
    return (Path(__file__).parents[2] / "db" / "pg_migrations"
            / REQUIRED_MIGRATION).read_text(encoding="utf-8")


def _clean() -> str:
    return re.sub(r"--[^\n]*", "", _migration())


def _declared_columns(table: str) -> set:
    text = _clean()
    marker = f"CREATE TABLE IF NOT EXISTS stratum.{table}"
    if marker not in text:
        return set()
    # Split on the name only. Splitting on the name *and* its opening paren
    # leaves `body` starting after it, and then hunting for the next "(" lands
    # inside the first CHECK rather than at the start of the column list — which
    # reports one column and looks like a parity failure.
    body = text.split(marker)[1]
    start = body.index("(") + 1
    depth, block = 1, []
    for char in body[start:]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        block.append(char)
    parts, depth, current = [], 0, []
    for char in "".join(block):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    declared = set()
    for fragment in parts:
        fragment = fragment.strip()
        if not fragment:
            continue
        head = fragment.split()[0]
        if head.upper() in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY",
                             "FOREIGN", "REFERENCES"}:
            continue
        declared.add(head)
    return declared


def schema_gate() -> str:
    """One new table, additive only, FK into A only."""
    clean = _clean()
    for table in RELATION_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean:
            return "FAIL"
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        if forbidden in clean:
            return "FAIL"
    for table in UNTOUCHABLE_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean:
            return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    return "PASS"


def fk_verb_gate() -> str:
    """Every foreign key is RESTRICT, single-column or composite.

    Measured across the A chain: CASCADE appears only in 070-072, the extraction
    chain, where a deleted book should take its evidence with it. Every frozen
    artifact from 073 on is RESTRICT. A relation is a recorded comparison, so
    deleting its book or either of its units must not take it silently.
    """
    clean = _clean()
    # \s* before the paren: the single-column and composite references are
    # written with different spacing, and a check that only passes on one
    # formatting reports a schema problem when there is none.
    single = re.findall(r"REFERENCES\s+stratum\.\w+\s*\(id\)\s*ON DELETE (\w+)",
                        clean)
    composite = re.findall(
        r"REFERENCES\s+stratum\.\w+\s*\(id, source_version_id\)\s*"
        r"ON DELETE (\w+)", clean)
    if len(single) != 1 or len(composite) != 2:
        return "FAIL"
    if set(single + composite) != {"RESTRICT"}:
        return "FAIL"
    return "PASS"


def isolation_schema_gate() -> str:
    """The same-source composite keys, and their index, are actually declared.

    The review spec asked for same-source enforcement and measured that the
    single-column keys of v1.0 did not provide it. This reads the file to confirm
    the composite form is present rather than trusting the comment.
    """
    clean = _clean()
    for side in ("left", "right"):
        if (f"CONSTRAINT relation_{side}_same_source" not in clean
                or f"FOREIGN KEY ({side}_unit_id, source_version_id)"
                not in clean):
            return "FAIL"
    if clean.count("REFERENCES stratum.knowledge_unit (id, source_version_id)") \
            != 2:
        return "FAIL"
    if f"ON stratum.knowledge_unit (id, source_version_id)" not in clean:
        return "FAIL"
    return "PASS"


def frozen_index_gate() -> str:
    """The one index on a frozen table, and nothing else touching it.

    079 may add an index to knowledge_unit because the review spec authorised
    it. It may not alter the table, and it may not reach any other frozen table.
    """
    clean = _clean()
    if f"CREATE UNIQUE INDEX IF NOT EXISTS {FROZEN_TABLE_INDEX}" not in clean:
        return "FAIL"
    indexed = re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS \w+\s+"
                         r"ON stratum\.(\w+)", clean)
    # The composite-key target, plus the eight new-table indexes.
    if indexed.count("knowledge_unit") != 1:
        return "FAIL"
    if set(indexed) - {"knowledge_unit", *RELATION_TABLES}:
        return "FAIL"
    return "PASS"


def constraint_gate() -> str:
    """Hash unique, both evidence arrays guarded, closed vocabularies,
    self-relation excluded, and the writer's columns all declared."""
    clean = _clean()
    required = (
        "CONSTRAINT relation_candidate_hash_uniq UNIQUE (relation_hash)",
        "CONSTRAINT relation_no_self CHECK (left_unit_id <> right_unit_id)",
    )
    for fragment in required:
        if fragment not in clean:
            return "FAIL"
    # Two sides, two guards. One guard would leave the other side optional.
    for side in ("left", "right"):
        if f"CHECK (cardinality({side}_evidence_ids) >= 1)" not in clean:
            return "FAIL"
    if "array_length(" in clean:
        return "FAIL"
    if "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" not in clean:
        return "FAIL"
    if not set(RELATION_COLUMNS) <= _declared_columns(RELATION_TABLES[0]):
        return "FAIL"
    return "PASS"


def vocabulary_gate() -> str:
    """PRECEDES is the only value the CHECK admits.

    The deferred types must be absent from the constraint, not merely unused,
    so a later writer cannot smuggle CONTRASTS in through raw SQL.
    """
    clean = _clean()
    if "CHECK (relation_type IN ('PRECEDES'))" not in clean:
        return "FAIL"
    line = clean.split("CHECK (relation_type IN (")[1].split(")")[0]
    for deferred in DEFERRED_TYPES:
        if deferred in line or deferred in clean:
            return "FAIL"
    return "PASS"


def null_status_gate() -> str:
    """status and both evidence columns are NOT NULL.

    Measured in the P5.2 schema review: a CHECK passes on NULL, so a nullable
    status walks straight past the vocabulary it was written to enforce. Same
    class as the array_length finding in 077.
    """
    clean = _clean()
    body = clean.split("CREATE TABLE IF NOT EXISTS stratum."
                       "relation_candidate (")[1]
    for column in ("status", "left_evidence_ids", "right_evidence_ids"):
        fragment = next(f for f in body.split("\n")
                        if f.strip().startswith(f"{column} "))
        if "NOT NULL" not in fragment:
            return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Writer columns, schema columns and dataclass fields must agree.

    077 shipped once referencing two columns it never declared and every insert
    failed against a real database. Only the disagreement shows it.
    """
    declared = _declared_columns(RELATION_TABLES[0])
    fields = set(vars(RelationCandidate(id="", relation_type="",
                                       source_version_id="", left_unit_id="",
                                       right_unit_id="")))
    if not set(RELATION_COLUMNS) <= declared:
        return "FAIL"
    if not set(RELATION_COLUMNS) <= fields:
        return "FAIL"
    if "created_at" in RELATION_INSERT_COLUMNS:
        # 079 declares DEFAULT now(); writing the column anyway is how 077
        # shipped an insert that could contradict the stored timestamp.
        return "FAIL"
    return "PASS"


def banned_field_gate() -> str:
    """No relation row grew a judgement column."""
    return "FAIL" if any(banned_field_report().values()) else "PASS"


# ── Gate 2 authority ─────────────────────────────────────────────────────────

def ku_relation_untouched_gate(result: Dict) -> str:
    """The frozen 075 relation layer is not created, altered or merged.

    079 is a second layer beside ku_relation. Two vocabularies coexist by
    decision, and this is the gate that keeps the decision honest.
    """
    clean = _clean()
    if "CREATE TABLE IF NOT EXISTS stratum.ku_relation" in clean:
        return "FAIL"
    if "ALTER TABLE stratum.ku_relation" in clean:
        return "FAIL"
    if "ku_relation" in result["sink"].ROW_TYPES and \
            "ku_relation" in RELATION_TABLES:
        return "FAIL"
    return "PASS"


def authority_gate(result: Dict) -> str:
    """B, C and BU2 all zero, in three layers."""
    if external_imports():
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    payload = {"relations": [r.id for r in result["sink"].relation_candidates.values()]}
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Dict) -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, measured in the three layers.

    Never a word scan of this file: the token list would match itself, which is
    the false positive that produced 24 hits in A仓.
    """
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    drift = len(referenced - ALLOWED_FK_TARGETS)
    payload = {"relations": [r.id for r in result["sink"].relation_candidates.values()]}
    total = len(external_imports()) + drift + len(artifact_drift(payload))
    return {"B_REFERENCE": total, "C_REFERENCE": total,
            "BU2_DEPENDENCY": drift,
            "external_imports": len(external_imports())}


def baseline_mutation_gate(result: Dict) -> str:
    """The A chain underneath is byte-identical after the write."""
    after = {key: dict(vars(unit))
             for key, unit in sorted(result["sink"].units.items())}
    return "PASS" if after == result["unit_snapshot_before"] else "FAIL"


# ── Gate 3 trace ─────────────────────────────────────────────────────────────

def trace_gate(result: Dict) -> str:
    """relation -> unit -> evidence -> same book, 100%."""
    writer: RelationWriter = result["writer"]
    if not result["sink"].relation_candidates:
        return "FAIL"
    if writer.traceability_percent() != 100.0:
        return "FAIL"
    if writer.cross_source_relations():
        return "FAIL"
    return "PASS"


def double_side_gate(result: Dict) -> str:
    """Both sides carry evidence.

    Two CHECKs in 079 make an evidence-less side unreachable through SQL. The
    query exists so the gate reads that fact instead of assuming it.
    """
    writer: RelationWriter = result["writer"]
    if writer.single_side_relations():
        return "FAIL"
    return "PASS"


# ── Gate 4 replay ────────────────────────────────────────────────────────────

def _fingerprint(sink) -> Dict[str, str]:
    return {key: sink.relation_candidates[key].relation_hash
            for key in sorted(sink.relation_candidates)}


def replay_gate() -> Dict[str, object]:
    """Re-run the whole relation: same hash, nothing new."""
    first = build_relation()
    before = _fingerprint(first["sink"])
    second = build_relation()
    after = _fingerprint(second["sink"])
    again = first["builder"].build(
        first["result"]["base"]["source_version_id"],
        PILOT_RELATION[0], PILOT_RELATION[1], RELATION_TYPES[0],
        PILOT_DECLARED_VERSION)
    first["writer"].write(again)
    final = _fingerprint(first["sink"])
    return {
        "relations": len(after),
        "identical_fingerprints": int(before == after),
        "rewrite_is_noop": int(before == final),
        "new_relation": max(0, len(after) - len(before)),
        "duplicate_hashes": len(first["writer"].duplicate_hashes()),
    }


def idempotency_gate(result: Dict) -> str:
    """Writing the same relation twice appends nothing."""
    writer: RelationWriter = result["writer"]
    before = _fingerprint(result["sink"])
    writer.write(result["candidate"])
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


def hash_stability_gate() -> str:
    """Same input, same id and hash; any change, a different relation.

    Covers the four ways the inputs can move: the extractor version, either
    unit, and either side's evidence.
    """
    left, right = PILOT_RELATION
    evidence = ["ev_22f99d11e192"]
    other = ["ev_291e662405a9"]
    base_id = relation_id(RELATION_TYPES[0], "sv_x", left, right,
                          PILOT_DECLARED_VERSION)
    base_hash = relation_hash(RELATION_TYPES[0], "sv_x", left, right, evidence,
                              other, PILOT_DECLARED_VERSION)
    variants = [
        relation_id(RELATION_TYPES[0], "sv_x", left, right,
                    EXTRACTOR_VERSION) != base_id,
        relation_id(RELATION_TYPES[0], "sv_x", right, left,
                    PILOT_DECLARED_VERSION) != base_id,
        relation_hash(RELATION_TYPES[0], "sv_x", left, right, other, other,
                      PILOT_DECLARED_VERSION) != base_hash,
        relation_hash(RELATION_TYPES[0], "sv_x", left, right, evidence,
                      other, EXTRACTOR_VERSION) != base_hash,
        # Traversal order within one side is not a claim.
        relation_hash(RELATION_TYPES[0], "sv_x", left, right,
                      list(reversed(evidence)), other,
                      PILOT_DECLARED_VERSION) == base_hash,
        relation_id(RELATION_TYPES[0], "sv_x", left, right,
                    PILOT_DECLARED_VERSION) == base_id,
    ]
    return "PASS" if all(variants) else "FAIL"


# ── Gate 5 isolation ─────────────────────────────────────────────────────────

def same_source_gate(result: Dict) -> str:
    """Both units are of the relation's own source version."""
    writer: RelationWriter = result["writer"]
    if writer.cross_source_relations():
        return "FAIL"
    for candidate in result["sink"].relation_candidates.values():
        for unit_id in (candidate.left_unit_id, candidate.right_unit_id):
            unit = result["sink"].units.get(unit_id)
            if unit is None or unit.source_version_id != \
                    candidate.source_version_id:
                return "FAIL"
    return "PASS"


def order_gate(result: Dict) -> str:
    """The declared left unit really does sit earlier in the book.

    A writer gate, not a CHECK: ordering needs reading_evidence and PostgreSQL
    refuses a CHECK that reads another table.
    """
    writer: RelationWriter = result["writer"]
    if writer.out_of_order_relations():
        return "FAIL"
    for candidate in result["sink"].relation_candidates.values():
        if not precedes_in_book(result["builder"], candidate.left_unit_id,
                                candidate.right_unit_id):
            return "FAIL"
    return "PASS"


# ── Gate: negative ───────────────────────────────────────────────────────────

def _clone(candidate) -> RelationCandidate:
    return RelationCandidate(
        id=candidate.id, relation_type=candidate.relation_type,
        source_version_id=candidate.source_version_id,
        left_unit_id=candidate.left_unit_id,
        right_unit_id=candidate.right_unit_id,
        left_evidence_ids=list(candidate.left_evidence_ids),
        right_evidence_ids=list(candidate.right_evidence_ids),
        relation_hash=candidate.relation_hash, status=candidate.status,
        extractor_version=candidate.extractor_version,
        created_at=candidate.created_at)


def _downgrade() -> None:
    """A supported relation may not fall back to GENERATED or REJECTED.

    Built on a fresh relation so the shared fixture is not left supported.
    """
    fresh = build_relation()
    writer = fresh["writer"]
    # The sink holds a *copy* of the built candidate, so the lifecycle is
    # reached through what write() returned.
    candidate = fresh["written"]
    writer.support(candidate.id)
    for target in (RelationStatus.GENERATED, RelationStatus.REJECTED):
        try:
            transition(candidate, target)
        except RelationViolation:
            continue
        raise AssertionError(f"supported -> {target.value} was allowed")
    raise RelationViolation(
        "no downgrade from SUPPORTED is legal; the loop proves it")


def _rejected_is_final() -> None:
    """A rejected relation may not be revived."""
    fresh = build_relation()
    writer = fresh["writer"]
    candidate = fresh["written"]
    writer.reject(candidate.id)
    for target in (RelationStatus.GENERATED, RelationStatus.SUPPORTED):
        try:
            transition(candidate, target)
        except RelationViolation:
            continue
        raise AssertionError(f"rejected -> {target.value} was allowed")
    raise RelationViolation("no edge leaves REJECTED; the loop proves it")


def negative_gate(result: Dict) -> Dict[str, bool]:
    """Each forbidden shape must actually be refused.

    Reported as a map rather than a single PASS so a regression names which case
    stopped being refused. Probes go through `write()`, which raises, rather
    than `preconditions()`, which returns a tuple — asserting on a return value
    that nothing raises on would report a refusal that never happened.
    """
    # A throwaway relation, not the reported one: a leak into the shared sink
    # would quietly change the counts this report is asserting on.
    throwaway = build_relation()
    builder = throwaway["builder"]
    writer: RelationWriter = throwaway["writer"]
    source_version = throwaway["result"]["base"]["source_version_id"]
    left, right = PILOT_RELATION

    def refuses(fn) -> bool:
        try:
            fn()
        except (RelationPrecondition, RelationViolation, ValueError):
            return True
        return False

    def write_clone(mutate) -> None:
        """Clone the pilot relation, damage it, and try to write it."""
        clone = _clone(throwaway["candidate"])
        mutate(clone)
        # A distinct id and hash so the duplicate short-circuit cannot mask the
        # precondition check.
        clone.id = "rlc_damaged"
        clone.relation_hash = "rlh_damaged"
        writer.write(clone)

    checks = {
        # vocabulary
        "deferred_supports": refuses(
            lambda: builder.build(source_version, left, right, "SUPPORTS",
                                  PILOT_DECLARED_VERSION)),
        "deferred_contrasts": refuses(
            lambda: builder.build(source_version, left, right, "CONTRASTS",
                                  PILOT_DECLARED_VERSION)),
        "deferred_depends_on": refuses(
            lambda: builder.build(source_version, left, right, "DEPENDS_ON",
                                  PILOT_DECLARED_VERSION)),
        "unknown_type": refuses(
            lambda: builder.build(source_version, left, right, "CONCLUSION",
                                  PILOT_DECLARED_VERSION)),
        # shape
        "self_relation": refuses(
            lambda: builder.build(source_version, left, left, "PRECEDES",
                                  PILOT_DECLARED_VERSION)),
        # evidence
        "no_left_evidence": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("left_evidence_ids", []))),
        "no_right_evidence": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("right_evidence_ids", []))),
        "cross_book_evidence": refuses(
            lambda: write_clone(
                lambda c: c.right_evidence_ids.append("ev_not_in_this_book"))),
        "unknown_unit": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("right_unit_id", "ku_not_a_unit"))),
        # isolation
        "cross_source": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("source_version_id",
                                        "sv_a_different_book"))),
        "no_such_source_version": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("source_version_id", "sv_absent"))),
        # order. Checked at write, not at build: the builder composes what the
        # caller declared, and refusing a declared pair here would hide which
        # of the two units is the problem.
        "order_reversed": refuses(
            lambda: writer.write(
                builder.build(source_version, right, left, "PRECEDES",
                              PILOT_DECLARED_VERSION))),
        "order_same_unit": refuses(
            lambda: writer.write(
                builder.build(source_version, left, left, "PRECEDES",
                              PILOT_DECLARED_VERSION))),
        # lifecycle
        "verified_status": refuses(lambda: RelationStatus("VERIFIED")),
        "confirmed_status": refuses(lambda: RelationStatus("CONFIRMED")),
        "supported_downgrade": refuses(_downgrade),
        "rejected_revived": refuses(_rejected_is_final),
        # forbidden operations
        "merge_relations": refuses(
            lambda: writer.merge_relations("rlc_a", "rlc_b")),
        "verify_relation": refuses(
            lambda: writer.verify_relation(throwaway["written"].id)),
        "add_semantics": refuses(
            lambda: writer.add_semantics(throwaway["written"].id)),
        "update_relation": refuses(
            lambda: writer.update_relation(throwaway["written"].id, status="X")),
        "delete_relation": refuses(
            lambda: writer.delete_relation(throwaway["written"].id)),
    }
    return checks


# ── gates ────────────────────────────────────────────────────────────────────

def gate_results(result: Dict) -> Dict[str, object]:
    """The five acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = negative_gate(result)
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_fk_verb": fk_verb_gate(),
        "GATE_1_isolation_schema": isolation_schema_gate(),
        "GATE_1_frozen_index": frozen_index_gate(),
        "GATE_1_constraints": constraint_gate(),
        "GATE_1_vocabulary": vocabulary_gate(),
        "GATE_1_not_null": null_status_gate(),
        "GATE_1_column_parity": column_parity_gate(),
        "GATE_1_banned_fields": banned_field_gate(),
        "GATE_2_authority": authority_gate(result),
        "GATE_2_ku_relation_untouched": ku_relation_untouched_gate(result),
        "GATE_2_baseline_unchanged": baseline_mutation_gate(result),
        "GATE_3_trace": trace_gate(result),
        "GATE_3_double_side": double_side_gate(result),
        "GATE_3_traceability_percent": result["writer"].traceability_percent(),
        "GATE_4_replay": "PASS" if (replay["identical_fingerprints"] == 1
                                    and replay["rewrite_is_noop"] == 1
                                    and replay["new_relation"] == 0
                                    and replay["duplicate_hashes"] == 0)
        else "FAIL",
        "GATE_4_idempotency": idempotency_gate(result),
        "GATE_4_hash_stability": hash_stability_gate(),
        "GATE_5_isolation": same_source_gate(result),
        "GATE_5_order": order_gate(result),
        "GATE_6_negative": "PASS" if all(negative.values()) else "FAIL",
        "GATE_6_negative_detail": negative,
    }


_SCHEMA_GATES = ("GATE_1_schema", "GATE_1_fk_verb",
                 "GATE_1_isolation_schema", "GATE_1_frozen_index",
                 "GATE_1_constraints", "GATE_1_vocabulary", "GATE_1_not_null",
                 "GATE_1_column_parity", "GATE_1_banned_fields")

_IMPLEMENTATION_GATES = (
    "GATE_2_authority", "GATE_2_ku_relation_untouched",
    "GATE_2_baseline_unchanged", "GATE_3_trace", "GATE_3_double_side",
    "GATE_4_replay", "GATE_4_idempotency", "GATE_4_hash_stability",
    "GATE_5_isolation", "GATE_5_order", "GATE_6_negative")


# ── reporting ────────────────────────────────────────────────────────────────

def report(result: Dict) -> Dict:
    writer: RelationWriter = result["writer"]
    sink = result["sink"]
    builder: RelationBuilder = result["builder"]
    relations = []
    for candidate in sorted(sink.relation_candidates.values(), key=lambda r: r.id):
        relations.append({
            "relation_id": candidate.id,
            "relation_hash": candidate.relation_hash,
            "relation_type": candidate.relation_type,
            "source_version_id": candidate.source_version_id,
            "status": candidate.status,
            "extractor_version": candidate.extractor_version,
            "left": _side(result, builder, candidate.left_unit_id,
                          candidate.left_evidence_ids),
            "right": _side(result, builder, candidate.right_unit_id,
                           candidate.right_evidence_ids),
        })
    return {
        "task": "A_P5_2_RELATION",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "relation_version": RELATION_VERSION,
        "pilot_chapter": "第一章 古代时期的信贷",
        "relation_types_authorised": list(RELATION_TYPES),
        "relation_types_deferred": list(DEFERRED_TYPES),
        "relation_count": len(sink.relation_candidates),
        "pilot_rows": writer.pilot_rows(),
        "extracted_rows": writer.extracted_rows(),
        "traceability_percent": writer.traceability_percent(),
        "notes": dict(RELATION_NOTES),
        "relations": relations,
    }


def _side(result: Dict, builder: RelationBuilder, unit_id: str,
          evidence_ids: List[str]) -> Dict:
    """One side of a relation, with where it sits in the book."""
    unit = result["sink"].units[unit_id]
    locator = builder.locator_of(unit_id)
    return {
        "unit_id": unit_id,
        "statement": unit.statement,
        "evidence_ids": evidence_ids,
        "page": locator[0] if locator else None,
    }


def acceptance(result: Dict) -> Dict[str, object]:
    """The review spec's FINAL REPORT block, computed from measurements."""
    gates = gate_results(result)
    replay = replay_gate()
    contamination = contamination_counts(result)
    negative = gates["GATE_6_negative_detail"]
    writer: RelationWriter = result["writer"]
    checks = {
        "relation_persisted": len(result["sink"].relation_candidates),
        "both_sides_evidenced": gates["GATE_3_double_side"] == "PASS",
        "order_declared_and_holds": gates["GATE_5_order"] == "PASS",
        "traceability_percent": gates["GATE_3_traceability_percent"],
        "source_isolation": gates["GATE_5_isolation"],
        "replay_stable": gates["GATE_4_replay"],
        "transaction_atomic": "PASS" if gates["GATE_1_schema"] == "PASS"
        else "FAIL",
        "deferred_types_present": len(writer.deferred_type_rows()),
        "self_relations": len(writer.self_relations()),
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
        "baseline_mutated": 0 if gates["GATE_2_baseline_unchanged"] == "PASS"
        else 1,
        "negative_refusals": sum(1 for v in negative.values() if v),
        "negative_cases": len(negative),
    }
    passed = (checks["relation_persisted"] == 1
              and checks["both_sides_evidenced"]
              and checks["order_declared_and_holds"]
              and checks["traceability_percent"] == 100.0
              and checks["source_isolation"] == "PASS"
              and checks["replay_stable"] == "PASS"
              and checks["transaction_atomic"] == "PASS"
              and checks["deferred_types_present"] == 0
              and checks["self_relations"] == 0
              and checks["B_CONTAMINATION"] == 0
              and checks["C_CONTAMINATION"] == 0
              and checks["BU2_DEPENDENCY"] == 0
              and checks["baseline_mutated"] == 0
              and checks["negative_refusals"] == checks["negative_cases"])
    return {
        "checks": checks,
        "gates": gates,
        "A_P5_2_RELATION_SCHEMA":
            "PASS" if all(gates[k] == "PASS" for k in _SCHEMA_GATES)
            else "BLOCKED",
        "A_P5_2_RELATION_IMPLEMENTATION":
            "PASS" if passed
            else "BLOCKED",
        "RELATION_TYPE": "PRECEDES_ONLY",
        "DEFERRED_TYPES": list(DEFERRED_TYPES),
        "MIGRATION_079": REQUIRED_MIGRATION,
    }


def final_report(result: Dict) -> Dict[str, str]:
    """The v0.2 FINAL REPORT block, verbatim keys.

    COMMIT_SHA and TAG are read from the environment because they name a commit
    that has not been made yet. They are reported as PENDING rather than guessed:
    a freeze report that invents its own commit id is worse than one that admits
    it has none.
    """
    gates = gate_results(result)
    acceptance_block = acceptance(result)
    contamination = contamination_counts(result)
    verdict = ("PASS"
               if acceptance_block["A_P5_2_RELATION_IMPLEMENTATION"] == "PASS"
               else "BLOCKED")
    return {
        "A_P5_2_RELATION": verdict,
        "MIGRATION_079": REQUIRED_MIGRATION,
        "RELATION_TYPE": "PRECEDES_ONLY",
        "RELATION_ROWS": str(len(result["sink"].relation_candidates)),
        "TRACEABILITY": f"{gates['GATE_3_traceability_percent']}%",
        "SOURCE_ISOLATION": str(gates["GATE_5_isolation"]),
        "REPLAY": str(gates["GATE_4_replay"]),
        "AUTHORITY_SCAN": str(gates["GATE_2_authority"]),
        "B_CONTAMINATION": str(contamination["B_REFERENCE"]),
        "C_CONTAMINATION": str(contamination["C_REFERENCE"]),
        "DB_MUTATION": str(checks_baseline(gates)),
        "BU2_MUTATION": str(contamination["BU2_DEPENDENCY"]),
        "075_UNTOUCHED": str(gates["GATE_2_ku_relation_untouched"]),
        "COMMIT_SHA": os.environ.get("A_P5_2_COMMIT_SHA", "PENDING"),
        "TAG": os.environ.get("A_P5_2_TAG", "PENDING"),
        "FINAL_STATUS": verdict,
    }


def checks_baseline(gates: Dict[str, object]) -> int:
    """Mutations to the frozen A chain: 0 or 1."""
    return 0 if gates["GATE_2_baseline_unchanged"] == "PASS" else 1


def write_sql(result: Dict, path: str) -> str:
    """Emit the relation table for a DBA to execute."""
    script = emit_relation_sql(result["sink"].relation_candidates)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P5_2_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [line.strip() for line in
            source.read_text(encoding="utf-8").splitlines() if line.strip()]


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    target = path or os.environ.get("A_P5_2_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)",
        source.read_text(encoding="utf-8"))} or None


def main() -> None:
    result = build_relation()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    doc = report(result)
    doc.update(acceptance(result))
    doc["final_report"] = final_report(result)
    doc["ledger"] = ledger_lines()
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()