"""Run PostgreSQL migrations for the Stratum service layer.

Usage:
    python -m stratum.db.run_pg_migrations [upgrade|downgrade] [target]

Migrations live in src/stratum/db/pg_migrations/*.sql and are applied in
filename order. Applied filenames are tracked in the _pg_migrations table.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "pg_migrations"


def _connect():
    import psycopg2

    dsn = os.environ.get("STRATUM_DATABASE_DSN")
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
        port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
        user=os.environ.get("STRATUM_PG_USER", "aii"),
        password=os.environ.get("STRATUM_PG_PASSWORD", ""),
        dbname=os.environ.get("STRATUM_PG_DB", "aii_kg"),
    )


def _apply_migration(con, cur, name: str, sql: str) -> None:
    """Apply one migration and record it atomically in the tracking table."""
    try:
        cur.execute(sql)
        cur.execute("INSERT INTO public._pg_migrations (filename) VALUES (%s)", (name,))
        con.commit()
    except Exception:
        con.rollback()
        raise


def upgrade(target: str = "head") -> None:
    con = _connect()
    con.autocommit = False
    cur = con.cursor()

    # Migrations historically mix qualified and unqualified table names.  The
    # service-layer runtime uses this same search path, so make the runner
    # explicit instead of silently creating half the schema in `public`.
    cur.execute("CREATE SCHEMA IF NOT EXISTS stratum")
    cur.execute("SET search_path TO stratum, public")

    # Bootstrap tracking table in public to preserve the old runner's record.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public._pg_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    con.commit()

    cur.execute("SELECT filename FROM public._pg_migrations")
    applied = {row[0] for row in cur.fetchall()}

    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("No migration files found in", _MIGRATIONS_DIR)
        return

    applied_count = 0
    for f in files:
        name = f.name
        if name in applied:
            continue
        if target != "head" and name > target:
            break
        print(f"  → Applying {name}")
        sql = f.read_text(encoding="utf-8")
        try:
            _apply_migration(con, cur, name, sql)
            applied_count += 1
        except Exception as e:
            print(f"  ✗ FAILED {name}: {e}")
            cur.close()
            con.close()
            sys.exit(1)

    cur.close()
    con.close()
    if applied_count:
        print(f"✅ Applied {applied_count} migration(s).")
    else:
        print("✅ Already up to date.")


def downgrade(target: str = "base") -> None:
    con = _connect()
    con.autocommit = False
    cur = con.cursor()

    cur.execute("SELECT filename FROM public._pg_migrations ORDER BY filename DESC")
    applied = [row[0] for row in cur.fetchall()]

    for name in applied:
        if target != "base" and name <= target:
            break
        # Down = DROP TABLE IF EXISTS for CREATE TABLE migrations; ALTER TABLE
        # columns are left in place (safe for prod).
        print(f"  ← Rolling back {name}")
        try:
            cur.execute("DELETE FROM public._pg_migrations WHERE filename = %s", (name,))
            con.commit()
        except Exception:
            con.rollback()
            cur.close()
            con.close()
            raise

    cur.close()
    con.close()
    print("✅ Downgrade complete.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    tgt = sys.argv[2] if len(sys.argv) > 2 else "head"
    if action == "upgrade":
        upgrade(tgt)
    elif action == "downgrade":
        downgrade(tgt)
    else:
        print(f"Unknown action: {action}. Use 'upgrade' or 'downgrade'.")
        sys.exit(1)
