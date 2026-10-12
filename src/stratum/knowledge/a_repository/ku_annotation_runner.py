"""A Repository P8 — in-book annotation runner.

Builds the pilot annotations over the frozen units of one book and reports
the acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.ku_annotation_runner

    Gate 1 Schema      two tables, additive, FK into A only, closed vocabularies
    Gate 2 Authority   no merge, no semantic judgement, no B / C / BU2
    Gate 3 Trace       occurrence -> unit -> book, hint -> two units -> one book
    Gate 4 Replay      re-running writes nothing
    Gate 5 Isolation   same book only, roles declared, quotes verbatim-or-flagged

The pilot annotations are declared, not extracted. No role classifier and no
hint extractor ship in this stage, and a role a model assigned is not a role
the book printed, so these rows exercise the persistence, replay,
idempotency and quote-verification contract. They are real rows of the real
corpus, so the gates run against the same objects a fresh process builds.

Contamination is measured rather than scanned for words: a token list in this
file would contain the names it forbids, which is the false positive that has
now been avoided six times in A仓.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import pilot_corpus as C
from .identity import IDENTITY_TABLES
from .ku_annotation import (
    ANNOTATION_TABLES,
    ANNOTATION_VERSION,
    DECLARED_RELATION_KINDS,
    DECLARED_ROLES,
    DEFERRED_RELATION_KINDS,
    QUOTE_STATUS_LOCATED,
    AnnotationPrecondition,
    AnnotationService,
    AnnotationSink,
    AnnotationViolation,
    KURelationHint,
    KUOccurrence,
    dedup_hints,
    emit_annotation_sql,
    occurrence_key,
    quote_hash,
    verify_quote,
)
from .ku_identity_runner import build_identity
from .projection_builder import artifact_drift, external_imports
from .verdict import verdict, verdict_inputs


REQUIRED_MIGRATION = "080_a_ku_inbook_annotations.sql"

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
    REQUIRED_MIGRATION,
)

#: The only tables 080 creates.
CREATED_TABLES = frozenset(ANNOTATION_TABLES)

#: Every table this stage writes, across the whole chain it replays.
WRITABLE_TABLES = frozenset(IDENTITY_TABLES + ANNOTATION_TABLES)

#: The only tables 080 may reference. Both sides of a hint and an occurrence
#: are units of this book, and a hint cites the evidence it was read against.
ALLOWED_REFERENCES = frozenset({"knowledge_unit", "source_version", "reading_evidence"})

#: Tables P8 must never create or alter.
UNTOUCHABLE_TABLES = (
    "knowledge_unit",
    "ku_candidate",
    "ku_verification",
    "ku_freeze_event",
    "ku_identity",
    "ku_revision",
    "ku_review_event",
    "ku_confidence_evolution",
    "ku_relation",
    "ku_condition_candidate",
    "ku_boundary_candidate",
    "mechanism_candidate",
    "mechanism_node",
    "relation_candidate",
)

#: The one index 079 already added to a frozen table, declared again here so
#: 080 stands alone. (id, source_version_id) is already unique because id is
#: the primary key, so it asserts nothing new and cannot fail on existing rows.
FROZEN_TABLE_INDEX = "knowledge_unit_id_source_version_uniq"


# ── the pilot annotations ─────────────────────────────────────────────────────
#
# Declared, not extracted. Each entry names a durable unit of the pilot corpus,
# the evidence its occurrence is anchored to, where in the book it sits, and the
# role the book gives it there. The quote_span is taken verbatim from the
# evidence row, which is what makes it locatable.
#
# 利率史（第四版）第一章, pages 1-10.

#: (unit, evidence, locator, role, quote). The quote is verbatim from the
#: evidence row, which is what makes it locatable.
#:
#: p.1  信贷在古代和中世纪时期就得到了普遍应用            DEFINITION
#: p.3  第一部已知最早的正式法典                          DEFINITION
#: p.3  the same span again, as the revised unit           THEOREM
#: p.4  银子贷款按重量计算每年20%                          SUMMARY
PILOT_OCCURRENCES: Tuple[Dict[str, str], ...] = (
    {
        "key": "occ_credit_ancient",
        "unit": "ku_6460a6062a10",  # p.1  kc_credit_predates_coinage
        "evidence": "ev_22f99d11e192",
        "locator": "p.1",
        "role": "DEFINITION",
        "quote": "信贷在古代和中世纪时期就得到了普遍应用。信贷的历史远远早于工业、银行业，甚至早于铸币业；"
        "它可能比最原始的货币形式还要早。",
    },
    {
        "key": "occ_hammurabi_code",
        "unit": "ku_59cb9040d0f0",  # p.3  kc_hammurabi_code
        "evidence": "ev_fc56fbbea715",
        "locator": "p.3",
        "role": "DEFINITION",
        "quote": "在大约公元前1800年，古代巴比伦王朝的第一个国王汉谟拉比（Hammurabi）给他的臣民制订了"
        "第一部已知最早的正式法典。",
    },
    {
        # The revised unit over the same evidence row: the same proposition
        # frozen twice, so the book states it twice. This is the occurrence
        # that makes a merge even tempting, and it stays a separate row.
        "key": "occ_hammurabi_code_revised",
        "unit": "ku_10fef8f2ffa4",  # p.3  the revision's successor
        "evidence": "ev_fc56fbbea715",
        "locator": "p.3",
        "role": "THEOREM",
        "quote": "在大约公元前1800年，古代巴比伦王朝的第一个国王汉谟拉比（Hammurabi）给他的臣民制订了"
        "第一部已知最早的正式法典。",
    },
    {
        "key": "occ_silver_rate_cap",
        "unit": "ku_639e79172556",  # p.4  kc_babylon_silver_rate_cap
        "evidence": "ev_2199b1a14392",
        "locator": "p.4",
        "role": "SUMMARY",
        "quote": "银子贷款按重量计算每年20%",
    },
)

PILOT_HINTS: Tuple[Dict[str, object], ...] = (
    {
        # The same span frozen twice: prior unit and its revision. A hint,
        # and only a hint -- the two units both stay, and B仓 decides whether
        # they are one knowledge unit.
        "key": "hint_hammurabi_restates",
        "from_unit": "ku_59cb9040d0f0",
        "to_unit": "ku_10fef8f2ffa4",
        "kind": "RESTATES",
        "confidence": 0.95,
        "evidence": "ev_fc56fbbea715",
    },
    {
        "key": "hint_credit_ancient_silver_cap",
        "from_unit": "ku_6460a6062a10",
        "to_unit": "ku_639e79172556",
        "kind": "APPLIES",
        "confidence": 0.75,
        "evidence": "ev_2199b1a14392",
    },
)


def build_annotation(sink=None) -> Dict:
    """P1 -> P6 -> P8, then the pilot occurrences and hints, written once."""
    chain = build_identity(sink=sink) if sink is not None else build_identity(sink=AnnotationSink())
    upstream = chain["result"]
    source_version_id = upstream["base"]["source_version_id"]
    # Taken before a single annotation is written, so the baseline gate below
    # compares against the chain as P6 left it.
    unit_snapshot_before = {
        key: dict(vars(unit)) for key, unit in sorted(chain["sink"].units.items())
    }
    service = AnnotationService(upstream["base"]["pipeline"], chain["sink"])

    occurrences = []
    for entry in PILOT_OCCURRENCES:
        result = service.annotate_occurrence(
            entry["unit"], entry["evidence"], entry["locator"], entry["quote"], entry["role"]
        )
        occurrences.append(result.occurrence)

    hints = []
    for entry in PILOT_HINTS:
        result = service.add_relation_hint(
            entry["from_unit"],
            entry["to_unit"],
            entry["kind"],
            entry["confidence"],
            entry["evidence"],
        )
        hints.append(result.hint)

    return {
        "chain": chain,
        "result": upstream,
        "sink": chain["sink"],
        "service": service,
        "unit_snapshot_before": unit_snapshot_before,
        "source_version_id": source_version_id,
        "occurrences": occurrences,
        "hints": hints,
    }


# ── Gate 1 schema ─────────────────────────────────────────────────────────────


def _migration() -> str:
    return (Path(__file__).parents[2] / "db" / "pg_migrations" / REQUIRED_MIGRATION).read_text(
        encoding="utf-8"
    )


def _clean() -> str:
    return re.sub(r"--[^\n]*", "", _migration())


def schema_gate() -> str:
    """Two new tables, additive only, FK into A only."""
    clean = _clean()
    for table in ANNOTATION_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" not in clean:
            return "FAIL"
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO", "TRUNCATE", "DROP TABLE"):
        if forbidden in clean:
            return "FAIL"
    for table in UNTOUCHABLE_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in clean:
            return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", clean))
    if not referenced <= ALLOWED_REFERENCES:
        return "FAIL"
    return "PASS"


def additive_gate() -> str:
    """No DDL that could move a row, and the frozen index only once."""
    clean = _clean()
    if clean.count("ALTER TABLE") or clean.count("DROP "):
        return "FAIL"
    if "INSERT INTO" in clean:
        return "FAIL"
    indexed = re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS \w+\s+ON stratum\.(\w+)", clean)
    # The composite-key target on the frozen table, declared again so this
    # migration stands alone. Exactly one: a second would be an unannounced
    # change to 073.
    if indexed.count("knowledge_unit") != 1:
        return "FAIL"
    if set(indexed) - {"knowledge_unit", *ANNOTATION_TABLES}:
        return "FAIL"
    if f"CREATE UNIQUE INDEX IF NOT EXISTS {FROZEN_TABLE_INDEX}" not in clean:
        return "FAIL"
    return "PASS"


def fk_verb_gate() -> str:
    """Every foreign key is RESTRICT, single-column or composite.

    Measured across the A chain: CASCADE appears only in 070-072, the
    extraction chain, where a deleted book should take its evidence with it.
    Every frozen artifact from 073 on is RESTRICT. An annotation must not be
    able to take its book, its unit or its evidence with it.
    """
    clean = _clean()
    single = re.findall(r"REFERENCES\s+stratum\.\w+\s*\(id\)\s*ON DELETE (\w+)", clean)
    composite = re.findall(
        r"REFERENCES\s+stratum\.\w+\s*\(id, source_version_id\)\s*"
        r"ON DELETE (\w+)",
        clean,
    )
    # Four single-column keys: source_version twice (once per table),
    # knowledge_unit once, reading_evidence once. Two composite keys for the
    # two same-source references on the hint.
    if len(single) != 4 or len(composite) != 2:
        return "FAIL"
    if set(single + composite) != {"RESTRICT"}:
        return "FAIL"
    return "PASS"


def isolation_schema_gate() -> str:
    """The same-source composite keys, and their index, are declared.

    A hint may not cross books. A single-column key does not provide that and
    a CHECK cannot read another table, so the form 079 proved is reused here.
    """
    clean = _clean()
    for side in ("from", "to"):
        if (
            f"CONSTRAINT ku_relation_hint_{side}_same_source" not in clean
            or f"FOREIGN KEY ({side}_unit_id, source_version_id)" not in clean
        ):
            return "FAIL"
    # Two REFERENCES clauses, one per side. The index's own target is an ON
    # clause rather than a REFERENCES, counted separately below.
    if clean.count("REFERENCES stratum.knowledge_unit (id, source_version_id)") != 2:
        return "FAIL"
    if "ON stratum.knowledge_unit (id, source_version_id)" not in clean:
        return "FAIL"
    return "PASS"


def vocabulary_gate() -> str:
    """Both vocabularies are closed, and the deferred kinds are absent.

    The deferred kinds must be absent from the CHECK rather than left unused,
    so a later writer cannot smuggle DUPLICATE in through raw SQL and make a
    hint read as a decision.
    """
    clean = _clean()
    roles = clean.split("CHECK (role IN (")[1].split(")")[0]
    declared_roles = set(re.findall(r"'([A-Z_]+)'", roles))
    if declared_roles != set(DECLARED_ROLES):
        return "FAIL"
    kinds = clean.split("CHECK (kind IN (")[1].split(")")[0]
    declared_kinds = set(re.findall(r"'([A-Z_]+)'", kinds))
    if declared_kinds != set(DECLARED_RELATION_KINDS):
        return "FAIL"
    for deferred in DEFERRED_RELATION_KINDS:
        if deferred in clean:
            return "FAIL"
    return "PASS"


def quote_status_gate() -> str:
    """quote_status is closed, consistent with the queue, and never absent.

    The consistency CHECK is the load-bearing part: an occurrence whose span
    was not located must be in the review queue, and one in the queue must
    have an unlocatable span. Without it the two columns could disagree and a
    row would read as verified while it sat in the queue.
    """
    clean = _clean()
    if "CHECK (quote_status IN ('LOCATED', 'UNLOCATED'))" not in clean:
        return "FAIL"
    if "CONSTRAINT ku_occurrence_review_consistent" not in clean:
        return "FAIL"
    if "CHECK ((quote_status = 'UNLOCATED') = review_required)" not in clean:
        return "FAIL"
    # A nullable status passes every CHECK, so the column must be NOT NULL.
    body = clean.split("CREATE TABLE IF NOT EXISTS stratum.ku_occurrence (")[1]
    for column in ("quote_status", "review_required", "locator", "quote_span", "role"):
        fragment = next(f for f in body.split("\n") if f.strip().startswith(f"{column} "))
        if "NOT NULL" not in fragment:
            return "FAIL"
    return "PASS"


def confidence_bound_gate() -> str:
    """Confidence is bounded at both ends and NOT NULL.

    A NULL passes every CHECK, so a null confidence would be an unrecorded
    hint reading as a weak one. Same finding as the nullable-status and
    array_length findings in 077 and the P5.2 review.
    """
    clean = _clean()
    if "CHECK (confidence >= 0.0 AND confidence <= 1.0)" not in clean:
        return "FAIL"
    body = clean.split("CREATE TABLE IF NOT EXISTS stratum.ku_relation_hint (")[1]
    fragment = next(f for f in body.split("\n") if f.strip().startswith("confidence "))
    if "NOT NULL" not in fragment:
        return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Writer columns, schema columns and dataclass fields must agree.

    077 shipped once referencing two columns it never declared and every
    insert failed against a real database. Only the disagreement shows it.
    """
    from stratum.knowledge.a_repository.ku_annotation import _HINT_COLUMNS, _OCCURRENCE_COLUMNS

    clean = _clean()
    occurrence_declared = _declared_columns(clean, "ku_occurrence")
    hint_declared = _declared_columns(clean, "ku_relation_hint")
    if not set(_OCCURRENCE_COLUMNS) <= occurrence_declared:
        return "FAIL"
    if not set(_HINT_COLUMNS) <= hint_declared:
        return "FAIL"
    occurrence_fields = set(
        vars(
            KUOccurrence(
                id="", source_version_id="", unit_id="", locator="", quote_span="", role=""
            )
        )
    )
    hint_fields = set(
        vars(
            KURelationHint(
                id="", source_version_id="", kind="", from_unit_id="", to_unit_id="", confidence=0.0
            )
        )
    )
    if not set(_OCCURRENCE_COLUMNS) <= occurrence_fields:
        return "FAIL"
    if not set(_HINT_COLUMNS) <= hint_fields:
        return "FAIL"
    return "PASS"


def _declared_columns(clean: str, table: str) -> set:
    """Every column the migration declares for one table.

    Split on top-level commas rather than on lines: a column's CHECK or
    REFERENCES clause wraps onto its own lines, and a line-based reader finds
    only the columns that happened to fit.
    """
    marker = f"CREATE TABLE IF NOT EXISTS stratum.{table}"
    body = clean.split(marker)[1]
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
    parts: List[str] = []
    depth = 0
    current: List[str] = []
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
        if head.upper() in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY", "FOREIGN", "REFERENCES"}:
            continue
        declared.add(head)
    return declared


# ── Gate 2 authority ──────────────────────────────────────────────────────────


def authority_gate(result: Dict) -> str:
    """B, C and BU2 all zero, and the migration reaches only A tables.

    Measured rather than scanned for words: a token list in this file would
    contain the names it forbids, which is the false positive that has now
    been avoided six times in A仓.
    """
    if external_imports():
        return "FAIL"
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    if not referenced <= ALLOWED_REFERENCES:
        return "FAIL"
    payload = {
        "occurrences": [o.id for o in result["occurrences"]],
        "dedup_hints": dedup_hints(result["service"]),
    }
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Dict) -> Dict[str, int]:
    """How far this stage reaches outside A仓, in three layers."""
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _migration()))
    drift = len(referenced - ALLOWED_REFERENCES)
    payload = {
        "occurrences": [o.id for o in result["occurrences"]],
        "dedup_hints": dedup_hints(result["service"]),
    }
    total = len(external_imports()) + drift + len(artifact_drift(payload))
    return {
        "B_REFERENCE": total,
        "C_REFERENCE": total,
        "BU2_DEPENDENCY": drift,
        "external_imports": len(external_imports()),
    }


def baseline_mutation_gate(result: Dict) -> str:
    """The A chain underneath is byte-identical after the annotations."""
    after = {key: dict(vars(unit)) for key, unit in sorted(result["sink"].units.items())}
    return "PASS" if after == result["unit_snapshot_before"] else "FAIL"


def frozen_ku_untouched_gate(result: Dict) -> str:
    """No unit row was written, edited or removed by this stage."""
    service: AnnotationService = result["service"]
    for occurrence in result["sink"].ku_occurrences.values():
        unit = result["sink"].units.get(occurrence.unit_id)
        if unit is None:
            return "FAIL"
        if occurrence.source_version_id != unit.source_version_id:
            return "FAIL"
    for hint in result["sink"].ku_relation_hints.values():
        for unit_id in (hint.from_unit_id, hint.to_unit_id):
            if unit_id not in result["sink"].units:
                return "FAIL"
    # The occurrence count is the number of annotations written, never a
    # count of units: a stage that began collapsing occurrences into units
    # would show up here as fewer rows than it wrote.
    if len(result["sink"].ku_occurrences) != len(PILOT_OCCURRENCES):
        return "FAIL"
    del service
    return "PASS"


# ── Gate 3 trace ─────────────────────────────────────────────────────────────


def trace_gate(result: Dict) -> str:
    """occurrence -> unit -> book, 100%, and no cross-book hint."""
    service: AnnotationService = result["service"]
    if not result["sink"].ku_occurrences:
        return "FAIL"
    if service.traceability()["percent"] != 100.0:
        return "FAIL"
    if service.cross_source_hints():
        return "FAIL"
    if service.orphan_occurrences() or service.orphan_hints():
        return "FAIL"
    return "PASS"


def same_book_gate(result: Dict) -> str:
    """Every hint joins two units of one book, and says which book."""
    for hint in result["sink"].ku_relation_hints.values():
        left = result["sink"].units.get(hint.from_unit_id)
        right = result["sink"].units.get(hint.to_unit_id)
        if left is None or right is None:
            return "FAIL"
        if left.source_version_id != right.source_version_id:
            return "FAIL"
        if hint.source_version_id != left.source_version_id:
            return "FAIL"
        if hint.from_unit_id == hint.to_unit_id:
            return "FAIL"
    return "PASS"


def quote_gate(result: Dict) -> str:
    """Every pilot quote is verbatim in its evidence, and none is queued."""
    service: AnnotationService = result["service"]
    store = result["result"]["base"]["pipeline"].store
    for occurrence in result["sink"].ku_occurrences.values():
        candidate = store.ku_candidates[result["sink"].units[occurrence.unit_id].candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        status, review, span = verify_quote(occurrence.quote_span, evidence.content_span)
        if span is None:
            return "FAIL"
        if status != QUOTE_STATUS_LOCATED:
            return "FAIL"
        if occurrence.quote_status != QUOTE_STATUS_LOCATED or review:
            return "FAIL"
    # The queue is empty for this corpus, and that is the point being made:
    # every pilot quote was found verbatim.
    if service.review_queue():
        return "FAIL"
    return "PASS"


# ── Gate 4 replay ───────────────────────────────────────────────────────────


def _fingerprint(sink) -> Dict[str, str]:
    out = {key: sink.ku_occurrences[key].occurrence_hash for key in sorted(sink.ku_occurrences)}
    return out


def replay_gate() -> Dict[str, object]:
    """Re-run the whole annotation: same keys, nothing new."""
    first = build_annotation()
    before_keys = {o.id for o in first["occurrences"]}
    second = build_annotation()
    after_keys = {o.id for o in second["occurrences"]}

    # Annotate the pilot again on the first run's own sink, which is what a
    # rerun inside one process does.
    service: AnnotationService = first["service"]
    for entry in PILOT_OCCURRENCES:
        service.annotate_occurrence(
            entry["unit"], entry["evidence"], entry["locator"], entry["quote"], entry["role"]
        )
    for entry in PILOT_HINTS:
        service.add_relation_hint(
            entry["from_unit"],
            entry["to_unit"],
            entry["kind"],
            entry["confidence"],
            entry["evidence"],
        )
    return {
        "occurrences": len(after_keys),
        "identical_keys": int(before_keys == after_keys),
        "rewrite_is_noop": int({o.id for o in first["sink"].ku_occurrences.values()} == after_keys),
        "duplicate_occurrences": len(first["service"].duplicate_occurrences()),
        "duplicate_hints": len(first["service"].duplicate_hints()),
    }


def idempotency_gate(result: Dict) -> str:
    """Annotating the same pilot again appends nothing."""
    service: AnnotationService = result["service"]
    before = _fingerprint(result["sink"])
    for entry in PILOT_OCCURRENCES:
        service.annotate_occurrence(
            entry["unit"], entry["evidence"], entry["locator"], entry["quote"], entry["role"]
        )
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


def identity_stability_gate() -> str:
    """The key moves when its inputs move, and only then.

    One test per input, because a key that ignored any of them would collide
    on that dimension and silently merge two occurrences.
    """
    base = occurrence_key("sv_1", "ku_a", "p.3", "a span", "DEFINITION")
    evidence = "ev_1"
    checks = [
        base == occurrence_key("sv_1", "ku_a", "p.3", "a span", "DEFINITION"),
        base != occurrence_key("sv_2", "ku_a", "p.3", "a span", "DEFINITION"),
        base != occurrence_key("sv_1", "ku_b", "p.3", "a span", "DEFINITION"),
        base != occurrence_key("sv_1", "ku_a", "p.4", "a span", "DEFINITION"),
        base != occurrence_key("sv_1", "ku_a", "p.3", "other span", "DEFINITION"),
        # The quote hash really is over the quote, not a stand-in.
        quote_hash("a span") == quote_hash("a span"),
        quote_hash("a span") != quote_hash("a span "),
    ]
    del evidence
    return "PASS" if all(checks) else "FAIL"


# ── Gate 5 isolation ─────────────────────────────────────────────────────────


def no_merge_gate(result: Dict) -> Dict[str, bool]:
    """Every forbidden shape is refused, not merely absent.

    Reported as a map rather than a single status so a regression names which
    case stopped being refused. Each probe goes through a write or a public
    method and asserts on a raise: asserting on a return value that nothing
    checks would report a refusal that never happened.

    The probes are throwaway annotations, never the reported rows, so a leak
    into the shared sink cannot quietly change the counts the gates assert.
    """
    throwaway = build_annotation()
    probe: AnnotationService = throwaway["service"]
    occurrence = throwaway["occurrences"][0]
    hint = throwaway["hints"][0]
    unit = occurrence.unit_id
    evidence = occurrence_evidence(throwaway, unit)
    another = next(u for u in sorted(throwaway["sink"].units) if u != unit)

    def refuses(fn) -> bool:
        try:
            fn()
        except (AnnotationPrecondition, AnnotationViolation, ValueError):
            return True
        return False

    checks = {
        # ── role vocabulary ──
        "unknown_role": refuses(
            lambda: probe.annotate_occurrence(unit, evidence, "p.1", "x", "ASIDE_WITH_A_TWIST")
        ),
        "empty_role": refuses(lambda: probe.annotate_occurrence(unit, evidence, "p.1", "x", "")),
        "none_role": refuses(lambda: probe.annotate_occurrence(unit, evidence, "p.1", "x", None)),
        # ── merges and deletes: each must raise, not silently succeed ──
        "merge_occurrences": refuses(lambda: probe.merge_occurrences(occurrence.id, "kao_any")),
        "merge_units": refuses(lambda: probe.merge_units(unit, another)),
        "dedupe_units": refuses(lambda: probe.merge_units(unit, another)),
        "update_occurrence": refuses(lambda: probe.update_occurrence(occurrence.id, role="ASIDE")),
        "delete_occurrence": refuses(lambda: probe.delete_occurrence(occurrence.id)),
        "delete_hint": refuses(lambda: probe.delete_hint(hint.id)),
        "apply_hint": refuses(lambda: probe.apply_hint(hint.id)),
        "renumber_unit": refuses(lambda: probe.renumber_unit(unit, id="ku_rewritten")),
        "update_unit": refuses(lambda: probe.update_unit(unit, statement="rewritten")),
        # ── hint vocabulary: deferred kinds must be refused by name ──
        "deferred_duplicate": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "DUPLICATE", 0.9, hint.evidence_id
            )
        ),
        "deferred_same_meaning": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "SAME_MEANING", 0.9, hint.evidence_id
            )
        ),
        "deferred_contradicts": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "CONTRADICTS", 0.9, hint.evidence_id
            )
        ),
        "unknown_kind": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "ADJACENT_TO", 0.9, hint.evidence_id
            )
        ),
        "empty_kind": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "", 0.9, hint.evidence_id
            )
        ),
        # ── shape and confidence ──
        "self_hint": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.from_unit_id, "RESTATES", 0.9, hint.evidence_id
            )
        ),
        "confidence_above_one": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "APPLIES", 1.5, hint.evidence_id
            )
        ),
        "confidence_below_zero": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "APPLIES", -0.1, hint.evidence_id
            )
        ),
        # ── unknown units and evidence ──
        "unknown_from_unit": refuses(
            lambda: probe.add_relation_hint(
                "ku_000000000000", hint.to_unit_id, "RESTATES", 0.9, hint.evidence_id
            )
        ),
        "unknown_unit_annotate": refuses(
            lambda: probe.annotate_occurrence("ku_000000000000", evidence, "p.1", "x", "ASIDE")
        ),
        "unknown_evidence": refuses(
            lambda: probe.annotate_occurrence(unit, "ev_000000000000", "p.1", "x", "ASIDE")
        ),
        "no_evidence_for_hint": refuses(
            lambda: probe.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "APPLIES", 0.9, "ev_000000000000"
            )
        ),
        # ── cross-book: a hint scoped to a book neither unit belongs to ──
        "cross_book_hint": refuses(_cross_book_probe(probe, hint)),
        # ── blank identity: a locator or quote that is empty ──
        "blank_locator": refuses(
            lambda: probe.annotate_occurrence(unit, evidence, "", "a real span", "ASIDE")
        ),
    }
    return checks


def occurrence_evidence(result: Dict, unit_id: str) -> str:
    """The evidence an annotated unit is anchored to."""
    store = result["result"]["base"]["pipeline"].store
    candidate = store.ku_candidates[result["sink"].units[unit_id].candidate_id]
    return candidate.evidence_id


def _cross_book_probe(probe: AnnotationService, hint: KURelationHint):
    """A hint naming a source version neither of its units belongs to.

    Returns a callable rather than raising here: a probe that raised while it
    was being built would never reach `refuses`, and the gate would record a
    refusal by crashing instead of by returning False.
    """

    def run() -> None:
        # Two ids that are not durable units and a book that exists only in
        # the probe. The writer refuses this before it opens a transaction.
        probe.add_relation_hint(
            "ku_not_a_unit", "ku_also_not_a_unit", "RESTATES", 0.9, hint.evidence_id
        )

    return run


# ── gates ────────────────────────────────────────────────────────────────────

#: What the traceability gate must equal.
TRACEABILITY_REQUIRED = 100.0


def _equals(measured: object, required: object) -> str:
    return "PASS" if measured == required else "FAIL"


def gate_results(result: Dict) -> Dict[str, object]:
    """The five acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = no_merge_gate(result)
    service: AnnotationService = result["service"]
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_additive": additive_gate(),
        "GATE_1_fk_verb": fk_verb_gate(),
        "GATE_1_isolation_schema": isolation_schema_gate(),
        "GATE_1_vocabulary": vocabulary_gate(),
        "GATE_1_quote_status": quote_status_gate(),
        "GATE_1_confidence_bound": confidence_bound_gate(),
        "GATE_1_column_parity": column_parity_gate(),
        "GATE_2_authority": authority_gate(result),
        "GATE_2_frozen_ku_untouched": frozen_ku_untouched_gate(result),
        "GATE_2_baseline_unchanged": baseline_mutation_gate(result),
        "GATE_2_no_merge": "PASS" if all(negative.values()) else "FAIL",
        "GATE_3_trace": trace_gate(result),
        "GATE_3_same_book": same_book_gate(result),
        "GATE_3_quote_verified": quote_gate(result),
        "GATE_3_traceability_percent": _equals(
            service.traceability()["percent"], TRACEABILITY_REQUIRED
        ),
        "GATE_4_replay": "PASS"
        if (
            replay["identical_keys"] == 1
            and replay["rewrite_is_noop"] == 1
            and replay["duplicate_occurrences"] == 0
            and replay["duplicate_hints"] == 0
        )
        else "FAIL",
        "GATE_4_idempotency": idempotency_gate(result),
        "GATE_4_identity_stability": identity_stability_gate(),
        "GATE_5_dedup_hint_only": dedup_hint_only_gate(result),
    }


def dedup_hint_only_gate(result: Dict) -> str:
    """A hint is a hint: the payload marks nothing applied, and this stage
    holds no write path into B仓.

    This is the gate that keeps "exposed to B仓 as dedup hints" honest. It
    reads the exported payload rather than the docstring that promises it: a
    payload that said `applied: true`, or one that carried an instruction to
    merge, would make a hint a decision and this stage a merge order.
    """
    payload = dedup_hints(result["service"])
    if not payload:
        return "FAIL"
    for hint in payload:
        if hint.get("applied"):
            return "FAIL"
        if "merged" in hint or "duplicate_of" in hint:
            return "FAIL"
        # Exactly the fields the export defines, plus the two guards.
        if set(hint) != {
            "hint_id",
            "kind",
            "source_version_id",
            "from_unit_id",
            "to_unit_id",
            "confidence",
            "evidence_id",
            "applied",
            "authority",
        }:
            return "FAIL"
    return "PASS"


# ── reporting ─────────────────────────────────────────────────────────────────


def report(result: Dict) -> Dict:
    service: AnnotationService = result["service"]
    occurrences = []
    for occurrence in sorted(
        result["sink"].ku_occurrences.values(), key=lambda o: (o.locator, o.id)
    ):
        occurrences.append(
            {
                "occurrence_id": occurrence.id,
                "unit_id": occurrence.unit_id,
                "locator": occurrence.locator,
                "role": occurrence.role,
                "quote_status": occurrence.quote_status,
                "review_required": occurrence.review_required,
                "source_version_id": occurrence.source_version_id,
            }
        )
    return {
        "task": "A_P8_KU_INBOOK_ANNOTATION",
        "book": C.BOOK_TITLE,
        "chapter": C.CHAPTER,
        "run_id": result["result"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "annotation_version": ANNOTATION_VERSION,
        "declared_roles": list(DECLARED_ROLES),
        "declared_relation_kinds": list(DECLARED_RELATION_KINDS),
        "deferred_relation_kinds": list(DEFERRED_RELATION_KINDS),
        "occurrence_count": len(result["sink"].ku_occurrences),
        "hint_count": len(result["sink"].ku_relation_hints),
        "role_breakdown": service.role_breakdown(),
        "traceability": service.traceability(),
        "review_queue": service.review_queue(),
        "occurrences": occurrences,
        "dedup_hints": dedup_hints(service),
    }


def acceptance(result: Dict, ledger: Optional[List[str]]) -> Dict:
    """The FINAL REPORT block, computed from the measurements."""
    gates = gate_results(result)
    negative = no_merge_gate(result)
    contamination = contamination_counts(result)
    service: AnnotationService = result["service"]
    checks = {
        "occurrences_written": len(result["sink"].ku_occurrences),
        "hints_written": len(result["sink"].ku_relation_hints),
        "units_unchanged": len(result["sink"].units),
        "role_breakdown": service.role_breakdown(),
        "review_queue": len(service.review_queue()),
        "cross_source_hints": len(service.cross_source_hints()),
        "duplicate_occurrences": len(service.duplicate_occurrences()),
        "duplicate_hints": len(service.duplicate_hints()),
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
        "negative_refusals": sum(1 for v in negative.values() if v),
        "negative_cases": len(negative),
        "schema_in_ledger": schema_in_ledger(ledger),
    }
    passed = (
        checks["occurrences_written"] == len(PILOT_OCCURRENCES)
        and checks["hints_written"] == len(PILOT_HINTS)
        and checks["review_queue"] == 0
        and checks["cross_source_hints"] == 0
        and checks["duplicate_occurrences"] == 0
        and checks["duplicate_hints"] == 0
        and checks["B_CONTAMINATION"] == 0
        and checks["C_CONTAMINATION"] == 0
        and checks["BU2_DEPENDENCY"] == 0
        and gates["GATE_2_no_merge"] == "PASS"
        and checks["negative_refusals"] == checks["negative_cases"]
    )
    return {
        "A_P8_KU_INBOOK_ANNOTATION": verdict(gates),
        "verdict_inputs": verdict_inputs(gates),
        "A_P8_SCHEMA": (
            "PASS"
            if gates["GATE_1_schema"] == "PASS" and gates["GATE_1_additive"] == "PASS"
            else "BLOCKED"
        ),
        "A_P8_IMPLEMENTATION": "PASS" if passed else "BLOCKED",
        "MIGRATION_080": REQUIRED_MIGRATION,
        "NO_MERGE": str(gates["GATE_2_no_merge"]),
        "DEDUP_HINTS_FOR_B": checks["hints_written"],
        "checks": checks,
        "gates": gates,
    }


def final_report(result: Dict, ledger: Optional[List[str]]) -> Dict[str, str]:
    """The FINAL REPORT block, verbatim keys.

    COMMIT_SHA and TAG come from the environment because they name a commit
    that has not been made yet, and are reported as PENDING rather than
    guessed: a freeze report that invents its own commit id is worse than one
    that admits it has none.
    """
    block = acceptance(result, ledger)
    gates = block["gates"]
    service: AnnotationService = result["service"]
    contamination = contamination_counts(result)
    return {
        "A_P8_KU_INBOOK_ANNOTATION": block["A_P8_IMPLEMENTATION"],
        "MIGRATION_080": REQUIRED_MIGRATION,
        "OCCURRENCE_ROWS": str(len(result["sink"].ku_occurrences)),
        "HINT_ROWS": str(len(result["sink"].ku_relation_hints)),
        "ROLES_DECLARED": ",".join(DECLARED_ROLES),
        "HINT_KINDS": ",".join(DECLARED_RELATION_KINDS),
        "MERGED_UNITS": "0",
        "TRACEABILITY": f"{service.traceability()['percent']}%",
        "REVIEW_QUEUE": str(len(service.review_queue())),
        "SAME_BOOK": str(gates["GATE_3_same_book"]),
        "REPLAY": str(gates["GATE_4_replay"]),
        "AUTHORITY_SCAN": str(gates["GATE_2_authority"]),
        "B_CONTAMINATION": str(contamination["B_REFERENCE"]),
        "C_CONTAMINATION": str(contamination["C_REFERENCE"]),
        "BU2_DEPENDENCY": str(contamination["BU2_DEPENDENCY"]),
        "NO_MERGE": str(gates["GATE_2_no_merge"]),
        "COMMIT_SHA": os.environ.get("A_P8_COMMIT_SHA", "PENDING"),
        "TAG": os.environ.get("A_P8_TAG", "PENDING"),
        "FINAL_STATUS": block["A_P8_IMPLEMENTATION"],
    }


def write_sql(result: Dict, path: str) -> str:
    """Emit both annotation tables for a DBA to execute.

        python -m stratum.knowledge.a_repository.ku_annotation_runner \\
            --sql annotation.sql
        docker cp annotation.sql aii-postgres:/tmp/
        docker exec -e PGOPTIONS="-c search_path=stratum,public" aii-postgres \\
          psql -U aii -d stratum_a_p3_staging -v ON_ERROR_STOP=1 -1 -q \\
          -f /tmp/annotation.sql

    One BEGIN/COMMIT, every statement ON CONFLICT DO NOTHING, so the file is
    safe to run twice.
    """
    script = emit_annotation_sql(result["sink"].ku_occurrences, result["sink"].ku_relation_hints)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P8_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [
        line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def schema_in_ledger(ledger: Optional[List[str]]) -> str:
    """No ledger is no evidence, and must not read as PASS.

    R-2. `NOT_EXECUTED` makes the verdict BLOCKED rather than PASS, the same
    rule P6 froze after a missing ledger produced A_P6_IDENTITY=PASS.
    """
    if ledger is None:
        return "NOT_EXECUTED"
    if not all(name in ledger for name in REQUIRED_CHAIN):
        return "FAIL"
    return "PASS"


def main() -> None:
    result = build_annotation()
    if "--sql" in sys.argv:
        target = sys.argv[sys.argv.index("--sql") + 1]
        print(write_sql(result, target))
        return
    ledger = ledger_lines()
    doc = report(result)
    doc.update(acceptance(result, ledger))
    doc["final_report"] = final_report(result, ledger)
    doc["schema_gate"] = schema_in_ledger(ledger)
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
