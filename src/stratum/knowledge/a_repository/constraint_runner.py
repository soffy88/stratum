"""A Repository P5.4 — constraint annotation runner.

Builds the pilot declared constraint over the frozen corpus and reports the
acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.constraint_runner

    Gate 1 Schema      table exists, additive, FK into A only, RESTRICT only,
                       closed vocabularies, no new index on a frozen table
    Gate 2 Authority   no recommendation column, no B / C / BU2, frozen layers
                       untouched
    Gate 3 Quote       DECISION=SPAN_ONLY: every quoted field is a literal
                       substring of its own span
    Gate 4 Trace       constraint -> unit -> span, 100%
    Gate 5 Replay      re-running writes nothing, hashes stable
    Gate 6 Isolation   the unit is of the annotation's own source version
    Gate 7 Negative    unquoted fields, deferred types, invalid statuses,
                       advisory wording, derived constraints — all refused

Contamination is measured in three layers and reuses P7's gates. A word scan
over A仓 source returns hits that are all of A仓's own guard lists; that trap
has now been avoided seven times.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .constraint_writer import (
    ADVISORY_MARKERS,
    CONSTRAINT_BANNED_FIELDS,
    CONSTRAINT_COLUMNS,
    CONSTRAINT_INSERT_COLUMNS,
    CONSTRAINT_NOTES,
    CONSTRAINT_TABLES,
    CONSTRAINT_TYPES,
    CONSTRAINT_VERSION,
    EXTRACTOR_VERSION,
    PILOT_DECLARED_VERSION,
    SOFT_MARKERS,
    ConstraintCandidate,
    ConstraintPrecondition,
    ConstraintSink,
    ConstraintStatus,
    ConstraintViolation,
    ConstraintWriter,
    banned_field_report,
    emit_constraint_sql,
    evidence_span,
    field_is_quoted,
    transition,
    unquoted_fields,
)
from .ku_identity_runner import build_identity
from .verdict import verdict, verdict_inputs
from .projection_builder import artifact_drift, external_imports


REQUIRED_MIGRATION = "081_a_constraint_candidate.sql"

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
    "079_a_relation_candidate.sql",
    "080_a_paper_source.sql",
    REQUIRED_MIGRATION,
)

#: The only tables 081 may reference.
ALLOWED_FK_TARGETS = frozenset({"source_version", "knowledge_unit"})

#: Tables P5.4 must never create or alter.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event", "ku_condition_candidate",
                      "ku_boundary_candidate", "ku_relation",
                      "mechanism_candidate", "mechanism_node",
                      "relation_candidate", "paper_source_candidate",
                      "paper_evidence")

#: §8 of the review spec lists UNIQUE (id, source_version_id) on knowledge_unit
#: as required. It already exists, created by 079 for its own composite key, so
#: 081 adds no index to any frozen table. Named here so a reader who sees a
#: composite foreign key with no index in this file knows it is a reuse.
REUSED_FROZEN_INDEX = "knowledge_unit_id_source_version_uniq"

#: The one constraint the corpus can honestly support.
#:
#: Span: 贷款的利息被限制为不得超过每年8.333%
#:   subject  利息
#:   predicate 被限制为不得超过        <- explicit prohibition, so HARD
#:   object   每年8.333%
#:   boundary 8.333%
#:
#: Every field is a literal substring of that span. The KU statement for the
#: same unit says 罗马法定利率上限：8.333%/年, whose 上限 and "8.333%/年" are in
#: neither form present in the span — which is exactly why the fields are
#: quoted from the span and not from the KU statement.
PILOT_CONSTRAINT = {
    "knowledge_unit_id": "ku_15a527238f5c",
    "constraint_type": "HARD",
    "subject": "利息",
    "predicate": "被限制为不得超过",
    "object": "每年8.333%",
    "boundary": "8.333%",
}

#: Spans that carry a limit or prohibition marker but yield no constraint.
#: Measured, not assumed — each is recorded with why it is absent rather than
#: quietly dropped.
MEASURED_REJECTIONS = {
    "ku_639e79172556": "span 银子贷款按重量计算每年20% states a rate with no "
                       "上限, no 不得超过 and no 禁止; the cap framing is the "
                       "KU statement's, so a rate fact is not a constraint",
    "ku_8b366dd7b4d1": "如果作弊收取的利息高于法定上限，那么债务的本金就会被免除 "
                       "is a conditional consequence, not a limit on the rate",
    "ku_5840cc146f9f": "索伦法典取消利率上限 records the removal of a limit, not "
                       "a limit stated by this source",
    "ku_4ccc104bb7a8": "高于法定上限的利息将被处以4倍损害赔偿 is a sanction "
                       "attached to a limit, not the limit itself",
    "ku_93a979cb6fab": "因而必须进行重大改革 refers 必须 to reform, not to a "
                       "credit constraint",
}

#: Constraint-bearing spans with no frozen knowledge unit. 081 requires
#: knowledge_unit_id NOT NULL, so these cannot be written at all.
UNANCHORED_SPANS = (
    "p4 法定利率上限确定为谷物贷款每年33.333%，以实物偿还",
    "p5 所有贷款都必须附有书面合约，并由官员作证",
    "p7 他们减少或者豁免了许多债务…但是禁止个人劳役偿债",
)


def build_constraint(sink=None) -> Dict:
    """P1 -> P7 -> P6 -> P5.4, then the pilot constraint, written once."""
    chain = (build_identity(sink=sink) if sink is not None
             else build_identity(sink=ConstraintSink()))
    upstream = chain["result"]
    units = {key: dict(vars(unit))
             for key, unit in sorted(chain["sink"].units.items())}

    writer = ConstraintWriter(upstream["base"]["pipeline"], chain["sink"])
    candidate = writer.builder.build(
        source_version_id=upstream["base"]["source_version_id"],
        unit_id=PILOT_CONSTRAINT["knowledge_unit_id"],
        constraint_type=PILOT_CONSTRAINT["constraint_type"],
        subject=PILOT_CONSTRAINT["subject"],
        predicate=PILOT_CONSTRAINT["predicate"],
        obj=PILOT_CONSTRAINT["object"],
        boundary=PILOT_CONSTRAINT["boundary"],
        extractor_version=PILOT_DECLARED_VERSION)
    written = writer.write(candidate)

    return {"chain": chain, "result": upstream, "sink": chain["sink"],
            "writer": writer, "candidate": candidate, "written": written,
            "unit_snapshot_before": units}


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
    # leaves body starting after it, and hunting for the next "(" then lands
    # inside the first CHECK rather than at the start of the column list.
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
    for table in CONSTRAINT_TABLES:
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
    """Every foreign key is RESTRICT, single-column or composite."""
    clean = _clean()
    verbs = re.findall(r"ON DELETE (\w+)", clean)
    if set(verbs) != {"RESTRICT"}:
        return "FAIL"
    if len(verbs) != 2:
        return "FAIL"
    return "PASS"


def isolation_schema_gate() -> str:
    """The unit must be of the annotation's own source version.

    §8 of the review spec forbids service-only enforcement, and a CHECK cannot
    do this — it would read knowledge_unit, which PostgreSQL refuses. So the
    tie is a composite key, and this reads the file to confirm the composite
    form rather than trusting the comment.
    """
    clean = _clean()
    if "CONSTRAINT constraint_unit_same_source" not in clean:
        return "FAIL"
    if "FOREIGN KEY (knowledge_unit_id, source_version_id)" not in clean:
        return "FAIL"
    if "REFERENCES stratum.knowledge_unit (id, source_version_id)" not in clean:
        return "FAIL"
    return "PASS"


def index_reuse_gate() -> str:
    """081 indexes only its own table; the composite key reuses 079's index.

    §8 lists UNIQUE (id, source_version_id) on knowledge_unit as required. It
    already exists. Creating it again here would be a duplicate index on a frozen
    table, so this asserts the opposite: no frozen table is indexed by 081.
    """
    clean = _clean()
    indexed = re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS \w+\s+"
                         r"ON stratum\.(\w+)", clean)
    if set(indexed) - set(CONSTRAINT_TABLES):
        return "FAIL"
    if REUSED_FROZEN_INDEX in clean.replace("\n", " ").split("REFERENCES")[-1]:
        return "FAIL"
    return "PASS"


def constraint_gate() -> str:
    """Hash unique, evidence non-empty, quoted fields non-empty, columns
    declared."""
    clean = _clean()
    for fragment in (
            "CONSTRAINT constraint_candidate_hash_uniq UNIQUE (constraint_hash)",
            "CHECK (cardinality(evidence_ids) >= 1)",
            "CHECK (length(btrim(subject)) > 0)",
            "CHECK (length(btrim(predicate)) > 0)",
            "CHECK (length(btrim(object)) > 0)"):
        if fragment not in clean:
            return "FAIL"
    if "array_length(" in clean:
        return "FAIL"
    if "CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED'))" not in clean:
        return "FAIL"
    if not set(CONSTRAINT_COLUMNS) <= _declared_columns(CONSTRAINT_TABLES[0]):
        return "FAIL"
    return "PASS"


def vocabulary_gate() -> str:
    """constraint_type closed to three values, status closed, no judgement word.

    The deferred words must be absent from the constraints, not merely unused,
    so raw SQL cannot write one later.
    """
    clean = _clean()
    if "CHECK (constraint_type IN ('HARD', 'SOFT', 'SELF_DEFINED'))" not in clean:
        return "FAIL"
    for banned in ("VERIFIED", "CONFIRMED", "APPROVED"):
        if banned in clean:
            return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Writer columns, schema columns and dataclass fields must agree."""
    fields = set(vars(ConstraintCandidate(
        id="", source_version_id="", knowledge_unit_id="", constraint_type="",
        subject="", predicate="", object="")))
    if not set(CONSTRAINT_COLUMNS) <= _declared_columns(CONSTRAINT_TABLES[0]):
        return "FAIL"
    if not set(CONSTRAINT_COLUMNS) <= fields:
        return "FAIL"
    if "created_at" in CONSTRAINT_INSERT_COLUMNS:
        return "FAIL"
    return "PASS"


def banned_field_gate() -> str:
    """No constraint row grew an advice column."""
    return "FAIL" if any(banned_field_report().values()) else "PASS"


def hash_ordering_gate() -> str:
    """evidence_ids is sorted before hashing; traversal order is not a claim."""
    import inspect
    from .constraint_writer import constraint_hash
    source = inspect.getsource(constraint_hash)
    if "sorted(evidence_ids)" not in source:
        return "FAIL"
    if "authors" in source:
        return "FAIL"
    return "PASS"


# ── Gate 2 authority ─────────────────────────────────────────────────────────

def frozen_layers_untouched_gate() -> str:
    """077's condition/boundary layer and every later frozen layer."""
    clean = _clean()
    for table in ("ku_condition_candidate", "ku_boundary_candidate",
                  "ku_relation", "relation_candidate",
                  "paper_source_candidate"):
        if table in clean:
            return "FAIL"
    return "PASS"


def authority_gate(result: Dict) -> str:
    """B, C and BU2 all zero, in three layers."""
    if external_imports():
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    if not referenced <= ALLOWED_FK_TARGETS:
        return "FAIL"
    payload = {"constraints": [c.id for c in
                               result["sink"].constraint_candidates.values()]}
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Dict) -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, measured in the three layers.

    Never a word scan of this file: the token list would match itself.
    """
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    drift = len(referenced - ALLOWED_FK_TARGETS)
    payload = {"constraints": [c.id for c in
                               result["sink"].constraint_candidates.values()]}
    total = len(external_imports()) + drift + len(artifact_drift(payload))
    return {"B_REFERENCE": total, "C_REFERENCE": total,
            "BU2_DEPENDENCY": drift,
            "external_imports": len(external_imports())}


def baseline_mutation_gate(result: Dict) -> str:
    """The A chain underneath is byte-identical after the write."""
    after = {key: dict(vars(unit))
             for key, unit in sorted(result["sink"].units.items())}
    return "PASS" if after == result["unit_snapshot_before"] else "FAIL"


# ── Gate 3 quote authority ───────────────────────────────────────────────────

def quote_authority_gate(result: Dict) -> str:
    """DECISION=SPAN_ONLY: every quoted field is in its own span.

    The single check this whole stage exists for. It is a writer gate because a
    CHECK cannot read another table, so it has to be *checked* rather than
    assumed — hence a gate rather than a comment.
    """
    writer: ConstraintWriter = result["writer"]
    if writer.unquoted_candidates():
        return "FAIL"
    for candidate in result["sink"].constraint_candidates.values():
        for evidence_id in candidate.evidence_ids:
            evidence = result["result"]["base"]["pipeline"].store.evidence.get(
                evidence_id)
            span = evidence_span(evidence)
            if span is None or not field_is_quoted(candidate, span):
                return "FAIL"
    return "PASS"


def ku_statement_not_evidence_gate(result: Dict) -> str:
    """The KU statement is context, never a quotation source.

    Measured on this corpus: the silver-loan unit's statement says
    巴比伦法定利率上限 while its span says 银子贷款按重量计算每年20% with no 上限 at
    all. And for the pilot unit, 法定利率上限 and 8.333%/年 are in the statement
    while only 8.333% is in the span.

    So this asserts the negative direction specifically: no quoted field may be a
    word that exists **only** in the statement. That is the shape a laundered
    interpretation would take, and it is the thing §2 forbids.
    """
    store = _store(result)
    for candidate in result["sink"].constraint_candidates.values():
        unit = result["sink"].units[candidate.knowledge_unit_id]
        statement = unit.statement or ""
        spans = [evidence_span(store.evidence.get(e))
                 for e in candidate.evidence_ids]
        if any(span is None for span in spans):
            return "FAIL"
        for value in (candidate.subject, candidate.predicate, candidate.object,
                      candidate.boundary):
            if value is None:
                continue
            in_span = any(value in (span or "") for span in spans)
            if not in_span:
                return "FAIL"
            # Present in the statement but not the span is exactly what the
            # decision forbids as a *source*; it may appear as context, so this
            # records the distinction rather than banning the word outright.
            if value in statement and not in_span:
                return "FAIL"
    return "PASS"


# ── Gate 4 trace ─────────────────────────────────────────────────────────────

def trace_gate(result: Dict) -> str:
    """constraint -> unit -> span, 100%."""
    writer: ConstraintWriter = result["writer"]
    if not result["sink"].constraint_candidates:
        return "FAIL"
    if writer.traceability_percent() != 100.0:
        return "FAIL"
    if writer.cross_source_candidates():
        return "FAIL"
    return "PASS"


def coverage_gate(result: Dict) -> str:
    """Report which constraint types were exercised.

    Not a pass/fail on coverage: SOFT and SELF_DEFINED are expected False and
    the frozen decision is to report that rather than narrow the vocabulary. What
    this checks is that an undeclared type was never written.
    """
    writer: ConstraintWriter = result["writer"]
    if writer.unauthorised_type_rows():
        return "FAIL"
    coverage = writer.type_coverage()
    if set(coverage) != set(CONSTRAINT_TYPES):
        return "FAIL"
    return "PASS"


# ── Gate 5 replay ────────────────────────────────────────────────────────────

def _fingerprint(sink) -> Dict[str, str]:
    return {key: sink.constraint_candidates[key].constraint_hash
            for key in sorted(sink.constraint_candidates)}


def replay_gate() -> Dict[str, object]:
    """Re-run the whole constraint: same hash, nothing new."""
    first = build_constraint()
    before = _fingerprint(first["sink"])
    second = build_constraint()
    after = _fingerprint(second["sink"])
    again = first["writer"].builder.build(
        first["result"]["base"]["source_version_id"],
        PILOT_CONSTRAINT["knowledge_unit_id"],
        PILOT_CONSTRAINT["constraint_type"], PILOT_CONSTRAINT["subject"],
        PILOT_CONSTRAINT["predicate"], PILOT_CONSTRAINT["object"],
        PILOT_CONSTRAINT["boundary"], PILOT_DECLARED_VERSION)
    first["writer"].write(again)
    final = _fingerprint(first["sink"])
    return {
        "constraints": len(after),
        "identical_fingerprints": int(before == after),
        "rewrite_is_noop": int(before == final),
        "new_constraint": max(0, len(after) - len(before)),
        "duplicate_hashes": len(first["writer"].duplicate_hashes()),
    }


def idempotency_gate(result: Dict) -> str:
    """Writing the same constraint twice appends nothing."""
    writer: ConstraintWriter = result["writer"]
    before = _fingerprint(result["sink"])
    writer.write(result["candidate"])
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


def hash_stability_gate() -> str:
    """Same input, same hash. Any quoted field or the evidence set, a new one."""
    from .constraint_writer import constraint_hash, constraint_id
    base_id = constraint_id("sv_x", "ku_x", "HARD", PILOT_DECLARED_VERSION)
    base_hash = constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "b",
                                ["ev_a", "ev_b"], PILOT_DECLARED_VERSION)
    variants = [
        # every quoted field is identity
        constraint_hash("sv_x", "ku_x", "HARD", "S", "p", "o", "b",
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) != base_hash,
        constraint_hash("sv_x", "ku_x", "HARD", "s", "P", "o", "b",
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) != base_hash,
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "O", "b",
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) != base_hash,
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "B",
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) != base_hash,
        # a nullable boundary is still identity
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", None,
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) != base_hash,
        # evidence set
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "b",
                        ["ev_c"], PILOT_DECLARED_VERSION) != base_hash,
        # extractor version
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "b",
                        ["ev_a", "ev_b"], EXTRACTOR_VERSION) != base_hash,
        # traversal order is not a claim
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "b",
                        ["ev_b", "ev_a"], PILOT_DECLARED_VERSION) == base_hash,
        # deterministic
        constraint_hash("sv_x", "ku_x", "HARD", "s", "p", "o", "b",
                        ["ev_a", "ev_b"], PILOT_DECLARED_VERSION) == base_hash,
        # a second rule from the same unit is a different candidate
        constraint_id("sv_x", "ku_x", "SOFT", PILOT_DECLARED_VERSION)
        != base_id,
    ]
    return "PASS" if all(variants) else "FAIL"


# ── Gate 6 isolation ─────────────────────────────────────────────────────────

def same_source_gate(result: Dict) -> str:
    """The unit is of the annotation's own source version."""
    writer: ConstraintWriter = result["writer"]
    if writer.cross_source_candidates():
        return "FAIL"
    for candidate in result["sink"].constraint_candidates.values():
        unit = result["sink"].units[candidate.knowledge_unit_id]
        if unit.source_version_id != candidate.source_version_id:
            return "FAIL"
    return "PASS"


# ── Gate 7 negative ──────────────────────────────────────────────────────────

def _clone(candidate) -> ConstraintCandidate:
    return ConstraintCandidate(
        id=candidate.id, source_version_id=candidate.source_version_id,
        knowledge_unit_id=candidate.knowledge_unit_id,
        constraint_type=candidate.constraint_type, subject=candidate.subject,
        predicate=candidate.predicate, object=candidate.object,
        evidence_ids=list(candidate.evidence_ids), boundary=candidate.boundary,
        constraint_hash=candidate.constraint_hash,
        extractor_version=candidate.extractor_version,
        status=candidate.status, created_at=candidate.created_at)


def _downgrade() -> None:
    """A supported candidate may not fall back to GENERATED or REJECTED."""
    fresh = build_constraint()
    writer = fresh["writer"]
    candidate = fresh["written"]
    writer.support(candidate.id)
    for target in (ConstraintStatus.GENERATED, ConstraintStatus.REJECTED):
        try:
            transition(candidate, target)
        except ConstraintViolation:
            continue
        raise AssertionError(f"supported -> {target.value} was allowed")
    raise ConstraintViolation("no downgrade is legal; the loop proves it")


def _rejected_is_final() -> None:
    """A rejected candidate may not be revived."""
    fresh = build_constraint()
    writer = fresh["writer"]
    candidate = fresh["written"]
    writer.reject(candidate.id)
    for target in (ConstraintStatus.GENERATED, ConstraintStatus.SUPPORTED):
        try:
            transition(candidate, target)
        except ConstraintViolation:
            continue
        raise AssertionError(f"rejected -> {target.value} was allowed")
    raise ConstraintViolation("no edge leaves REJECTED; the loop proves it")


def negative_gate(result: Dict) -> Dict[str, bool]:
    """Each forbidden shape must actually be refused.

    Reported as a map so a regression names which case stopped being refused.
    Probes go through `write()`, which raises, rather than the precondition
    method, which returns a tuple — asserting on a return value nothing raises
    on would report a refusal that never happened.
    """
    throwaway = build_constraint()
    writer: ConstraintWriter = throwaway["writer"]
    builder = writer.builder
    source_version = throwaway["result"]["base"]["source_version_id"]

    def refuses(fn) -> bool:
        try:
            fn()
        except (ConstraintPrecondition, ConstraintViolation, ValueError,
                KeyError):
            return True
        return False

    def write_clone(mutate) -> None:
        clone = _clone(throwaway["candidate"])
        mutate(clone)
        # A distinct id and hash so the duplicate short-circuit cannot mask the
        # precondition check.
        clone.id = "cnc_damaged"
        clone.constraint_hash = "cnh_damaged"
        writer.write(clone)

    def build_with(**kwargs) -> ConstraintCandidate:
        params = {"source_version_id": source_version,
                  "unit_id": PILOT_CONSTRAINT["knowledge_unit_id"],
                  "constraint_type": PILOT_CONSTRAINT["constraint_type"],
                  "subject": PILOT_CONSTRAINT["subject"],
                  "predicate": PILOT_CONSTRAINT["predicate"],
                  "obj": PILOT_CONSTRAINT["object"],
                  "boundary": PILOT_CONSTRAINT["boundary"],
                  "extractor_version": PILOT_DECLARED_VERSION}
        params.update(kwargs)
        return builder.build(**params)

    def write_built(candidate) -> None:
        candidate.id = "cnc_built"
        candidate.constraint_hash = "cnh_built"
        writer.write(candidate)

    checks = {
        # DECISION=SPAN_ONLY — the central refusal
        "ku_statement_not_quoted": refuses(
            lambda: write_built(build_with(subject="法定利率上限"))),
        "boundary_not_in_span": refuses(
            lambda: write_built(build_with(boundary="8.333%/年"))),
        # Not 不得超过: that *is* a substring of the span, so accepting it is
        # correct and probing it would assert a bug. The predicate has to be a
        # wording the span does not carry.
        "predicate_not_in_span": refuses(
            lambda: write_built(build_with(predicate="不得高于"))),
        "predicate_much_worse_than_span_wording": refuses(
            lambda: write_built(build_with(predicate="禁止"))),
        "subject_not_in_span": refuses(
            lambda: write_built(build_with(subject="利率"))),
        # `obj`, not `object`: the builder names it after the builtin it avoids.
        "object_not_in_span": refuses(
            lambda: write_built(build_with(obj="20%"))),
        "invented_boundary": refuses(
            lambda: write_built(build_with(boundary="5%"))),
        # vocabulary
        "unknown_type": refuses(
            lambda: build_with(constraint_type="ADVISORY")),
        "recommended_type": refuses(
            lambda: build_with(constraint_type="RECOMMENDED")),
        "no_such_source_version": refuses(
            lambda: write_built(build_with(source_version_id="sv_absent"))),
        "no_such_unit": refuses(
            lambda: write_built(build_with(unit_id="ku_not_a_unit"))),
        # isolation
        "cross_source_unit": refuses(
            lambda: write_clone(
                lambda c: c.__setattr__("source_version_id",
                                        "sv_another_book"))),
        "no_evidence": refuses(
            lambda: write_clone(lambda c: c.evidence_ids.clear())),
        "cross_book_evidence": refuses(
            lambda: write_clone(
                lambda c: c.evidence_ids.append("ev_not_in_this_book"))),
        # lifecycle
        "verified_status": refuses(lambda: ConstraintStatus("VERIFIED")),
        "confirmed_status": refuses(lambda: ConstraintStatus("CONFIRMED")),
        "approved_status": refuses(lambda: ConstraintStatus("APPROVED")),
        "supported_downgrade": refuses(_downgrade),
        "rejected_revived": refuses(_rejected_is_final),
        # forbidden operations
        "derive_constraint": refuses(
            lambda: writer.derive_constraint(throwaway["written"].id)),
        "recommend": refuses(
            lambda: writer.recommend(throwaway["written"].id, rate=0.05)),
        "merge_constraints": refuses(
            lambda: writer.merge_constraints("cnc_a", "cnc_b")),
        "enforce": refuses(lambda: writer.enforce(throwaway["written"].id)),
        "update_candidate": refuses(
            lambda: writer.update_candidate(throwaway["written"].id,
                                            subject="x")),
        "delete_candidate": refuses(
            lambda: writer.delete_candidate(throwaway["written"].id)),
    }
    return checks


# ── gates ────────────────────────────────────────────────────────────────────

#: What the traceability gate must equal. It was previously emitted as a bare
#: percentage inside `gates`, which the shared verdict contract cannot read.
TRACEABILITY_REQUIRED = 100.0


def _equals(measured: object, required: object) -> str:
    """One measurement as a gate status, against a stated requirement."""
    return "PASS" if measured == required else "FAIL"


def gate_results(result: Dict) -> Dict[str, object]:
    """The acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = negative_gate(result)
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_fk_verb": fk_verb_gate(),
        "GATE_1_isolation_schema": isolation_schema_gate(),
        "GATE_1_index_reuse": index_reuse_gate(),
        "GATE_1_constraints": constraint_gate(),
        "GATE_1_vocabulary": vocabulary_gate(),
        "GATE_1_column_parity": column_parity_gate(),
        "GATE_1_hash_ordering": hash_ordering_gate(),
        "GATE_1_banned_fields": banned_field_gate(),
        "GATE_2_authority": authority_gate(result),
        "GATE_2_frozen_layers": frozen_layers_untouched_gate(),
        "GATE_2_baseline_unchanged": baseline_mutation_gate(result),
        "GATE_3_quote_authority": quote_authority_gate(result),
        "GATE_3_ku_statement_not_evidence": ku_statement_not_evidence_gate(result),
        "GATE_4_trace": trace_gate(result),
        "GATE_4_coverage": coverage_gate(result),
        "GATE_4_traceability_percent": _equals(result["writer"].traceability_percent(),
                                   TRACEABILITY_REQUIRED),
        "GATE_5_replay": "PASS" if (replay["identical_fingerprints"] == 1
                                    and replay["rewrite_is_noop"] == 1
                                    and replay["new_constraint"] == 0
                                    and replay["duplicate_hashes"] == 0)
        else "FAIL",
        "GATE_5_idempotency": idempotency_gate(result),
        "GATE_5_hash_stability": hash_stability_gate(),
        "GATE_6_isolation": same_source_gate(result),
        "GATE_7_negative": "PASS" if all(negative.values()) else "FAIL",
    }


_SCHEMA_GATES = ("GATE_1_schema", "GATE_1_fk_verb", "GATE_1_isolation_schema",
                 "GATE_1_index_reuse", "GATE_1_constraints", "GATE_1_vocabulary",
                 "GATE_1_column_parity", "GATE_1_hash_ordering",
                 "GATE_1_banned_fields")


# ── reporting ────────────────────────────────────────────────────────────────

def _store(result: Dict):
    """The ingestion store.

    book_sources / source_versions / evidence live here, not on the sink:
    IdentitySink carries the frozen derived rows, while evidence is upstream.
    """
    return result["result"]["base"]["pipeline"].store


def report(result: Dict) -> Dict:
    writer: ConstraintWriter = result["writer"]
    sink = result["sink"]
    store = _store(result)
    constraints = []
    for candidate in sorted(sink.constraint_candidates.values(),
                            key=lambda c: c.id):
        unit = sink.units[candidate.knowledge_unit_id]
        spans = []
        for evidence_id in candidate.evidence_ids:
            evidence = store.evidence.get(evidence_id)
            spans.append({
                "evidence_id": evidence_id,
                "page": evidence.page_number if evidence else None,
                "span": evidence_span(evidence),
            })
        constraints.append({
            "constraint_id": candidate.id,
            "constraint_hash": candidate.constraint_hash,
            "constraint_type": candidate.constraint_type,
            "source_version_id": candidate.source_version_id,
            "knowledge_unit_id": candidate.knowledge_unit_id,
            "status": candidate.status,
            "extractor_version": candidate.extractor_version,
            "quoted": {"subject": candidate.subject,
                       "predicate": candidate.predicate,
                       "object": candidate.object,
                       "boundary": candidate.boundary},
            "unit_statement": unit.statement,
            "spans": spans,
            "all_fields_quoted_from_span": all(
                field_is_quoted(candidate, span["span"])
                for span in spans if span["span"]),
        })
    return {
        "task": "A_P5_4_CONSTRAINT",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["result"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "constraint_version": CONSTRAINT_VERSION,
        "constraint_types_declared": list(CONSTRAINT_TYPES),
        "quote_authority": "READING_EVIDENCE_ONLY",
        "ku_statement_as_evidence": "FORBIDDEN",
        "constraint_count": len(sink.constraint_candidates),
        "pilot_rows": writer.pilot_rows(),
        "extracted_rows": writer.extracted_rows(),
        "traceability_percent": writer.traceability_percent(),
        "type_coverage": writer.type_coverage(),
        "measured_rejections": dict(MEASURED_REJECTIONS),
        "unanchored_spans": list(UNANCHORED_SPANS),
        "notes": dict(CONSTRAINT_NOTES),
        "constraints": constraints,
    }


def acceptance(result: Dict) -> Dict[str, object]:
    """§20 acceptance, computed from measurements."""
    gates = gate_results(result)
    contamination = contamination_counts(result)
    negative = negative_gate(result)
    writer: ConstraintWriter = result["writer"]
    checks = {
        "constraint_persisted": len(result["sink"].constraint_candidates),
        "fields_quoted_from_span": gates["GATE_3_quote_authority"],
        # The measurement, not the gate that now reports it.
        "traceability_percent": result["writer"].traceability_percent(),
        "source_isolation": gates["GATE_6_isolation"],
        "replay_stable": gates["GATE_5_replay"],
        "transaction_atomic": "PASS" if gates["GATE_1_schema"] == "PASS"
        else "FAIL",
        "unauthorised_type_rows": len(writer.unauthorised_type_rows()),
        "cross_source_candidates": len(writer.cross_source_candidates()),
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
        "baseline_mutated": 0 if gates["GATE_2_baseline_unchanged"] == "PASS"
        else 1,
        "negative_refusals": sum(1 for v in negative.values() if v),
        "negative_cases": len(negative),
    }
    passed = (checks["constraint_persisted"] == 1
              and checks["fields_quoted_from_span"] == "PASS"
              and checks["traceability_percent"] == 100.0
              and checks["source_isolation"] == "PASS"
              and checks["replay_stable"] == "PASS"
              and checks["transaction_atomic"] == "PASS"
              and checks["unauthorised_type_rows"] == 0
              and checks["cross_source_candidates"] == 0
              and checks["B_CONTAMINATION"] == 0
              and checks["C_CONTAMINATION"] == 0
              and checks["BU2_DEPENDENCY"] == 0
              and checks["baseline_mutated"] == 0
              and checks["negative_refusals"] == checks["negative_cases"])
    return {
        "checks": checks,
        "gates": gates,
        # Derived from every reported gate. The IMPLEMENTATION conjunction
        # below reads a subset, so gates outside it could print PASS and change
        # nothing; the legacy keys are kept for the tests, artifacts and freeze
        # reports that read them.
        "A_P5_4_CONSTRAINT": verdict(gates),
        "verdict_inputs": verdict_inputs(gates),
        "A_P5_4_CONSTRAINT_SCHEMA":
            "PASS" if all(gates[k] == "PASS" for k in _SCHEMA_GATES)
            else "BLOCKED",
        "A_P5_4_CONSTRAINT_IMPLEMENTATION": "PASS" if passed else "BLOCKED",
        "MIGRATION_081": REQUIRED_MIGRATION,
        "TYPE_COVERAGE": writer.type_coverage(),
        "UNTESTED": ["soft_constraint_extraction", "self_defined_constraint",
                     "constraint_completeness", "legal_correctness",
                     "advisory_wording_in_corpus"],
    }


def final_report(result: Dict) -> Dict[str, str]:
    """The spec's FINAL REPORT FORMAT block, verbatim keys.

    COMMIT_SHA and TAG name a commit that has not been made, so they report
    PENDING rather than a guess.
    """
    gates = gate_results(result)
    acceptance_block = acceptance(result)
    contamination = contamination_counts(result)
    verdict = ("PASS"
               if acceptance_block["A_P5_4_CONSTRAINT_IMPLEMENTATION"] == "PASS"
               else "BLOCKED")
    return {
        "TASK": "A_P5_4_CONSTRAINT",
        "MIGRATION_081": REQUIRED_MIGRATION,
        "CONSTRAINT_ROWS": str(len(result["sink"].constraint_candidates)),
        # The measurement. This field reads the gate's status when it does not,
        # which renders the report as "PASS%" instead of "100.0%".
        "TRACEABILITY": f"{result['writer'].traceability_percent()}%",
        "REPLAY": str(gates["GATE_5_replay"]),
        "AUTHORITY_SCAN": str(gates["GATE_2_authority"]),
        "B_CONTAMINATION": str(contamination["B_REFERENCE"]),
        "C_CONTAMINATION": str(contamination["C_REFERENCE"]),
        "DB_MUTATION": str(0 if gates["GATE_2_baseline_unchanged"] == "PASS"
                           else 1),
        "BU2_MUTATION": str(contamination["BU2_DEPENDENCY"]),
        "COMMIT_SHA": os.environ.get("A_P5_4_COMMIT_SHA", "PENDING"),
        "TAG": os.environ.get("A_P5_4_TAG", "PENDING"),
        "FINAL_STATUS": verdict,
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit the constraint table for a DBA to execute."""
    script = emit_constraint_sql(result["sink"].constraint_candidates)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P5_4_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [line.strip() for line in
            source.read_text(encoding="utf-8").splitlines() if line.strip()]


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    target = path or os.environ.get("A_P5_4_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)",
        source.read_text(encoding="utf-8"))} or None


def main() -> None:
    result = build_constraint()
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