"""A Repository P5.5 — paper evidence composite FK repair.

Contract tests for migration 082. The repair adds a *rule* and records nothing,
so most of these assert against the live database rather than an in-memory model.

Note the split in what is checked where:
  * the DDL's shape      — read from the migration file
  * the constraint's work — read from PostgreSQL, because "does it refuse the
                           cross-catalog case" is a question only the database
                           can answer
  * the replay signal    — the second execution is opt-in, because a validation
                           step that migrates the database is a trap
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "082_a_paper_evidence_composite_fk.sql"
ARTIFACT = ROOT / "artifacts" / "a_repository" / "p5_5_082_paper_evidence_fk.json"

from stratum.knowledge.a_repository.paper_evidence_fk_runner import (  # noqa: E402
    ALLOWED_FK_TARGETS,
    BASELINE_ANCHOR,
    EXPECTED_CONSTRAINT,
    EXPECTED_INDEX,
    REQUIRED_MIGRATION,
    UNTOUCHABLE_TABLES,
    acceptance,
    authority_gate,
    baseline_gate,
    constraint_present_gate,
    contamination_counts,
    duplicate_objects,
    existing_data_gate,
    final_report,
    gate_results,
    index_present_gate,
    index_target_gate,
    negative_db_gate,
    no_new_lifecycle_gate,
    replay_gate,
    report,
    row_mutation_gate,
    schema_gate,
    schema_reports_only_two_objects,
    _clean,
    _statements,
)


# ── 1. composite FK exists ───────────────────────────────────────────────────

def test_composite_fk_exists():
    """STEP 2 is present, is a foreign key, and uses RESTRICT."""
    assert schema_gate() == "PASS"
    assert constraint_present_gate() == "PASS"
    clean = _clean()
    assert "ALTER TABLE stratum.paper_evidence" in clean
    assert f"ADD CONSTRAINT {EXPECTED_CONSTRAINT}" in clean
    assert "FOREIGN KEY (paper_id, catalog_source_id)" in clean
    assert "REFERENCES stratum.paper_source_candidate (id, book_source_id)" \
        in clean
    assert "ON DELETE RESTRICT" in clean


def test_the_fk_target_index_exists():
    """STEP 1 is present, and covers exactly (id, book_source_id)."""
    assert index_present_gate() == "PASS"
    assert index_target_gate() == "PASS"
    clean = _clean()
    assert f"CREATE UNIQUE INDEX IF NOT EXISTS {EXPECTED_INDEX}" in clean
    assert "ON stratum.paper_source_candidate (id, book_source_id)" in clean


def test_the_index_precedes_the_constraint():
    """A foreign key needs its unique target first.

    Measured on 079 and 080: with the index declared after the table,
    PostgreSQL refuses with "no unique constraint matching given keys". The DDL
    is transactional so it rolls back cleanly, but the ordering is load-bearing
    and is asserted rather than assumed.
    """
    clean = _clean()
    assert clean.index("CREATE UNIQUE INDEX") < clean.index("ADD CONSTRAINT")


# ── 2. same catalog accepted ─────────────────────────────────────────────────

def test_same_catalog_accepted():
    """The honest case must still be accepted, or the constraint is wrong.

    A rule that refuses everything is not a repair; it is a denial of service on
    the writer. This runs in a transaction and rolls back.
    """
    checks = negative_db_gate()
    assert checks["same_catalog_accepted"] is True


# ── 3. cross catalog rejected ────────────────────────────────────────────────

def test_cross_catalog_rejected():
    """The hole 080 left open, now closed by the database.

    Measured before 082: a real paper plus a real catalog row that the paper's
    candidate does not own was ACCEPTED. Both references were individually
    valid; together they described a declaration no source made.
    """
    checks = negative_db_gate()
    assert checks["cross_catalog_refused"] is True


def test_unknown_paper_rejected():
    checks = negative_db_gate()
    assert checks["unknown_paper_refused"] is True


def test_unknown_catalog_rejected():
    checks = negative_db_gate()
    assert checks["unknown_catalog_refused"] is True


def test_negative_detail_names_every_case():
    checks = negative_db_gate()
    for name in ("cross_catalog_refused", "unknown_paper_refused",
                 "unknown_catalog_refused", "same_catalog_accepted"):
        assert name in checks


# ── 4. unknown catalog rejected (covered above) and existing data intact ─────

def test_existing_data_satisfies_the_new_fk():
    """Every stored declaration satisfies the tie.

    The DDL already guarantees this: ADD CONSTRAINT for a foreign key validates
    existing rows unless declared NOT VALID, so a stored cross-catalog
    declaration would have aborted the migration outright. This is the readable
    version of that fact.
    """
    assert existing_data_gate() == "PASS"
    assert row_mutation_gate() == "PASS"


def test_baseline_anchor_is_row_counts():
    """11/12/1/11 — and rows, not indexes.

    knowledge_unit has 10 indexes and 11 rows. The distinction has already been
    recorded once, when a freeze record reported the index count as the row
    count, so the anchor is asserted explicitly here.
    """
    assert baseline_gate() == "PASS"
    assert BASELINE_ANCHOR["knowledge_unit"] == 11
    anchor = "/".join(str(BASELINE_ANCHOR[key]) for key in
                      ("knowledge_unit", "ku_freeze_event", "ku_revision",
                       "ku_identity"))
    assert anchor == "11/12/1/11"


# ── 5. delete restricted ─────────────────────────────────────────────────────

def test_delete_restricted():
    """A candidate may not take its declarations with it."""
    clean = _clean()
    assert "ON DELETE RESTRICT" in clean
    assert "CASCADE" not in clean
    assert "SET NULL" not in clean
    assert "SET DEFAULT" not in clean
    assert authority_gate() == "PASS"


# ── 6. migration replay stable ───────────────────────────────────────────────

def test_migration_replay_stable():
    """A second execution creates no duplicate object.

    Read-only by default. The opt-in second execution asserts the expected
    "already exists" signal, because PostgreSQL has no IF NOT EXISTS for ADD
    CONSTRAINT and the DO-block workaround would be a function, which A仓 does
    not introduce.
    """
    replay = replay_gate()
    assert replay["duplicate_objects"] == 0
    assert replay["index_present"] == 1
    assert replay["constraint_present"] == 1
    assert duplicate_objects() == []
    assert gate_results()["GATE_4_replay"] == "PASS"


def test_replay_does_not_execute_ddl_by_default():
    """Inspecting the gates must not migrate the database.

    An earlier version of the runner executed the migration from inside
    replay_gate(), so simply looking at the gates applied 082 while the ledger
    still said 081. That is a validation step mutating what it validates.
    """
    import os
    assert os.environ.get("A_P5_5_EXECUTE_REPLAY") is None or \
        os.environ.get("A_P5_5_EXECUTE_REPLAY") == "1"
    replay = replay_gate()
    if os.environ.get("A_P5_5_EXECUTE_REPLAY") != "1":
        assert replay["executed"] == 0


# ── 7. authority scan ────────────────────────────────────────────────────────

def test_authority_scan():
    """The new foreign key points at an A table, and only one."""
    assert authority_gate() == "PASS"
    counts = contamination_counts()
    assert counts["FK_OUTSIDE_A"] == 0
    assert counts["B_REFERENCE"] == 0
    assert counts["C_REFERENCE"] == 0
    assert counts["BU2_DEPENDENCY"] == 0
    clean = _clean().lower()
    for foreign in ("bu_onto", "chapter_bu", "aii_refined", "refined_ku",
                    "learning_objective"):
        assert f"references stratum.{foreign}" not in clean


def test_only_paper_source_candidate_is_referenced():
    assert ALLOWED_FK_TARGETS == frozenset({"paper_source_candidate"})
    referenced = set(re.findall(r"REFERENCES\s+stratum\.(\w+)", _clean()))
    assert referenced == {"paper_source_candidate"}


def test_the_source_file_carries_no_forbidden_authority_name():
    """A source file in this package is word-scanned for B仓 table names.

    tests/integration/test_a_authority_freeze.py reads every .py under
    src/stratum/knowledge/a_repository and asserts the forbidden table name does
    not appear — docstrings and comments included. Naming it, even in a guard
    list, is the violation that test exists to catch; that is exactly how the
    P5.4 runner broke once.
    """
    # Re-implemented rather than imported from the upstream test: importing
    # across test packages is brittle, and four lines are cheaper than a
    # dependency. The rule being enforced is the one that has already broken
    # twice — a guard list or a docstring that spells the name is the violation.
    forbidden = "knowledge" + "_claims"
    package = ROOT / "src" / "stratum" / "knowledge" / "a_repository"
    for path in package.glob("*.py"):
        assert forbidden not in path.read_text(encoding="utf-8"), \
            f"{path.name} references the B仓 table, in code or in prose"


# ── migration discipline ─────────────────────────────────────────────────────

def test_only_two_statements():
    """One index, one ADD CONSTRAINT, nothing else."""
    statements = _statements()
    assert len(statements) == 2
    assert schema_reports_only_two_objects() == "PASS"
    index, alter = statements
    assert index.upper().startswith("CREATE UNIQUE INDEX")
    assert alter.upper().startswith("ALTER TABLE")
    assert alter.upper().count("ADD CONSTRAINT") == 1


def test_no_destructive_statement():
    """DROP, RENAME, UPDATE, DELETE, INSERT and TRUNCATE are absent.

    Checked as statement-initial tokens, not substrings: a substring test for
    "DELETE " matches the ON DELETE RESTRICT the spec requires, so the naive
    version of this check forbids the exact clause 082 must write.
    """
    import re as _re
    for statement in _statements():
        normalised = " ".join(statement.upper().split())
        for verb in ("DROP", "RENAME", "UPDATE", "DELETE", "INSERT", "TRUNCATE"):
            assert not normalised.startswith(verb), \
                f"{verb} appears as a statement in 082"
        for forbidden in ("ALTER COLUMN", "NOT VALID"):
            assert forbidden not in normalised
    clean = _clean()
    assert "NOT VALID" not in clean, \
        "NOT VALID would skip validating existing rows, which is GATE_2"


def test_no_table_is_created_or_altered_beyond_paper_evidence():
    for table in UNTOUCHABLE_TABLES:
        assert f"CREATE TABLE stratum.{table}" not in _clean()
        assert f"ALTER TABLE stratum.{table}" not in _clean()


def test_082_touches_no_frozen_migration():
    """080 and 081 are byte-identical to what was frozen."""
    frozen = {
        "080_a_paper_source.sql":
            "6215e46078709bc8fc8548ccaa7de218024ba7e44dc917f16ed69f4d6312bfd5",
        "081_a_constraint_candidate.sql":
            "0e9ebc2ddc443412fe9c0203ab3a7150fd7b02d0034c9368e126483283069f4e",
    }
    import hashlib
    for name, expected in frozen.items():
        digest = hashlib.sha256(
            (MIGRATIONS / name).read_bytes()).hexdigest()
        assert digest == expected, f"{name} changed"


def test_no_new_lifecycle():
    """No freeze_event, no verification_event, no revision, no status.

    082 is a schema integrity repair, not a new knowledge artifact.
    """
    assert no_new_lifecycle_gate() == "PASS"
    clean = _clean().upper()
    for forbidden in ("FREEZE_EVENT", "VERIFICATION_EVENT", "KU_REVISION",
                      "INSERT INTO"):
        assert forbidden not in clean


def test_earlier_migrations_are_untouched():
    """Nothing from 070 to 081 mentions this repair."""
    for path in sorted(MIGRATIONS.glob("0[78]*_a_*.sql")):
        if path.name == MIGRATION.name:
            continue
        assert EXPECTED_CONSTRAINT not in path.read_text(encoding="utf-8")
        assert EXPECTED_INDEX not in path.read_text(encoding="utf-8")


# ── gates and artifact ───────────────────────────────────────────────────────

def test_all_gates_pass():
    gates = gate_results()
    for name, value in gates.items():
        if isinstance(value, dict):
            continue
        assert value == "PASS", f"{name}={value}"


def test_acceptance_block():
    block = acceptance()
    checks = block["checks"]
    assert block["082_ACCEPTANCE"] == "PASS"
    assert checks["composite_fk_exists"] == "PASS"
    assert checks["fk_target_present"] == "PASS"
    assert checks["same_catalog_accepted"] is True
    assert checks["cross_catalog_refused"] is True
    assert checks["unknown_paper_refused"] is True
    assert checks["unknown_catalog_refused"] is True
    assert checks["existing_data_valid"] == "PASS"
    assert checks["rows_mutated"] == 0
    assert checks["baseline_intact"] == "PASS"
    assert checks["replay_classified"] == "PASS"
    assert checks["FK_OUTSIDE_A"] == 0
    assert checks["B_CONTAMINATION"] == 0
    assert checks["C_CONTAMINATION"] == 0
    assert checks["BU2_DEPENDENCY"] == 0


def test_final_report_block():
    """The spec's COMMIT GATE keys, present and honest."""
    block = final_report()
    for key in ("TASK", "MIGRATION", "DB_MUTATION", "ROWS_MUTATED", "NEW_INDEX",
                "NEW_FK", "ALTER_SCOPE", "BASELINE", "A_CONTAMINATION",
                "B_CONTAMINATION", "C_CONTAMINATION", "FINAL_STATUS",
                "COMMIT_SHA", "TAG"):
        assert key in block, key
    assert block["TASK"] == ("STRATUM_A_P5_5_082_"
                             "PAPER_EVIDENCE_COMPOSITE_FK_REPAIR")
    assert block["MIGRATION"] == REQUIRED_MIGRATION
    assert block["DB_MUTATION"] == "staging only"
    assert block["ROWS_MUTATED"] == "0"
    assert block["NEW_INDEX"] == "1"
    assert block["NEW_FK"] == "1"
    assert block["ALTER_SCOPE"] == "ADD_CONSTRAINT_ONLY"
    assert block["BASELINE"] == "11/12/1/11"
    assert block["FINAL_STATUS"] == "FROZEN"
    # No commit has been made, so these are PENDING rather than guessed.
    assert block["COMMIT_SHA"] == "PENDING"
    assert block["TAG"] == "PENDING"


def test_report_records_the_closed_limitation():
    doc = report()
    assert doc["closes_limitation"].startswith("P5.3")
    assert doc["status_limitation"] == "database enforced"
    assert doc["new_index"] == EXPECTED_INDEX
    assert doc["new_foreign_key"] == EXPECTED_CONSTRAINT
    assert doc["baseline_anchor"] == dict(BASELINE_ANCHOR)
    assert doc["baseline_note"] == "row counts, not index counts"


def test_committed_artifact_matches_a_fresh_run():
    assert ARTIFACT.exists(), "run paper_evidence_fk_runner to emit it"
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fresh = report()
    for key in ("task", "authority", "repair_version", "migration",
                "new_index", "new_foreign_key", "fk_target", "delete_verb",
                "baseline_anchor", "closes_limitation", "status_limitation"):
        assert committed[key] == fresh[key], key