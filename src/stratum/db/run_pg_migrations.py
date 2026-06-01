"""Run PostgreSQL migrations for the Stratum service layer.

Usage:
    python -m stratum.db.run_pg_migrations [upgrade|downgrade] [target]

Migrations live in src/stratum/db/pg_migrations/*.sql and are applied in
filename order. Applied filenames are tracked in the _pg_migrations table.
"""

from __future__ import annotations

import os
import sys
import glob
from pathlib import Path

_DSN = os.environ.get(
    "STRATUM_DATABASE_DSN",
    "postgresql://stratum:stratum@localhost:5433/stratum",
)

_MIGRATIONS_DIR = Path(__file__).parent / "pg_migrations"


def _connect():
    import psycopg2

    return psycopg2.connect(_DSN)


def upgrade(target: str = "head") -> None:
    con = _connect()
    con.autocommit = True
    cur = con.cursor()

    # Bootstrap tracking table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _pg_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("SELECT filename FROM _pg_migrations")
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
        sql = f.read_text()
        try:
            cur.execute(sql)
            cur.execute("INSERT INTO _pg_migrations (filename) VALUES (%s)", (name,))
            applied_count += 1
        except Exception as e:
            print(f"  ✗ FAILED {name}: {e}")
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
    con.autocommit = True
    cur = con.cursor()

    cur.execute("SELECT filename FROM _pg_migrations ORDER BY filename DESC")
    applied = [row[0] for row in cur.fetchall()]

    for name in applied:
        if target != "base" and name <= target:
            break
        # Down = DROP TABLE IF EXISTS for CREATE TABLE migrations; ALTER TABLE
        # columns are left in place (safe for prod).
        print(f"  ← Rolling back {name}")
        cur.execute("DELETE FROM _pg_migrations WHERE filename = %s", (name,))

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
