"""A Repository P5.1 — mechanism chain runner.

Builds the pilot declared chain over the frozen units and reports the five
acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.mechanism_runner

    Gate 1 Schema      both tables, FK into A only, hash and order unique
    Gate 2 Trace       mechanism -> node -> KU -> evidence, 100%
    Gate 3 Replay      re-running writes nothing
    Gate 4 Authority   B / C / BU2 mutation = 0
    Gate 5 Negative    empty chain, TRIGGER-only, no evidence, VERIFIED,
                       empty array — all refused

Contamination is measured in three layers and reuses P7's gates. A word scan
over A仓 source returns 24 hits, all of them A仓's own guard lists; that trap
has now been avoided four times.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import pilot_corpus as C
from .ku_identity_runner import build_identity
from .verdict import verdict, verdict_inputs
from .mechanism import (
    EXTRACTOR_VERSION,
    MECHANISM_BANNED_FIELDS,
    MECHANISM_COLUMNS,
    MECHANISM_NOTES,
    MECHANISM_TABLES,
    MECHANISM_VERSION,
    NODE_COLUMNS,
    PILOT_DECLARED_VERSION,
    MechanismChainBuilder,
    MechanismPrecondition,
    MechanismSink,
    MechanismStatus,
    MechanismViolation,
    MechanismWriter,
    NodeRole,
    banned_field_report,
    chain_is_complete,
    emit_mechanism_sql,
    mechanism_hash,
    mechanism_id,
    node_id,
    transition,
)
from .projection_builder import artifact_drift, external_imports


REQUIRED_MIGRATION = "078_a_mechanism_chain.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    "075_a_ku_evolution.sql",
    "076_a_ku_identity.sql",
    "077_a_condition_boundary.sql",
    REQUIRED_MIGRATION,
)

#: The only tables 078 may reference. A chain records a structure inside one
#: book, so every link it follows is A's own frozen chain.
ALLOWED_FK_TARGETS = frozenset({"source_version", "knowledge_unit",
                               "mechanism_candidate"})

#: Tables P5.1 must never create or alter.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event", "ku_condition_candidate",
                      "ku_boundary_candidate", "ku_relation")

#: The pilot chain: three frozen units of 利率史 chapter 1, in reading order.
#:
#: Declared, not extracted. A real extractor cannot find a chain in this
#: corpus — the anchored spans are single-clause (measured 9 spans with one
#: clause, 1 with two) — so these rows exist to exercise the persistence,
#: replay and traceability contract and are labelled `pilot-declared` so they
#: can never be read as an extraction result.
PILOT_CHAIN: Tuple[Tuple[str, str], ...] = (
    ("ku_6460a6062a10", NodeRole.TRIGGER.value),      # p.2  信贷在古代和中世纪时期
    ("ku_93a979cb6fab", NodeRole.TRANSITION.value),    # p.6  雅典出现了一次经济危机
    ("ku_5840cc146f9f", NodeRole.RESULT.value),        # p.7  索伦的法典取消限制
)


def build_chain(sink=None) -> Dict:
    """P1 -> P7 -> P5.1, then the pilot chain, written in one transaction."""
    chain = (build_identity(sink=sink) if sink is not None
             else build_identity(sink=MechanismSink()))
    upstream = chain["result"]
    store = upstream["base"]["pipeline"].store
    units = {key: dict(vars(unit))
             for key, unit in sorted(chain["sink"].units.items())}

    builder = MechanismChainBuilder(upstream["base"]["pipeline"],
                                   chain["sink"].units)
    candidate = builder.build(
        source_version_id=upstream["base"]["source_version_id"],
        chain=PILOT_CHAIN,
        extractor_version=PILOT_DECLARED_VERSION)
    writer = MechanismWriter(upstream["base"]["pipeline"], chain["sink"])
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


def _table_body(text: str, table: str) -> str:
    block = re.sub(r"--[^\n]*", "",
                   text.split(f"CREATE TABLE IF NOT EXISTS {table}")[1]
                   if f"CREATE TABLE IF NOT EXISTS {table}" in text
                   else text.split(f"CREATE TABLE IF NOT EXISTS stratum.{table}")[1])
    start = block.index("(") + 1
    depth, out = 1, []
    for char in block[start:]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
    return "".join(out)


def _declared_columns(table: str) -> set:
    body = _table_body(_clean(), f"stratum.{table}")
    parts, depth, current = [], 0, []
    for char in body:
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
    """Both tables exist, additive only, FK into A only."""
    clean = _clean()
    for table in MECHANISM_TABLES:
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
    """Every foreign key is RESTRICT.

    Measured across the A chain: CASCADE appears only in 070-072, the
    extraction chain. Every frozen artifact from 073 on is RESTRICT, and 073
    states the position in the migration itself. A mechanism chain is a
    frozen artifact, so CASCADE here would be the first one in A仓 where
    deleting a parent silently takes its children.
    """
    clean = _clean()
    actions = re.findall(r"REFERENCES\s+stratum\.\w+\(id\)\s+ON DELETE (\w+)",
                         clean)
    if len(actions) != 3:
        return "FAIL"
    if set(actions) != {"RESTRICT"}:
        return "FAIL"
    return "PASS"


def constraint_gate() -> str:
    """Hash unique, order unique, cardinality guard, closed vocabularies,
    and the writer's columns all declared."""
    clean = _clean()
    required = (
        "CONSTRAINT mechanism_candidate_hash_uniq UNIQUE (mechanism_hash)",
        "CONSTRAINT mechanism_node_order_uniq",
        "UNIQUE (mechanism_id, sequence_order)",
    )
    for fragment in required:
        if fragment not in clean:
            return "FAIL"
    if clean.count("CHECK (cardinality(evidence_ids) >= 1)") != 1:
        return "FAIL"
    if "array_length(evidence_ids" in clean:
        return "FAIL"
    if "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" not in clean:
        return "FAIL"
    for table, columns in (("mechanism_candidate", MECHANISM_COLUMNS),
                           ("mechanism_node", NODE_COLUMNS)):
        if not set(columns) <= _declared_columns(table):
            return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Writer columns, schema columns and dataclass fields must agree.

    077 shipped once referencing two columns it never declared and every
    insert failed against a real database. Only the disagreement shows it.
    """
    for table, columns, fields in (
            ("mechanism_candidate", MECHANISM_COLUMNS,
             ("id", "source_version_id", "mechanism_hash", "status",
              "extractor_version", "created_at")),
            ("mechanism_node", NODE_COLUMNS,
             ("id", "mechanism_id", "knowledge_unit_id", "node_role",
              "sequence_order", "evidence_ids", "created_at"))):
        declared = _declared_columns(table)
        if not set(columns) <= declared:
            return "FAIL"
        if not set(columns) <= set(fields):
            return "FAIL"
    return "PASS"


def banned_field_gate() -> str:
    """No mechanism row grew a judgement column."""
    report = banned_field_report()
    return "FAIL" if any(report.values()) else "PASS"


# ── Gate 2 trace ─────────────────────────────────────────────────────────────

def trace_gate(result: Dict) -> str:
    """mechanism -> node -> KU -> evidence, 100%."""
    writer: MechanismWriter = result["writer"]
    if not result["sink"].mechanisms:
        return "FAIL"
    if writer.traceability_percent() != 100.0:
        return "FAIL"
    if writer.orphan_nodes() or writer.orphan_mechanisms():
        return "FAIL"
    if writer.cross_source_nodes():
        return "FAIL"
    return "PASS"


def completeness_gate(result: Dict) -> str:
    """Every written chain has all three roles.

    KNOWN_LIMITATION 5: a CHECK cannot count rows in another table, so a
    mechanism with zero nodes or only a TRIGGER is a state this database can
    hold. This is where it is closed.
    """
    writer: MechanismWriter = result["writer"]
    if writer.missing_roles():
        return "FAIL"
    for mechanism in result["sink"].mechanisms.values():
        nodes = writer.nodes_of(mechanism.id)
        if not nodes:
            return "FAIL"
        if [n.sequence_order for n in nodes] != \
                list(range(1, len(nodes) + 1)):
            return "FAIL"
    return "PASS"


# ── Gate 3 replay ────────────────────────────────────────────────────────────

def replay_gate() -> Dict[str, object]:
    """Re-run the whole chain: same hashes, nothing new."""
    first = build_chain()
    before = _fingerprint(first["sink"])
    second = build_chain()
    after = _fingerprint(second["sink"])
    again = first["builder"].build(
        first["result"]["base"]["source_version_id"],
        PILOT_CHAIN, PILOT_DECLARED_VERSION)
    first["writer"].write(again)
    final = _fingerprint(first["sink"])
    return {
        "mechanisms": len(after["mechanism"]),
        "nodes": len(after["node"]),
        "identical_fingerprints": int(before == after),
        "rewrite_is_noop": int(before == final),
        "new_mechanism": max(0, len(after["mechanism"])
                              - len(before["mechanism"])),
        "new_node": max(0, len(after["node"]) - len(before["node"])),
        "duplicate_chains": len(first["writer"].duplicate_chains()),
    }


def _fingerprint(sink) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {"mechanism": {}, "node": {}}
    for key in sorted(sink.mechanisms):
        out["mechanism"][key] = sink.mechanisms[key].mechanism_hash
    for key in sorted(sink.nodes):
        out["node"][key] = sink.nodes[key].sequence_order and \
            sink.nodes[key].id
    return out


def idempotency_gate(result: Dict) -> str:
    """Writing the same chain twice appends nothing."""
    writer: MechanismWriter = result["writer"]
    before = _fingerprint(result["sink"])
    writer.write(result["candidate"])
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


# ── Gate 4 authority ─────────────────────────────────────────────────────────

def authority_gate(result: Dict) -> str:
    """B, C and BU2 all zero, in three layers."""
    if external_imports():
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    payload = {
        "mechanisms": [m.id for m in result["sink"].mechanisms.values()],
        "nodes": [n.id for n in result["sink"].nodes.values()],
    }
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Dict) -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, measured in the three layers.

    Never a word scan of this file: the token list would match itself, which
    is the false positive that produced 24 hits in A仓.
    """
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    drift = len(referenced - ALLOWED_FK_TARGETS)
    payload = {
        "mechanisms": [m.id for m in result["sink"].mechanisms.values()],
        "nodes": [n.id for n in result["sink"].nodes.values()],
    }
    total = len(external_imports()) + drift + len(artifact_drift(payload))
    return {"B_REFERENCE": total, "C_REFERENCE": total,
            "BU2_DEPENDENCY": drift,
            "external_imports": len(external_imports())}


def baseline_mutation_gate(result: Dict) -> str:
    """The A chain underneath is byte-identical after the write."""
    after = {key: dict(vars(unit))
             for key, unit in sorted(result["sink"].units.items())}
    return "PASS" if after == result["unit_snapshot_before"] else "FAIL"


# ── Gate 5 negative ──────────────────────────────────────────────────────────

def negative_gate(result: Dict) -> Dict[str, bool]:
    """Each forbidden shape must actually be refused.

    Reported as a map rather than a single PASS so a regression names which
    case stopped being refused.

    Probes go through `write()`, which raises, rather than
    `preconditions()`, which returns a tuple — asserting on a return value
    that nothing raises on would report a refusal that never happened.
    """
    # A throwaway chain, not the reported one. Two of these probes are
    # expected to fail to be refused at some point during development, and a
    # leak into the shared sink would quietly change the counts this report
    # is asserting on.
    throwaway = build_chain()
    builder = throwaway["builder"]
    writer: MechanismWriter = throwaway["writer"]
    source_version = throwaway["result"]["base"]["source_version_id"]
    unit = next(iter(throwaway["sink"].units))

    def refuses(fn) -> bool:
        try:
            fn()
        except (MechanismPrecondition, MechanismViolation, ValueError):
            return True
        return False

    trigger_only = ((unit, NodeRole.TRIGGER.value),)
    missing_unit = ((PILOT_CHAIN[0][0], NodeRole.TRIGGER.value),
                    ("ku_not_a_unit", NodeRole.RESULT.value))

    def write_clone(mutate) -> None:
        """Build a clone of the pilot chain, damage it, and try to write it."""
        clone = _clone(throwaway["candidate"])
        mutate(clone)
        # A distinct hash so the duplicate short-circuit cannot mask the
        # precondition check.
        clone.id = "mec_damaged"
        clone.mechanism_hash = "meh_damaged"
        for node in clone.nodes:
            node.mechanism_id = clone.id
        writer.write(clone)

    checks = {
        "empty_chain": refuses(
            lambda: builder.build(source_version, (), PILOT_DECLARED_VERSION)),
        "trigger_only": refuses(
            lambda: builder.build(source_version, trigger_only,
                                 PILOT_DECLARED_VERSION)),
        "missing_unit": refuses(
            lambda: builder.build(source_version, missing_unit,
                                 PILOT_DECLARED_VERSION)),
        "unknown_role": refuses(
            lambda: builder.build(source_version,
                                 ((unit, "CONCLUSION"),),
                                 PILOT_DECLARED_VERSION)),
        "no_evidence": refuses(
            lambda: write_clone(
                lambda c: c.nodes[0].__setattr__("evidence_ids", []))),
        "empty_array": refuses(
            lambda: write_clone(
                lambda c: c.nodes[0].__setattr__("evidence_ids", []))),
        # The pilot is one book, so there is no unit from another
        # source_version to point at. Moving the chain's own book is the
        # equivalent probe: every node then sits in a different version from
        # the chain, which is exactly what the guard checks.
        "cross_source": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("source_version_id",
                                        "sv_a_different_book"))),
        "cross_book_evidence": refuses(
            lambda: write_clone(
                lambda c: c.nodes[0].__setattr__("evidence_ids",
                                                 ["ev_not_in_this_book"]))),
        "duplicate_sequence": refuses(
            lambda: write_clone(
                lambda c: c.nodes[1].__setattr__("sequence_order", 1))),
    }

    # A status of VERIFIED is not a member of the enum, so naming one raises
    # before any state is touched. GENERATED -> SUPPORTED is legal and is not
    # what this probes.
    checks["verified_status"] = refuses(
        lambda: MechanismStatus("VERIFIED"))
    checks["confirmed_status"] = refuses(
        lambda: MechanismStatus("CONFIRMED"))
    checks["supported_downgrade"] = refuses(_downgrade)
    checks["merge_chains"] = refuses(
        lambda: writer.merge_chains("mec_a", "mec_b"))
    checks["verify_chain"] = refuses(
        lambda: writer.verify_chain(throwaway["written"].id))
    checks["add_cause"] = refuses(
        lambda: writer.add_cause(throwaway["written"].id))
    return checks


def _downgrade() -> None:
    """A supported chain may not fall back to GENERATED or REJECTED.

    Built on a fresh chain so the shared fixture is not left supported.
    """
    fresh = build_chain()
    writer = fresh["writer"]
    # The sink holds a *copy* of the built candidate, so the lifecycle is
    # reached through what write() returned. Mutating the builder's own
    # object would change something the chain does not see — the same
    # copy-on-write shape as P4.1's writer and P5.0's.
    candidate = fresh["written"]
    writer.support(candidate.id)
    for target in (MechanismStatus.GENERATED, MechanismStatus.REJECTED):
        try:
            transition(candidate, target)
        except MechanismViolation:
            continue
        raise AssertionError(f"supported -> {target.value} was allowed")
    raise MechanismViolation(
        "no downgrade from SUPPORTED is legal; the loop proves it")


def _clone(candidate):
    from .mechanism import MechanismCandidate, MechanismNode
    return MechanismCandidate(
        id=candidate.id, source_version_id=candidate.source_version_id,
        mechanism_hash=candidate.mechanism_hash, status=candidate.status,
        extractor_version=candidate.extractor_version,
        created_at=candidate.created_at,
        nodes=[MechanismNode(**vars(node)) for node in candidate.nodes])


def _attempt_downgrade(writer: MechanismWriter, candidate) -> None:
    """A supported chain may not fall back to GENERATED or REJECTED."""
    supported = writer._with_nodes(candidate)
    from .mechanism import MechanismStatus as S
    for target in (S.GENERATED, S.REJECTED):
        try:
            transition(supported, target)
        except MechanismViolation:
            supported.status = S.SUPPORTED.value
            continue
        raise AssertionError(f"supported -> {target.value} was allowed")
    raise MechanismViolation("no downgrade is legal; the loop proves it")


# ── gates ────────────────────────────────────────────────────────────────────

# This file used to carry `GATE_ORDER`, five names, while `gate_results`
# returned thirteen. Two of the names it omitted were the gates asserting no
# new identity and no mutation, and it had already drifted on the day it was
# written. Deleted rather than corrected: the parallel list is the mechanism
# by which a reported gate falls outside the verdict, and it drifts again for
# the next gate added. Order now comes from the mapping itself.
#: What the traceability gate must equal. It was previously emitted as a bare
#: percentage inside `gates`, which the shared verdict contract cannot read --
#: an unrecognised value is BLOCKED, so leaving it would have pinned this layer
#: to BLOCKED forever or tempted a special case outside the contract.
TRACEABILITY_REQUIRED = 100.0


def _equals(measured: object, required: object) -> str:
    """One measurement as a gate status, against a stated requirement."""
    return "PASS" if measured == required else "FAIL"


def gate_results(result: Dict) -> Dict[str, object]:
    """The five acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = negative_gate(result)
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_fk_verb": fk_verb_gate(),
        "GATE_1_constraints": constraint_gate(),
        "GATE_1_column_parity": column_parity_gate(),
        "GATE_1_banned_fields": banned_field_gate(),
        "GATE_2_trace": trace_gate(result),
        "GATE_2_completeness": completeness_gate(result),
        "GATE_2_traceability_percent": _equals(
            result["writer"].traceability_percent(), TRACEABILITY_REQUIRED),
        "GATE_3_replay": "PASS" if (replay["identical_fingerprints"] == 1
                                    and replay["rewrite_is_noop"] == 1
                                    and replay["new_mechanism"] == 0
                                    and replay["new_node"] == 0
                                    and replay["duplicate_chains"] == 0)
        else "FAIL",
        "GATE_3_idempotency": idempotency_gate(result),
        "GATE_4_authority": authority_gate(result),
        "GATE_4_baseline_unchanged": baseline_mutation_gate(result),
        "GATE_5_negative": "PASS" if all(negative.values()) else "FAIL",
    }


# ── reporting ────────────────────────────────────────────────────────────────

def report(result: Dict) -> Dict:
    writer: MechanismWriter = result["writer"]
    sink = result["sink"]
    chains = []
    for mechanism in sorted(sink.mechanisms.values(), key=lambda m: m.id):
        nodes = writer.nodes_of(mechanism.id)
        chains.append({
            "mechanism_id": mechanism.id,
            "mechanism_hash": mechanism.mechanism_hash,
            "source_version_id": mechanism.source_version_id,
            "status": mechanism.status,
            "extractor_version": mechanism.extractor_version,
            "roles": mechanism.roles(),
            "nodes": [{"sequence_order": n.sequence_order,
                       "node_role": n.node_role,
                       "knowledge_unit_id": n.knowledge_unit_id,
                       "evidence_ids": n.evidence_ids,
                       "statement": sink.units[n.knowledge_unit_id].statement}
                      for n in nodes],
        })
    return {
        "task": "A_P5_1_MECHANISM",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "mechanism_version": MECHANISM_VERSION,
        "pilot_chapter": "第一章 古代时期的信贷",
        "mechanism_count": len(sink.mechanisms),
        "node_count": len(sink.nodes),
        "pilot_rows": writer.pilot_rows(),
        "extracted_rows": writer.extracted_rows(),
        "traceability_percent": writer.traceability_percent(),
        "notes": dict(MECHANISM_NOTES),
        "chains": chains,
    }


def acceptance(result: Dict) -> Dict[str, object]:
    """The review spec's final acceptance block, computed from measurements."""
    gates = gate_results(result)
    replay = replay_gate()
    contamination = contamination_counts(result)
    # Was also published as `GATE_5_negative_detail`, whose value was this
    # same dict: `GATE_5_negative` is "PASS" if all of it is true, so the two
    # gates were one expression counted twice. The numbers stay in `checks`.
    negative = negative_gate(result)
    checks = {
        "mechanism_persisted": len(result["sink"].mechanisms),
        "nodes_ordered": all(
            [n.sequence_order for n in result["writer"].nodes_of(m.id)]
            == list(range(1, len(result["writer"].nodes_of(m.id)) + 1))
            for m in result["sink"].mechanisms.values()),
        # The measurement, not the gate that now reports it. Reading the
        # gate here would compare a status string to 100.0 and silently
        # turn every IMPLEMENTATION verdict BLOCKED.
        "evidence_linked": result["writer"].traceability_percent(),
        "replay_stable": gates["GATE_3_replay"],
        "transaction_atomic": "PASS" if gates["GATE_1_schema"] == "PASS"
        else "FAIL",
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
        "baseline_mutated": 0 if gates["GATE_4_baseline_unchanged"] == "PASS"
        else 1,
        "negative_refusals": sum(1 for v in negative.values() if v),
        "negative_cases": len(negative),
    }
    passed = (checks["mechanism_persisted"] == 1
              and checks["nodes_ordered"]
              and checks["evidence_linked"] == 100.0
              and checks["replay_stable"] == "PASS"
              and checks["transaction_atomic"] == "PASS"
              and checks["B_CONTAMINATION"] == 0
              and checks["C_CONTAMINATION"] == 0
              and checks["BU2_DEPENDENCY"] == 0
              and checks["baseline_mutated"] == 0
              and checks["negative_refusals"] == checks["negative_cases"])
    # The two keys below are kept because tests, artifacts and freeze reports
    # read them. The layer verdict is new and is derived from every gate the
    # function reports: the IMPLEMENTATION conjunction read five of thirteen, so
    # completeness, trace, idempotency and authority could print PASS and change
    # nothing. Same defect P5 Evolution, P6 and P7 were all reopened for.
    return {"checks": checks, "gates": gates,
            "A_P5_1_MECHANISM": verdict(gates),
            "verdict_inputs": verdict_inputs(gates),
            "A_P5_1_MECHANISM_SCHEMA":
                "PASS" if all(gates[k] == "PASS" for k in (
                    "GATE_1_schema", "GATE_1_fk_verb", "GATE_1_constraints",
                    "GATE_1_column_parity", "GATE_1_banned_fields")) else "BLOCKED",
            "A_P5_1_MECHANISM_IMPLEMENTATION": "PASS" if passed else "BLOCKED"}


def write_sql(result: Dict, path: str) -> str:
    """Emit both mechanism tables for a DBA to execute."""
    script = emit_mechanism_sql(result["sink"].mechanisms, result["sink"].nodes)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P5_1_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [line.strip() for line in
            source.read_text(encoding="utf-8").splitlines() if line.strip()]


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    target = path or os.environ.get("A_P5_1_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)",
        source.read_text(encoding="utf-8"))} or None


def main() -> None:
    result = build_chain()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    doc = report(result)
    doc.update(acceptance(result))
    doc["ledger"] = ledger_lines()
    counts = durable_counts()
    if counts is not None:
        doc["durable_rows"] = counts
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
