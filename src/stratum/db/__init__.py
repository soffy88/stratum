"""Stratum DB helpers — thin wrappers for PostgreSQL operations.

The existing DuckDB store (dao/ layer) is unchanged.
These helpers target the new PostgreSQL store for service-layer tables
(highlights, subscriptions, changefeed, platform_content, etc.).

Requires: psycopg2-binary (or psycopg[binary])
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

_DSN = os.environ.get(
    "STRATUM_DATABASE_DSN",
    "postgresql://stratum:stratum@localhost:5433/stratum",
)


def _get_dsn() -> str:
    return os.environ.get("STRATUM_DATABASE_DSN", _DSN)


def _serialize(v: Any) -> Any:
    """Convert Python dicts to JSON strings for JSONB columns.
    Lists are left as-is so psycopg2 maps them to PG arrays."""
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _prep(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize(v) for k, v in data.items()}


@contextmanager
def _conn():
    import psycopg2
    import psycopg2.extras

    con = psycopg2.connect(_get_dsn())
    con.autocommit = False
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def insert(table: str, data: dict[str, Any], returning: str = "id") -> Any:
    """INSERT a row and return the value of `returning` column."""
    d = _prep(data)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(f"%({k})s" for k in d)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING {returning}"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, d)
            row = cur.fetchone()
            return row[0] if row else None


def read(table: str, rid: str, id_column: str = "id") -> dict[str, Any] | None:
    """SELECT a single row by id."""
    sql = f"SELECT * FROM {table} WHERE {id_column} = %s LIMIT 1"
    with _conn() as con:
        import psycopg2.extras

        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (rid,))
            row = cur.fetchone()
            return dict(row) if row else None


def query(
    sql: str, params: dict[str, Any] | tuple | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Execute a raw SELECT and return list of dicts."""
    with _conn() as con:
        import psycopg2.extras

        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in (cur.fetchmany(limit) if limit else cur.fetchall())]


def write(
    table: str,
    data: dict[str, Any],
    conflict_on: list[str] | None = None,
) -> Any:
    """INSERT … ON CONFLICT DO UPDATE (upsert)."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f"%({k})s" for k in data)
    if conflict_on:
        conflict_cols = ", ".join(conflict_on)
        updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in data if k not in conflict_on)
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
            f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {updates}"
            f" RETURNING id"
        )
    else:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, data)
            row = cur.fetchone()
            return row[0] if row else None


def update(table: str, rid: str, data: dict[str, Any], id_column: str = "id") -> None:
    """UPDATE a row by id."""
    d = _prep(data)
    sets = ", ".join(f"{k} = %({k})s" for k in d)
    sql = f"UPDATE {table} SET {sets} WHERE {id_column} = %(___id)s"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, {**d, "___id": rid})


def soft_delete(table: str, rid: str, deleted_at_column: str = "deleted_at") -> None:
    """SET deleted_at = NOW() for a row."""
    sql = f"UPDATE {table} SET {deleted_at_column} = NOW() WHERE id = %s"
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(sql, (rid,))
