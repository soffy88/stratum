"""A Repository P5.0 — condition / boundary runner.

Extracts condition and boundary candidates from the frozen units and reports
the acceptance gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.condition_boundary_runner

    GATE A   frozen KU immutable      no unit row changed, none deleted
    GATE B   evidence trace           every candidate reaches an evidence row
    GATE C   B/C isolation            import graph, migration FK, artifact
    GATE D   baseline invariance      the frozen baseline is untouched
    GATE E   replay                   re-extracting appends nothing
    GATE F   anchoring                every statement is verbatim from its span

Contamination is detected in three layers and reuses P7's gates rather than
reintroducing a text scan. A word scan over A仓 source returns 24 hits, all of
them A仓's own guard lists — a gate that fires on its own rulebook is a gate
that gets switched off.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import pilot_corpus as C
from .condition_boundary import (
    BOUNDARY_COLUMNS,
    CONDITION_BOUNDARY_VERSION,
    CONDITION_COLUMNS,
    NOT_YET_EXTRACTABLE_BOUNDARY_TYPES,
    NOT_YET_EXTRACTABLE_CONDITION_TYPES,
    ACTOR_DISQUALIFIERS,
    ACTOR_MARKERS,
    BoundaryType,
    ConditionBoundaryExtractor,
    ConditionBoundarySink,
    ConditionBoundaryWriter,
    ConditionType,
    TIME_DISQUALIFIERS,
    TIME_MARKERS,
    emit_condition_boundary_sql,
)
from .projection_builder import artifact_drift, external_imports
from .ku_identity_runner import build_identity
from .verdict import VERDICT_PASS, verdict, verdict_inputs


REQUIRED_MIGRATION = "077_a_condition_boundary.sql"

REQUIRED_CHAIN = (
    "070_a_repository_foundation.sql",
    "071_a_evidence_quality.sql",
    "072_a_ku_verification.sql",
    "073_a_knowledge_unit_freeze.sql",
    "074_a_ku_freeze_persistence.sql",
    "075_a_ku_evolution.sql",
    "076_a_ku_identity.sql",
    REQUIRED_MIGRATION,
)

A_ONLY_TABLES = frozenset({"ku_condition_candidate", "ku_boundary_candidate"})

#: Tables P5.0 must never create or alter. The whole point of the layer is
#: that it sits beside these and not inside them.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event")


def build_baseline(sink=None) -> Dict:
    """P1 -> P4.1 -> P5 -> P6 -> P7, rebuilt deterministically.

    This layer sits on top of the whole frozen chain, so it starts from the
    same rebuild every other stage uses rather than from a warmer one.
    """
    chain = build_identity(sink=sink) if sink is not None else build_identity()
    upstream = chain["result"]
    return {"chain": chain, "upstream": upstream, "sink": chain["sink"]}


def current_units(result: Dict) -> List:
    """Frozen units a candidate may be attached to.

    A superseded unit is left out, matching P7's navigation rule. Its
    successor carries the reading; the superseded row keeps its own.
    """
    chain = result["chain"]
    superseded = {revision.prior_unit_id
                  for revision in chain["sink"].revisions.values()}
    return [chain["sink"].units[key] for key in sorted(chain["sink"].units)
            if key not in superseded]


def run_extraction(sink=None) -> Dict:
    """Extract, write, and return everything the gates need."""
    result = build_baseline(sink=sink if sink is not None
                            else ConditionBoundarySink())
    upstream = result["upstream"]
    before = unit_snapshot(result["sink"])

    extractor = ConditionBoundaryExtractor(upstream["base"]["pipeline"])
    units = current_units(result)
    extracted = extractor.extract_run(units)
    after_extract = unit_snapshot(result["sink"])

    writer = ConditionBoundaryWriter(upstream["base"]["pipeline"],
                                     result["sink"])
    written = writer.write_all(extracted)
    after_write = unit_snapshot(result["sink"])

    return {"result": result, "sink": result["sink"], "upstream": upstream,
            "writer": writer, "extractor": extractor,
            "extracted": extracted, "written": written, "units": units,
            "before_snapshot": before,
            "after_extract": after_extract,
            "after_write": after_write}


def unit_snapshot(sink) -> Dict[str, Dict]:
    """Every durable unit row as a comparable dict.

    Taken three times: before extraction, after extraction, after the write.
    The middle one is the one that matters for `verification_logic_mutation`
    — it proves the extractor itself changed nothing, before any write
    happened.
    """
    return {key: dict(vars(unit)) for key, unit in sorted(sink.units.items())}


# ── GATE A frozen KU immutable ───────────────────────────────────────────────

def ku_mutation_gate(result: Dict) -> str:
    """No unit row changed and none disappeared.

    A unit that is not durable cannot be qualified either, so a missing unit
    would be both a mutation and an orphan.
    """
    after = unit_snapshot(result["sink"])
    for unit_id, row in result["before_snapshot"].items():
        if after.get(unit_id) != row:
            return "FAIL"
    return "PASS"


def verification_logic_gate(result: Dict) -> str:
    """The extractor changed no unit row *before* any write.

    A separate check from GATE A because the extractor is the only code here
    that could plausibly touch the baseline: it reads frozen units. If it
    wrote, this catches it even though GATE A would also fire.
    """
    return "PASS" if result["after_extract"] == \
        result["before_snapshot"] else "FAIL"


def upstream_untouched_gate() -> str:
    """077 alters nothing it inherits.

    Structural: the migration may only CREATE. Any ALTER, DROP, UPDATE or
    backfill fails the gate rather than being noticed later.
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    statements = re.sub(r"--[^\n]*", "", migration)
    for forbidden in ("ALTER TABLE", "DROP ", "UPDATE ", "INSERT INTO",
                      "TRUNCATE"):
        if forbidden in statements:
            return "FAIL"
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)",
                             statements))
    if created != A_ONLY_TABLES:
        return "FAIL"
    for table in UNTOUCHABLE_TABLES:
        if f"CREATE TABLE IF NOT EXISTS stratum.{table} (" in statements:
            return "FAIL"
    return "PASS"


# ── GATE B evidence trace ────────────────────────────────────────────────────

def evidence_gate(result: Dict) -> str:
    """Every candidate reaches an evidence row, and through a real unit."""
    writer: ConditionBoundaryWriter = result["writer"]
    sink = result["sink"]
    conditions = list(sink.conditions.values())
    boundaries = list(sink.boundaries.values())
    if not conditions and not boundaries:
        return "FAIL"
    for row in conditions + boundaries:
        if not row.evidence_ids:
            return "FAIL"
        for evidence_id in row.evidence_ids:
            if evidence_id not in result["writer"].store.evidence:
                return "FAIL"
        unit = sink.units.get(row.knowledge_unit_id)
        if unit is None or not unit.canonical_text:
            return "FAIL"
    if writer.orphan_conditions() or writer.orphan_boundaries():
        return "FAIL"
    return "PASS"


def anchoring_gate(result: Dict) -> str:
    """Every statement is a verbatim substring of the span it came from.

    This is the check that makes "source-grounded" mean something. A
    non-empty result means the layer started writing prose instead of
    quoting, which is the failure this whole design exists to prevent.
    """
    writer: ConditionBoundaryWriter = result["writer"]
    if writer.misanchored_statements():
        return "FAIL"
    return "PASS"


def traceability_percent(result: Dict) -> float:
    """candidate -> evidence -> source, as a percentage."""
    sink = result["sink"]
    store = result["writer"].store
    rows = list(sink.conditions.values()) + list(sink.boundaries.values())
    if not rows:
        return 0.0
    traced = 0
    for row in rows:
        evidence = store.evidence.get(row.evidence_ids[0])
        if evidence is None:
            continue
        if evidence.source_version_id not in store.source_versions:
            continue
        traced += 1
    return round(100.0 * traced / len(rows), 2)


# ── GATE C B/C isolation ─────────────────────────────────────────────────────

def isolation_gate(result: Dict) -> str:
    """Three layers, P7's own gates.

    1 import graph · 2 migration FK · 3 runtime artifact.
    """
    if external_imports():
        return "FAIL"
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    if referenced != {"knowledge_unit"}:
        return "FAIL"
    payload = {"condition_candidates":
               sorted(result["sink"].conditions),
               "boundary_candidates":
               sorted(result["sink"].boundaries)}
    if artifact_drift(payload):
        return "FAIL"
    return "PASS"


def contamination_counts(result: Optional[Dict] = None) -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, measured in the three layers.

    Never a word scan of this file. Scanning the source for forbidden names
    finds this module's own token list — the same self-match that produced 24
    false positives in A仓 and has now been avoided three separate times.

        1 import graph    P7's external_imports()
        2 migration FK    077's REFERENCES targets
        3 runtime artifact  the rows this layer actually wrote
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", migration))
    schema_drift = 0 if referenced <= {"knowledge_unit"} else len(referenced)

    artifact = {}
    if result is not None:
        artifact = {"conditions": sorted(result["sink"].conditions),
                    "boundaries": sorted(result["sink"].boundaries)}
    return {"B_REFERENCE": len(external_imports()) + schema_drift
            + len(artifact_drift(artifact)),
            "C_REFERENCE": len(external_imports()) + schema_drift
            + len(artifact_drift(artifact))}


# ── GATE D baseline invariance ───────────────────────────────────────────────

def baseline_invariance_gate(result: Dict) -> str:
    """Extraction plus writing left every frozen unit byte-identical."""
    return "PASS" if result["after_write"] == \
        result["before_snapshot"] else "FAIL"


def extraction_purity_gate() -> str:
    """The extractor holds no write path to anything upstream.

    Checked on the source, because a class that could mutate is a class that
    will eventually be asked to.
    """
    source = (Path(__file__).parent / "condition_boundary.py").read_text(
        encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    code = re.sub(r"^\s*#.*$", "", code, flags=re.MULTILINE)
    # No write to any field the frozen chain owns, and no call that would
    # change a verdict. Checked as code, with docstrings and comments
    # stripped, so the prose that *describes* the prohibition does not trip
    # the check that enforces it.
    for pattern in (r"\bslots\[",
                    r"\brequired_slots\s*=",
                    r"\bverification_score\s*=",
                    r"\.freeze_status\s*=",
                    r"\btransition\s*\(",
                    r"\bSemanticIntegrity\s*\(",
                    r"\bfrozen_units\[.*\]\s*="):
        if re.search(pattern, code):
            return "FAIL"
    if re.search(r"^[ \t]*(INSERT|UPDATE|DELETE|DROP)\b", code, re.MULTILINE):
        return "FAIL"
    return "PASS"


# ── GATE E replay ────────────────────────────────────────────────────────────

def replay_gate() -> Dict[str, object]:
    """Re-extract and re-write: same fingerprints, nothing new."""
    first = run_extraction()
    before = _fingerprint(first["result"]["sink"])
    second_units = current_units(first["result"])
    extractor = first["extractor"]
    again = extractor.extract_run(second_units)
    first["writer"].write_all(again)
    after = _fingerprint(first["result"]["sink"])

    fresh = run_extraction()
    return {
        "conditions": len(first["result"]["sink"].conditions),
        "boundaries": len(first["result"]["sink"].boundaries),
        "identical_fingerprints": int(before == after),
        "rebuild_identical": int(before == _fingerprint(fresh["result"]["sink"])),
        "NEW_CONDITION": max(0, len(after.get("condition", {}))
                              - len(before.get("condition", {}))),
        "NEW_BOUNDARY": max(0, len(after.get("boundary", {}))
                             - len(before.get("boundary", {}))),
    }


def _fingerprint(sink) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {"condition": {}, "boundary": {}}
    for key in sorted(sink.conditions):
        row = sink.conditions[key]
        out["condition"][key] = row.condition_hash
    for key in sorted(sink.boundaries):
        row = sink.boundaries[key]
        out["boundary"][key] = row.boundary_hash
    return out


def idempotency_gate(result: Dict) -> str:
    """Writing the same candidates twice appends nothing."""
    writer: ConditionBoundaryWriter = result["writer"]
    before = _fingerprint(result["sink"])
    writer.write_all(writer.extractor.extract_run(result["units"]))
    return "PASS" if _fingerprint(result["sink"]) == before else "FAIL"


# ── vocabulary gates ─────────────────────────────────────────────────────────

def vocabulary_gate() -> str:
    """Declared types, admitted types and markers agree with the schema.

    The three failure modes this catches, all of which happened once during
    development: a value the code emits and the schema rejects, a factor
    name admitted with no extractor behind it, and a marker list that
    silently reintroduces a known false positive.
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    clean = re.sub(r"--[^\n]*", "", migration)
    # Compared one block at a time. A set of tuples plus `pop()` assigns the
    # two vocabularies in arbitrary order, which made this gate fail at
    # random rather than report anything real.
    declared_condition = set(re.findall(
        r"'([A-Z_]+)'",
        clean.split(
            "CREATE TABLE IF NOT EXISTS stratum.ku_condition_candidate"
        )[1].split("CHECK")[1]))
    declared_boundary = set(re.findall(
        r"'([A-Z_]+)'",
        clean.split(
            "CREATE TABLE IF NOT EXISTS stratum.ku_boundary_candidate"
        )[1].split("CHECK")[1]))
    if declared_condition != {t.value for t in ConditionType}:
        return "FAIL"
    if declared_boundary != {t.value for t in BoundaryType}:
        return "FAIL"
    # Withheld factors must not appear in the schema or the code's enum.
    for name in NOT_YET_EXTRACTABLE_CONDITION_TYPES:
        if name in {t.value for t in ConditionType}:
            return "FAIL"
    for name in NOT_YET_EXTRACTABLE_BOUNDARY_TYPES:
        if name in {t.value for t in BoundaryType}:
            return "FAIL"
    # Disqualified markers must not be in play.
    if any(bad in marker for marker in ACTOR_MARKERS
           for bad in ACTOR_DISQUALIFIERS):
        return "FAIL"
    if any(bad in marker for marker in TIME_MARKERS
           for bad in TIME_DISQUALIFIERS):
        return "FAIL"
    return "PASS"


def column_parity_gate() -> str:
    """Every column the writer emits, the schema declares.

    Added because 077 shipped once referencing two columns it never declared,
    and every insert failed against a real database. Reading either file does
    not catch it; the disagreement does.
    """
    migration = (Path(__file__).parents[2] / "db" / "pg_migrations"
                 / REQUIRED_MIGRATION).read_text(encoding="utf-8")
    for table, columns, dataclass_fields in (
            ("ku_condition_candidate", CONDITION_COLUMNS,
             ("id", "knowledge_unit_id", "condition_type", "statement",
              "evidence_ids", "extractor_version", "confidence",
              "condition_hash", "status", "created_at")),
            ("ku_boundary_candidate", BOUNDARY_COLUMNS,
             ("id", "knowledge_unit_id", "boundary_type", "statement",
              "evidence_ids", "extractor_version", "confidence",
              "boundary_hash", "status", "created_at"))):
        declared = _declared_columns(migration, table)
        if not set(columns) <= declared:
            return "FAIL"
        if not set(columns) <= set(dataclass_fields):
            return "FAIL"
    return "PASS"


def _table_body(text: str, table: str) -> str:
    """The inside of one CREATE TABLE, up to its closing paren.

    Depth-aware rather than line- or blank-line-based: a column's CHECK
    clause spans several lines, and a comment block puts a blank line inside
    the parentheses. Both fooled a simpler reader here.
    """
    block = text.split(f"CREATE TABLE IF NOT EXISTS stratum.{table}")[1]
    # Comments live inside the parentheses in this migration, and a comma in
    # a comment would otherwise split one "column" out of a sentence.
    block = re.sub(r"--[^\n]*", "", block)
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


def _split_top_level(body: str) -> List[str]:
    """Split on commas that are not inside parentheses."""
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
    return parts


def _declared_columns(text: str, table: str) -> set:
    declared = set()
    for fragment in _split_top_level(_table_body(text, table)):
        fragment = fragment.strip()
        if not fragment:
            continue
        head = fragment.split()[0]
        if head.upper() in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY",
                            "FOREIGN", "REFERENCES"}:
            continue
        declared.add(head)
    return declared


# ── gates ────────────────────────────────────────────────────────────────────

GATE_ORDER = ("GATE_A_frozen_ku_immutable", "GATE_B_evidence_trace",
              "GATE_C_isolation", "GATE_D_baseline_invariance",
              "GATE_E_replay", "GATE_F_anchoring")


#: What the three measurement gates must equal. Stated here rather than left
#: implicit, because these three were previously emitted as bare numbers inside
#: `gates` -- a percentage and two contamination counts. A gate whose value is a
#: float cannot be read by the shared verdict contract, which treats an
#: unrecognised value as BLOCKED; it would have pinned this layer to BLOCKED
#: forever, or tempted someone to special-case it outside the contract.
TRACEABILITY_REQUIRED = 100.0
CONTAMINATION_REQUIRED = 0


def _equals(measured: object, required: object) -> str:
    """One measurement as a gate status, against a stated requirement."""
    return VERDICT_PASS if measured == required else "FAIL"


def gate_results(result: Dict) -> Dict[str, object]:
    """Every gate, every one a status the shared verdict contract can read.

    None can be NOT_EXECUTED: they all run on real rows. The measurements
    behind the three converted gates stay visible in `acceptance()["checks"]`.
    """
    replay = replay_gate()
    trace = traceability_percent(result)
    contamination = contamination_counts(result)
    return {
        "GATE_A_frozen_ku_immutable": ku_mutation_gate(result),
        "GATE_A_verification_logic": verification_logic_gate(result),
        "GATE_A_upstream_untouched": upstream_untouched_gate(),
        "GATE_B_evidence_trace": evidence_gate(result),
        "GATE_B_traceability_percent": _equals(trace, TRACEABILITY_REQUIRED),
        "GATE_C_isolation": isolation_gate(result),
        "GATE_C_B_REFERENCE": _equals(contamination["B_REFERENCE"],
                                      CONTAMINATION_REQUIRED),
        "GATE_C_C_REFERENCE": _equals(contamination["C_REFERENCE"],
                                      CONTAMINATION_REQUIRED),
        "GATE_D_baseline_invariance": baseline_invariance_gate(result),
        "GATE_D_extraction_purity": extraction_purity_gate(),
        "GATE_E_replay": "PASS" if (replay["identical_fingerprints"] == 1
                                    and replay["rebuild_identical"] == 1
                                    and replay["NEW_CONDITION"] == 0
                                    and replay["NEW_BOUNDARY"] == 0) else "FAIL",
        "GATE_E_idempotency": idempotency_gate(result),
        "GATE_F_anchoring": anchoring_gate(result),
        "schema_vocabulary": vocabulary_gate(),
        "schema_column_parity": column_parity_gate(),
    }


# ── reporting ────────────────────────────────────────────────────────────────

def report(result: Dict) -> Dict:
    sink = result["sink"]
    return {
        "task": "A_P5_0_CONDITION_BOUNDARY",
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "run_id": result["upstream"]["base"]["reading_run_id"],
        "authority": "A_REPOSITORY",
        "mode": "ADDITIVE_ONLY",
        "units_considered": len(result["units"]),
        "condition_candidates": len(sink.conditions),
        "boundary_candidates": len(sink.boundaries),
        "condition_types": sorted({row.condition_type
                                   for row in sink.conditions.values()}),
        "boundary_types": sorted({row.boundary_type
                                  for row in sink.boundaries.values()}),
        "units_with_a_condition": len({row.knowledge_unit_id
                                       for row in sink.conditions.values()}),
        "withheld_condition_types": list(NOT_YET_EXTRACTABLE_CONDITION_TYPES),
        "withheld_boundary_types": list(NOT_YET_EXTRACTABLE_BOUNDARY_TYPES),
        "conditions": [
            {"id": row.id, "knowledge_unit_id": row.knowledge_unit_id,
             "condition_type": row.condition_type,
             "statement": row.statement, "evidence_ids": row.evidence_ids,
             "confidence": row.confidence, "status": row.status}
            for row in sorted(sink.conditions.values(), key=lambda r: r.id)],
        "boundaries": [
            {"id": row.id, "knowledge_unit_id": row.knowledge_unit_id,
             "boundary_type": row.boundary_type, "statement": row.statement,
             "evidence_ids": row.evidence_ids, "confidence": row.confidence,
             "status": row.status}
            for row in sorted(sink.boundaries.values(), key=lambda r: r.id)],
        "extractor_version": CONDITION_BOUNDARY_VERSION,
    }


def acceptance(result: Dict) -> Dict[str, object]:
    """The task's final acceptance block, computed from measured values."""
    gates = gate_results(result)
    # The measurement. Reading the gate here would put a status string where
    # the acceptance block reports a percentage.
    trace = traceability_percent(result)
    replay = replay_gate()
    contamination = contamination_counts(result)
    checks = {
        "FROZEN_KU_MUTATION": 0 if gates["GATE_A_frozen_ku_immutable"] == "PASS"
        else 1,
        "VERIFICATION_LOGIC_MUTATION": 0
        if gates["GATE_A_verification_logic"] == "PASS" else 1,
        "EVIDENCE_TRACEABILITY": trace,
        "ORPHAN": len(result["writer"].orphan_conditions())
        + len(result["writer"].orphan_boundaries()),
        "REPLAY": "PASS" if gates["GATE_E_replay"] == "PASS" else "FAIL",
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "ANCHORING": gates["GATE_F_anchoring"],
        "SCHEMA_VOCABULARY": gates["schema_vocabulary"],
        "SCHEMA_COLUMN_PARITY": gates["schema_column_parity"],
        "BOUNDARY_CANDIDATES": result["sink"].boundaries.__len__(),
        "CONDITION_CANDIDATES": result["sink"].conditions.__len__(),
        "NEW_CONDITION_ON_REPLAY": replay["NEW_CONDITION"],
        "NEW_BOUNDARY_ON_REPLAY": replay["NEW_BOUNDARY"],
    }
    # The verdict used to be a hand-written conjunction over `checks`, naming
    # nine of the fifteen gates. The other six -- upstream_untouched,
    # evidence_trace, isolation, baseline_invariance, extraction_purity and
    # idempotency -- could print PASS and change nothing. Same defect P5
    # Evolution and P6 were reopened for, in the layer that was supposed to be
    # the example. The verdict now comes from every gate the function reports.
    #
    # `checks` is kept: it is the measurement record, and it is where the
    # numbers behind the converted gates stay readable.
    orphan = checks["ORPHAN"]
    return {"checks": checks,
            "A_P5_0_CONDITION_BOUNDARY": verdict(gates),
            "orphan_conditions_and_boundaries": orphan,
            "verdict_inputs": verdict_inputs(gates),
            "gates": gates}


def write_sql(result: Dict, path: str) -> str:
    """Emit the two candidate tables for a DBA to execute."""
    script = emit_condition_boundary_sql(
        result["upstream"]["base"]["pipeline"].store,
        result["sink"].conditions, result["sink"].boundaries)
    Path(path).write_text(script, encoding="utf-8")
    return path


def ledger_lines(path: Optional[str] = None) -> Optional[List[str]]:
    target = path or os.environ.get("A_P5_0_LEDGER_FILE")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return [line.strip() for line in
            source.read_text(encoding="utf-8").splitlines() if line.strip()]


def durable_counts(path: Optional[str] = None) -> Optional[Dict[str, int]]:
    target = path or os.environ.get("A_P5_0_DB_COUNTS")
    if not target:
        return None
    source = Path(target)
    if not source.exists():
        return None
    return {key: int(value) for key, value in re.findall(
        r"(\w+)\s*=\s*(\d+)",
        source.read_text(encoding="utf-8"))} or None


def main() -> None:
    result = run_extraction()
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
