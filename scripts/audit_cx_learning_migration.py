#!/usr/bin/env python3
"""Audit or explicitly roll back the C-repository learning multi-user migration.

Default mode is read-only.  It reports whether ``cx.learning_*`` has the
multi-user columns and how much legacy data is still unmapped; it never guesses
an owner and never writes data.  ``--rollback`` only prints the destructive SQL
unless both ``--apply`` and ``--confirm-rollback`` are supplied.

Connection priority:
  ``AII_CONTEXT_DATABASE_DSN`` / ``STRATUM_CONTEXT_DATABASE_DSN`` /
  ``CONTEXT_DATABASE_URL`` (the latter is the existing AII convention).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass


TABLES = (
    "learning_profile",
    "learning_plan",
    "learning_progress",
    "learning_stuck",
)
REQUIRED_TABLES = (*TABLES, "learning_user_map")
REQUIRED_COLUMNS = {(table, "user_id") for table in TABLES}


@dataclass(frozen=True)
class AuditReport:
    schema_present: bool
    missing_columns: tuple[tuple[str, str], ...]
    missing_tables: tuple[str, ...] = ()
    profile_rows: int = 0
    mapped_profiles: int = 0
    unmapped_profiles: int = 0
    child_rows: int = 0
    mapped_child_rows: int = 0
    unmapped_child_rows: int = 0
    owner_mismatches: int = 0
    orphan_child_rows: int = 0
    attempts_arrays: int = 0

    @property
    def ready_for_mapping(self) -> bool:
        return self.schema_present and not self.missing_tables and not self.missing_columns


ROLLBACK_SQL = """\
-- Review/export cx.learning_user_map and user_id values before running this.
DROP TRIGGER IF EXISTS learning_plan_owner ON cx.learning_plan;
DROP TRIGGER IF EXISTS learning_progress_owner ON cx.learning_progress;
DROP TRIGGER IF EXISTS learning_stuck_owner ON cx.learning_stuck;
DROP FUNCTION IF EXISTS cx.inherit_learning_owner();
DROP INDEX IF EXISTS cx.idx_learning_profile_user;
DROP INDEX IF EXISTS cx.idx_learning_plan_user;
DROP INDEX IF EXISTS cx.idx_learning_progress_user;
DROP INDEX IF EXISTS cx.idx_learning_stuck_user;
DROP INDEX IF EXISTS cx.idx_learning_user_map_user;
DROP TABLE IF EXISTS cx.learning_user_map;
ALTER TABLE cx.learning_profile DROP COLUMN IF EXISTS user_id;
ALTER TABLE cx.learning_plan DROP COLUMN IF EXISTS user_id;
ALTER TABLE cx.learning_progress DROP COLUMN IF EXISTS user_id;
ALTER TABLE cx.learning_stuck DROP COLUMN IF EXISTS user_id;
"""


def _dsn() -> str:
    for name in (
        "AII_CONTEXT_DATABASE_DSN",
        "STRATUM_CONTEXT_DATABASE_DSN",
        "CONTEXT_DATABASE_URL",
    ):
        value = os.getenv(name)
        if value:
            return value
    return "postgresql://aii:aii_safe_pass@localhost:5436/aii_context"


def _connect(dsn: str):
    import psycopg2

    return psycopg2.connect(dsn)


def audit(conn) -> AuditReport:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'cx')"
        )
        schema_present = bool(cur.fetchone()[0])
        if not schema_present:
            return AuditReport(False, tuple(sorted(REQUIRED_COLUMNS)))

        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'cx' AND table_name = ANY(%s)",
            (list(REQUIRED_TABLES),),
        )
        existing_tables = {row[0] for row in cur.fetchall()}
        missing_tables = tuple(sorted(set(REQUIRED_TABLES) - existing_tables))
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'cx' AND table_name = ANY(%s)",
            (list(TABLES),),
        )
        existing = {(row[0], row[1]) for row in cur.fetchall()}
        missing = tuple(sorted(REQUIRED_COLUMNS - existing))
        if missing or ("learning_profile", "profile_id") not in existing or missing_tables:
            return AuditReport(True, missing, missing_tables)

        cur.execute("SELECT COUNT(*), COUNT(user_id) FROM cx.learning_profile")
        profile_rows, mapped_profiles = cur.fetchone()
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM cx.learning_plan)
              + (SELECT COUNT(*) FROM cx.learning_progress)
              + (SELECT COUNT(*) FROM cx.learning_stuck),
              (SELECT COUNT(*) FROM cx.learning_plan WHERE user_id IS NOT NULL)
              + (SELECT COUNT(*) FROM cx.learning_progress WHERE user_id IS NOT NULL)
              + (SELECT COUNT(*) FROM cx.learning_stuck WHERE user_id IS NOT NULL)
            """
        )
        child_rows, mapped_child_rows = cur.fetchone()
        cur.execute(
            """
            SELECT COUNT(*)
              FROM (
                SELECT lp.profile_id, lp.user_id, p.user_id AS profile_user_id
                  FROM cx.learning_plan lp
                  LEFT JOIN cx.learning_profile p ON p.profile_id = lp.profile_id
                UNION ALL
                SELECT lp.profile_id, lp.user_id, p.user_id
                  FROM cx.learning_progress lp
                  LEFT JOIN cx.learning_profile p ON p.profile_id = lp.profile_id
                UNION ALL
                SELECT ls.profile_id, ls.user_id, p.user_id
                  FROM cx.learning_stuck ls
                  LEFT JOIN cx.learning_profile p ON p.profile_id = ls.profile_id
              ) rows
             WHERE rows.user_id IS NOT NULL
               AND rows.profile_user_id IS NOT NULL
               AND rows.user_id <> rows.profile_user_id
            """
        )
        owner_mismatches = cur.fetchone()[0]
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM cx.learning_plan WHERE user_id IS NULL)
              + (SELECT COUNT(*) FROM cx.learning_progress WHERE user_id IS NULL)
              + (SELECT COUNT(*) FROM cx.learning_stuck WHERE user_id IS NULL)
            """
        )
        unmapped_child_rows = cur.fetchone()[0]
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM cx.learning_plan lp
                LEFT JOIN cx.learning_profile p ON p.profile_id = lp.profile_id
                WHERE p.profile_id IS NULL)
              + (SELECT COUNT(*) FROM cx.learning_progress lp
                LEFT JOIN cx.learning_profile p ON p.profile_id = lp.profile_id
                WHERE p.profile_id IS NULL)
              + (SELECT COUNT(*) FROM cx.learning_stuck ls
                LEFT JOIN cx.learning_profile p ON p.profile_id = ls.profile_id
                WHERE p.profile_id IS NULL)
            """
        )
        orphan_child_rows = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM cx.learning_progress
             WHERE attempts IS NOT NULL AND jsonb_typeof(attempts) = 'array'
            """
        )
        attempts_arrays = cur.fetchone()[0]
    return AuditReport(
        schema_present=True,
        missing_columns=missing,
        missing_tables=missing_tables,
        profile_rows=profile_rows,
        mapped_profiles=mapped_profiles,
        unmapped_profiles=profile_rows - mapped_profiles,
        child_rows=child_rows,
        mapped_child_rows=mapped_child_rows,
        unmapped_child_rows=unmapped_child_rows,
        owner_mismatches=owner_mismatches,
        orphan_child_rows=orphan_child_rows,
        attempts_arrays=attempts_arrays,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=None, help="Context PostgreSQL DSN (prefer env in CI)")
    parser.add_argument("--rollback", action="store_true", help="Show the rollback SQL")
    parser.add_argument(
        "--apply", action="store_true", help="Apply rollback; requires explicit confirmation"
    )
    parser.add_argument(
        "--confirm-rollback",
        action="store_true",
        help="Required with --rollback --apply; this drops user_id columns and mapping data",
    )
    args = parser.parse_args()

    if args.rollback:
        print(ROLLBACK_SQL)
        if not args.apply:
            print("rollback dry-run: no database write performed")
            return 0
        if not args.confirm_rollback:
            parser.error("--rollback --apply requires --confirm-rollback")
        conn = _connect(args.dsn or _dsn())
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(ROLLBACK_SQL)
        finally:
            conn.close()
        print("rollback applied")
        return 0

    conn = _connect(args.dsn or _dsn())
    try:
        report = audit(conn)
    finally:
        conn.close()
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2, sort_keys=True))
    if not report.ready_for_mapping:
        return 2
    if report.owner_mismatches or report.orphan_child_rows:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
