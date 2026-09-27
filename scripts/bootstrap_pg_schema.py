#!/usr/bin/env python3
"""Bootstrap the shared Stratum PostgreSQL schema, then apply migrations.

The base schema is a generated snapshot while ``pg_migrations`` contains
incremental changes.  Keeping the two explicit prevents a fresh deployment
from running only incremental tables and failing later when a router expects a
base table.
"""

from __future__ import annotations

from pathlib import Path

from stratum.db.run_pg_migrations import _connect, upgrade


def main() -> None:
    schema_path = Path(__file__).parents[1] / "src/stratum/db/pg_schema/001_stratum_base.sql"
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(schema_path.read_text(encoding="utf-8"))
    finally:
        conn.close()
    upgrade()


if __name__ == "__main__":
    main()
