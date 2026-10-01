"""A Repository P5.5 — paper evidence composite FK repair runner.

Validates migration 082 and reports the five gates.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.paper_evidence_fk_runner

    Gate 1 Schema      one index, one ADD CONSTRAINT, no row mutation
    Gate 2 Data        every stored declaration satisfies the tie
    Gate 3 Negative    cross-catalog, unknown paper, unknown catalog — refused
    Gate 4 Replay      a second execution reports ALREADY_APPLIED
    Gate 5 Authority   the new foreign key points at an A table only

This stage records **nothing new**. 082 adds a rule to a table 080 already
built: a declaration may only be attributed to the catalog row its own candidate
is about. Measured before the repair, that tie was service-enforced only, and the
schema accepted a cross-catalog declaration outright.

Because the gates here are about the *live database* rather than about an
in-memory sink, this runner talks to psql and reports what the database actually
does. Everything it asserts is reproducible by hand from the queries it prints.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .projection_builder import artifact_drift, external_imports


REQUIRED_MIGRATION = "082_a_paper_evidence_composite_fk.sql"

REPAIR_VERSION = "a-p5-5-v0.1"

#: The index STEP 1 creates, and the constraint STEP 2 adds. Named so the gates
#: assert these exact objects rather than "a constraint was added somehow".
EXPECTED_INDEX = "paper_source_candidate_id_book_source_uniq"
EXPECTED_CONSTRAINT = "paper_evidence_same_catalog_source_fk"

#: The FK target must be an A table and nothing else.
ALLOWED_FK_TARGETS = frozenset({"paper_source_candidate"})

#: Baseline the repair must not disturb. These are row counts, not index
#: counts: knowledge_unit has 10 indexes and 11 rows, and the distinction has
#: already been recorded once.
BASELINE_ANCHOR = {
    "knowledge_unit": 11,
    "ku_freeze_event": 12,
    "ku_revision": 1,
    "ku_identity": 11,
}

#: Tables 082 must not create or alter.
UNTOUCHABLE_TABLES = ("knowledge_unit", "ku_candidate", "ku_verification",
                      "ku_freeze_event", "ku_identity", "ku_revision",
                      "ku_review_event", "ku_condition_candidate",
                      "ku_boundary_candidate", "ku_relation",
                      "mechanism_candidate", "mechanism_node",
                      "relation_candidate", "constraint_candidate")


# ── database access ──────────────────────────────────────────────────────────

def _connection() -> Dict[str, str]:
    """Connection settings, overridable so this is not hard-coded to one box."""
    return {
        "container": os.environ.get("A_PG_CONTAINER", "aii-postgres"),
        "user": os.environ.get("A_PG_USER", "aii"),
        "database": os.environ.get("A_PG_DATABASE", "stratum_a_p3_staging"),
    }


def _psql(sql: str, expect_error: bool = False) -> Tuple[bool, str]:
    """Run SQL inside the container. Returns (succeeded, combined output).

    `expect_error` exists for the negative probes: a refused statement must
    *fail*, and a probe that swallowed its own error would report a refusal that
    never happened.
    """
    conn = _connection()
    handle = subprocess.run(
        ["docker", "exec", "-i", "-e", "PGOPTIONS=-c search_path=stratum,public",
         conn["container"], "psql", "-U", conn["user"], "-d", conn["database"],
         # -t -A: tuples only, unaligned. Without them psql prints a header
         # rule and a trailing "(1 row)", so the last line of any single-value
         # query is "(1 row)" rather than the value — which silently turns every
         # count comparison into a FAIL.
         "-v", "ON_ERROR_STOP=1", "-q", "-t", "-A", "-f", "-"],
        input=sql, capture_output=True, text=True, timeout=180)
    output = (handle.stdout + handle.stderr).strip()
    ok = handle.returncode == 0
    if expect_error:
        return (not ok), output
    return ok, output


# ── Gate 1 schema ────────────────────────────────────────────────────────────

def _migration() -> str:
    return (Path(__file__).parents[2] / "db" / "pg_migrations"
            / REQUIRED_MIGRATION).read_text(encoding="utf-8")


def _clean() -> str:
    return re.sub(r"--[^\n]*", "", _migration())


def _statements() -> List[str]:
    """Executable statements only, one per entry.

    Comment-stripped first, because the header discusses DROP, RENAME and NOT
    VALID at length while containing none of them. A substring check over the raw
    file would therefore report violations that are prose.
    """
    body = _clean()
    return [chunk.strip() for chunk in body.split(";") if chunk.strip()]


def schema_gate() -> str:
    """One index, one ADD CONSTRAINT, nothing destructive."""
    statements = _statements()
    if len(statements) != 2:
        return "FAIL"
    index, alter = statements
    if not index.upper().startswith("CREATE UNIQUE INDEX IF NOT EXISTS"):
        return "FAIL"
    if EXPECTED_INDEX not in index:
        return "FAIL"
    if "ON stratum.paper_source_candidate (id, book_source_id)" not in index:
        return "FAIL"
    if not alter.upper().startswith("ALTER TABLE STRATUM.PAPER_EVIDENCE"):
        return "FAIL"
    if alter.upper().count("ADD CONSTRAINT") != 1:
        return "FAIL"
    if EXPECTED_CONSTRAINT not in alter:
        return "FAIL"
    # The only ALTER permitted is ADD CONSTRAINT, so nothing may alter a column,
    # drop, rename or mutate. Checked two ways on purpose:
    #
    #   * a destructive verb is rejected only as a *statement-initial* token.
    #     A substring test for "DELETE " matches the ON DELETE RESTRICT that the
    #     spec mandates, so the naive version of this check forbids the exact
    #     clause 082 is required to write. Same shape of bug as the
    #     array_length finding in 077 and the locator/location rename.
    #   * ALTER COLUMN and NOT VALID are rejected anywhere, because neither has
    #     a legitimate appearance in this statement.
    normalised = " ".join(alter.upper().split())
    for verb in ("DROP", "RENAME", "UPDATE", "DELETE", "INSERT", "TRUNCATE"):
        if normalised.startswith(verb):
            return "FAIL"
    for forbidden in ("ALTER COLUMN", "NOT VALID"):
        if forbidden in normalised:
            return "FAIL"
    if "ON DELETE RESTRICT" not in normalised:
        return "FAIL"
    return "PASS"


def index_target_gate() -> str:
    """STEP 1 must be declared before STEP 2.

    Measured on 079 and 080: with the index after the table, PostgreSQL refuses
    the foreign key with "no unique constraint matching given keys". The DDL is
    transactional so the migration rolls back cleanly, but the ordering is still
    load-bearing and is asserted rather than assumed.
    """
    clean = _clean()
    return "PASS" if clean.index("CREATE UNIQUE INDEX") < \
        clean.index("ADD CONSTRAINT") else "FAIL"


def no_new_lifecycle_gate() -> str:
    """082 adds no event, no status, no revision.

    A schema integrity repair is not a new knowledge artifact.
    """
    clean = _clean().upper()
    for forbidden in ("FREEZE_EVENT", "VERIFICATION_EVENT", "KU_REVISION",
                      "STATUS", "INSERT INTO"):
        if forbidden in clean:
            return "FAIL"
    return "PASS"


def index_present_gate() -> str:
    """The FK target exists in the live database."""
    ok, output = _psql(
        f"SELECT 1 FROM pg_indexes WHERE schemaname='stratum' "
        f"AND indexname='{EXPECTED_INDEX}';")
    return "PASS" if ok and "1" in output else "FAIL"


def constraint_present_gate() -> str:
    """The composite foreign key exists in the live database."""
    ok, output = _psql(
        f"SELECT confdeltype FROM pg_constraint WHERE conname="
        f"'{EXPECTED_CONSTRAINT}';")
    # confdeltype 'r' is RESTRICT. 'a' would mean NO ACTION, which is close but
    # not the verb every frozen A table uses, so it is not accepted here.
    return "PASS" if ok and output.strip().endswith("r") else "FAIL"


def row_mutation_gate() -> str:
    """No row in either table changed.

    The repair adds a rule, so the row counts and the stored values must be
    exactly what they were. Compared against the live tables rather than a
    snapshot, because 082 has no in-memory model to compare to.
    """
    ok, output = _psql(
        "SELECT (SELECT count(*) FROM stratum.paper_source_candidate)||'/'||"
        "(SELECT count(*) FROM stratum.paper_evidence);")
    if not ok:
        return "FAIL"
    counts = output.strip().splitlines()[-1].strip()
    return "PASS" if counts == "1/4" else "FAIL"


# ── Gate 2 existing data ─────────────────────────────────────────────────────

def existing_data_gate() -> str:
    """Every stored declaration satisfies the tie.

    Note this is also enforced by the DDL: ADD CONSTRAINT for a foreign key
    validates existing rows unless declared NOT VALID, so a stored cross-catalog
    declaration would have aborted the migration. This query is the readable
    version of that fact.
    """
    ok, output = _psql(
        "SELECT count(*) FROM stratum.paper_evidence e "
        "JOIN stratum.paper_source_candidate c ON c.id = e.paper_id "
        "WHERE e.catalog_source_id <> c.book_source_id;")
    return "PASS" if ok and output.strip().splitlines()[-1].strip() == "0" else \
        "FAIL"


def baseline_gate() -> str:
    """The frozen A chain underneath is undisturbed."""
    ok, output = _psql(
        "SELECT (SELECT count(*) FROM stratum.knowledge_unit)||'/'||"
        "(SELECT count(*) FROM stratum.ku_freeze_event)||'/'||"
        "(SELECT count(*) FROM stratum.ku_revision)||'/'||"
        "(SELECT count(*) FROM stratum.ku_identity);")
    if not ok:
        return "FAIL"
    anchor = "/".join(
        str(BASELINE_ANCHOR[key]) for key in
        ("knowledge_unit", "ku_freeze_event", "ku_revision", "ku_identity"))
    return "PASS" if output.strip().splitlines()[-1].strip() == anchor else "FAIL"


# ── Gate 3 negative ──────────────────────────────────────────────────────────

def negative_db_gate() -> Dict[str, bool]:
    """The three refusals 080 could not produce. Must actually fail.

    Each probe runs in its own transaction and rolls back. `expect_error=True`
    means a statement that *succeeded* counts as a failure of the gate — a probe
    that swallowed its own error would report a refusal that never happened.
    """
    setup = """
        BEGIN;
        INSERT INTO stratum.book_source
          (id,title,author,publisher,isbn,language,metadata,created_at)
          VALUES ('bs_probe','Probe','Probe Author','Probe Press','0000000000000',
                  'zh','{}'::jsonb,NOW())
          ON CONFLICT DO NOTHING;
    """
    # CASE_1: a real paper, a real catalog row, but not the one it owns.
    cross = setup + """
        INSERT INTO stratum.paper_evidence
          (id,paper_id,statement_type,declared_value,declared_in,
           catalog_source_id,evidence_hash)
        SELECT 'peh_case1',
               (SELECT id FROM stratum.paper_source_candidate LIMIT 1),
               'AUTHOR',(SELECT author FROM stratum.book_source
                         WHERE id='bs_probe'),'BOOK_SOURCE_CATALOG','bs_probe',
               'peh_case1';
        ROLLBACK;
    """
    unknown_paper = setup + """
        INSERT INTO stratum.paper_evidence
          (id,paper_id,statement_type,declared_value,declared_in,
           catalog_source_id,evidence_hash)
        SELECT 'peh_case2','psc_absent','AUTHOR','Probe Author',
               'BOOK_SOURCE_CATALOG','bs_probe','peh_case2';
        ROLLBACK;
    """
    unknown_catalog = setup + """
        INSERT INTO stratum.paper_evidence
          (id,paper_id,statement_type,declared_value,declared_in,
           catalog_source_id,evidence_hash)
        SELECT 'peh_case3',
               (SELECT id FROM stratum.paper_source_candidate LIMIT 1),
               'AUTHOR','Probe Author','BOOK_SOURCE_CATALOG','bs_absent',
               'peh_case3';
        ROLLBACK;
    """
    same_catalog = setup + """
        INSERT INTO stratum.paper_evidence
          (id,paper_id,statement_type,declared_value,declared_in,
           catalog_source_id,evidence_hash)
        SELECT 'peh_ok',
               (SELECT id FROM stratum.paper_source_candidate LIMIT 1),
               'AUTHOR',
               (SELECT author FROM stratum.paper_source_candidate c
                 JOIN stratum.book_source b ON b.id = c.book_source_id
                 WHERE c.id = (SELECT id FROM stratum.paper_source_candidate
                                LIMIT 1)),
               'BOOK_SOURCE_CATALOG',
               (SELECT book_source_id FROM stratum.paper_source_candidate
                 LIMIT 1),
               'peh_ok';
        ROLLBACK;
    """

    def refused(sql: str) -> bool:
        ok, _ = _psql(sql, expect_error=True)
        return ok

    def accepted(sql: str) -> bool:
        ok, _ = _psql(sql)
        return ok

    return {
        # The point of the repair: this one was ACCEPTED before 082.
        "cross_catalog_refused": refused(cross),
        "unknown_paper_refused": refused(unknown_paper),
        "unknown_catalog_refused": refused(unknown_catalog),
        # And the honest case must still be accepted, or the constraint is wrong
        # rather than strict.
        "same_catalog_accepted": accepted(same_catalog),
    }


# ── Gate 4 replay ────────────────────────────────────────────────────────────

def replay_gate() -> Dict[str, object]:
    """Report whether a second execution of the migration would be a no-op.

    **This gate is read-only by default and executes no DDL.** That is the whole
    point of the flag: an earlier version of this runner ran the migration from
    inside `replay_gate()`, so merely *inspecting* the gates applied 082 to the
    staging database while the ledger still said 081. A validation step that
    mutates the thing it validates is a trap, and the ledger disagreement it
    caused is the same class of error already recorded once, at 079.

    So:
      * default              — inspect only. Asserts both objects exist exactly
                              once, which is the idempotency property that can
                              be checked without writing anything.
      * A_P5_5_EXECUTE_REPLAY=1 — actually run the migration a second time and
                              classify the outcome. This is the only path that
                              executes DDL, and it is opt-in.

    Expected second-run behaviour: STEP 1 is IF NOT EXISTS and is a silent no-op;
    STEP 2 has no IF NOT EXISTS in PostgreSQL, and the usual workaround is a DO
    block — which is an anonymous function, and this project does not introduce
    functions into A仓. So the second execution is expected to fail with
    "already exists", and that failure is the signal.
    """
    duplicates = duplicate_objects()
    read_only = {
        "duplicate_objects": len(duplicates),
        "index_present": int(index_present_gate() == "PASS"),
        "constraint_present": int(constraint_present_gate() == "PASS"),
        "executed": 0,
        "reported_already_applied": 0,
    }
    if os.environ.get("A_P5_5_EXECUTE_REPLAY") != "1":
        return read_only
    ok, output = _psql(_migration(), expect_error=True)
    already = "already exists" in output
    return {
        "duplicate_objects": len(duplicates),
        "index_present": int(index_present_gate() == "PASS"),
        "constraint_present": int(constraint_present_gate() == "PASS"),
        "executed": 1,
        # `_psql(..., expect_error=True)` already inverts its return: `ok` here
        # means the statement was refused, which is the expected outcome. Reading
        # it the other way round reported `second_run_failed: 0` on a run that
        # did fail.
        "second_run_refused": int(ok),
        "reported_already_applied": int(already),
    }


def duplicate_objects() -> List[str]:
    """Objects that exist more than once — which cannot happen, and is checked."""
    ok, output = _psql(
        "SELECT name FROM ("
        "  SELECT indexname AS name, count(*) FROM pg_indexes"
        "   WHERE schemaname='stratum' AND indexname='"
        + EXPECTED_INDEX + "' GROUP BY indexname HAVING count(*) > 1"
        "  UNION ALL"
        "  SELECT conname, count(*) FROM pg_constraint"
        "   WHERE conname='" + EXPECTED_CONSTRAINT
        + "' GROUP BY conname HAVING count(*) > 1"
        ") d;")
    return output.strip().splitlines() if ok and output.strip() else []


# ── Gate 5 authority ─────────────────────────────────────────────────────────

def authority_gate() -> str:
    """The new foreign key points at an A table, and only one."""
    ok, output = _psql(
        "SELECT confrelid::regclass::text FROM pg_constraint "
        f"WHERE conname='{EXPECTED_CONSTRAINT}';")
    if not ok:
        return "FAIL"
    targets = {line.strip() for line in output.strip().splitlines() if line.strip()}
    if not targets <= ALLOWED_FK_TARGETS:
        return "FAIL"
    return "PASS"


def contamination_counts() -> Dict[str, int]:
    """B_REFERENCE and C_REFERENCE, in the two layers this project uses."""
    ok, output = _psql(
        "SELECT count(*) FROM pg_constraint WHERE conname='"
        + EXPECTED_CONSTRAINT + "' AND confrelid::regclass::text ~ "
        "'(bu_|chapter_bu|aii_refined|refined_|learning|mastery)';")
    outside = 0
    if ok and output.strip():
        outside = int(output.strip().splitlines()[-1].strip())
    clean = _clean()
    forbidden_fk = len(re.findall(r"REFERENCES\s+stratum\.(?!paper_source_candidate)",
                                  clean))
    imports = len(external_imports())
    payload = {"repair": EXPECTED_CONSTRAINT}
    drift = len(artifact_drift(payload))
    total = outside + forbidden_fk + imports + drift
    return {"B_REFERENCE": total, "C_REFERENCE": total,
            "BU2_DEPENDENCY": outside + forbidden_fk,
            "FK_OUTSIDE_A": outside,
            "external_imports": imports}


def schema_reports_only_two_objects() -> str:
    """082 declares exactly one index and one constraint, and nothing else."""
    clean = _clean()
    if clean.count("CREATE UNIQUE INDEX") != 1:
        return "FAIL"
    if clean.count("ADD CONSTRAINT") != 1:
        return "FAIL"
    if clean.count("CREATE TABLE") != 0:
        return "FAIL"
    for table in UNTOUCHABLE_TABLES:
        if f"ALTER TABLE stratum.{table}" in clean:
            return "FAIL"
    return "PASS"


# ── gates ────────────────────────────────────────────────────────────────────

def gate_results() -> Dict[str, object]:
    """The five acceptance gates plus the checks behind them."""
    replay = replay_gate()
    negative = negative_db_gate()
    return {
        "GATE_1_schema": schema_gate(),
        "GATE_1_index_target": index_target_gate(),
        "GATE_1_two_objects": schema_reports_only_two_objects(),
        "GATE_1_index_present": index_present_gate(),
        "GATE_1_constraint_present": constraint_present_gate(),
        "GATE_1_no_new_lifecycle": no_new_lifecycle_gate(),
        "GATE_1_rows_unmutated": row_mutation_gate(),
        "GATE_2_existing_data": existing_data_gate(),
        "GATE_2_baseline": baseline_gate(),
        "GATE_3_negative": "PASS" if all(negative.values()) else "FAIL",
        "GATE_3_negative_detail": negative,
        "GATE_4_replay": "PASS" if (
            replay["duplicate_objects"] == 0
            and replay["index_present"] == 1
            and replay["constraint_present"] == 1
            # When the second execution was requested, it must also have
            # produced the expected "already exists" signal.
            and (replay["executed"] == 0
                 or replay["reported_already_applied"] == 1))
        else "FAIL",
        "GATE_4_replay_detail": replay,
        "GATE_5_authority": authority_gate(),
    }


_SCHEMA_GATES = ("GATE_1_schema", "GATE_1_index_target",
                 "GATE_1_two_objects", "GATE_1_index_present",
                 "GATE_1_constraint_present", "GATE_1_no_new_lifecycle",
                 "GATE_1_rows_unmutated")


# ── reporting ────────────────────────────────────────────────────────────────

def report() -> Dict:
    gates = gate_results()
    return {
        "task": "STRATUM_A_P5_5_082_PAPER_EVIDENCE_COMPOSITE_FK_REPAIR",
        "authority": "A_REPOSITORY",
        "repair_version": REPAIR_VERSION,
        "migration": REQUIRED_MIGRATION,
        "new_index": EXPECTED_INDEX,
        "new_foreign_key": EXPECTED_CONSTRAINT,
        "fk_target": "paper_source_candidate (id, book_source_id)",
        "delete_verb": "RESTRICT",
        "baseline_anchor": dict(BASELINE_ANCHOR),
        "baseline_note": "row counts, not index counts",
        "gates": gates,
        "closes_limitation": "P5.3 §3.3 — paper declaration catalog ownership "
                             "was service enforced only",
        "status_limitation": "database enforced",
        "notes": REPAIR_NOTES,
    }


REPAIR_NOTES = {
    "ALTER_SCOPE": "ADD_CONSTRAINT_ONLY",
    "NEW_INDEX": 1,
    "NEW_FK": 1,
    "ROWS_MUTATED": 0,
    "NEW_LIFECYCLE": "none",
    "REPLAY_SIGNAL": "MIGRATION_ALREADY_APPLIED",
    "REPLAY_NOTE": (
        "PostgreSQL has no IF NOT EXISTS for ADD CONSTRAINT and the usual "
        "workaround is a DO block, which is an anonymous function. A仓 "
        "introduces no functions, so the second execution is expected to fail "
        "with 'already exists' and that failure is the signal."),
    "EXISTING_DATA_VALIDATED_BY": (
        "the DDL itself: ADD CONSTRAINT for a foreign key validates existing "
        "rows unless NOT VALID, so a stored cross-catalog declaration would "
        "have aborted the migration"),
    "AUTHORITY_UNCHANGED": (
        "082 records nothing new. No freeze_event, no verification_event, no "
        "revision, no status. Only what the database tolerates has changed."),
}


def acceptance() -> Dict[str, object]:
    """The spec's COMMIT GATE block, computed from measurements."""
    gates = gate_results()
    contamination = contamination_counts()
    negative = gates["GATE_3_negative_detail"]
    checks = {
        "composite_fk_exists": gates["GATE_1_constraint_present"],
        "fk_target_present": gates["GATE_1_index_present"],
        "same_catalog_accepted": negative["same_catalog_accepted"],
        "cross_catalog_refused": negative["cross_catalog_refused"],
        "unknown_paper_refused": negative["unknown_paper_refused"],
        "unknown_catalog_refused": negative["unknown_catalog_refused"],
        "existing_data_valid": gates["GATE_2_existing_data"],
        "rows_mutated": 0 if gates["GATE_1_rows_unmutated"] == "PASS" else -1,
        "baseline_intact": gates["GATE_2_baseline"],
        "replay_classified": gates["GATE_4_replay"],
        "FK_OUTSIDE_A": contamination["FK_OUTSIDE_A"],
        "B_CONTAMINATION": contamination["B_REFERENCE"],
        "C_CONTAMINATION": contamination["C_REFERENCE"],
        "BU2_DEPENDENCY": contamination["BU2_DEPENDENCY"],
    }
    passed = (checks["composite_fk_exists"] == "PASS"
              and checks["fk_target_present"] == "PASS"
              and checks["same_catalog_accepted"]
              and checks["cross_catalog_refused"]
              and checks["unknown_paper_refused"]
              and checks["unknown_catalog_refused"]
              and checks["existing_data_valid"] == "PASS"
              and checks["rows_mutated"] == 0
              and checks["baseline_intact"] == "PASS"
              and checks["replay_classified"] == "PASS"
              and checks["FK_OUTSIDE_A"] == 0
              and checks["B_CONTAMINATION"] == 0
              and checks["C_CONTAMINATION"] == 0)
    return {
        "checks": checks,
        "gates": gates,
        "082_ACCEPTANCE": "PASS" if passed else "BLOCKED",
    }


def final_report() -> Dict[str, str]:
    """The spec's COMMIT GATE block, verbatim keys."""
    gates = gate_results()
    block = acceptance()
    contamination = contamination_counts()
    verdict = "FROZEN" if block["082_ACCEPTANCE"] == "PASS" else "BLOCKED"
    baseline = "/".join(str(BASELINE_ANCHOR[k]) for k in
                        ("knowledge_unit", "ku_freeze_event", "ku_revision",
                         "ku_identity"))
    return {
        "TASK": "STRATUM_A_P5_5_082_PAPER_EVIDENCE_COMPOSITE_FK_REPAIR",
        "MIGRATION": REQUIRED_MIGRATION,
        "DB_MUTATION": "staging only",
        "ROWS_MUTATED": "0",
        "NEW_INDEX": "1",
        "NEW_FK": "1",
        "ALTER_SCOPE": "ADD_CONSTRAINT_ONLY",
        "BASELINE": baseline,
        "A_CONTAMINATION": "0" if contamination["FK_OUTSIDE_A"] == 0 else "1",
        "B_CONTAMINATION": str(contamination["B_REFERENCE"]),
        "C_CONTAMINATION": str(contamination["C_REFERENCE"]),
        "FINAL_STATUS": verdict,
        "COMMIT_SHA": os.environ.get("A_P5_5_COMMIT_SHA", "PENDING"),
        "TAG": os.environ.get("A_P5_5_TAG", "PENDING"),
    }


def main() -> None:
    doc = report()
    doc.update(acceptance())
    doc["final_report"] = final_report()
    doc["contamination"] = contamination_counts()
    ledger = os.environ.get("A_P5_5_LEDGER_FILE")
    if ledger and Path(ledger).exists():
        doc["ledger"] = [line.strip() for line in
                         Path(ledger).read_text(encoding="utf-8").splitlines()
                         if line.strip()]
    target = os.environ.get("A_P5_5_ARTIFACT_FILE")
    payload = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
    if target:
        Path(target).write_text(payload + "\n", encoding="utf-8")
        print(target)
        return
    print(payload)


if __name__ == "__main__":
    main()