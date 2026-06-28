"""Stratum DB helpers — PostgreSQL service-layer store (P1.2, AII merge DB convergence).

Was DuckDB (single-writer singleton+lock); now PostgreSQL via a pooled psycopg2
connection against the `stratum` schema in aii-postgres (shared with AII's `aii`).
The DuckDB version is kept at __init__.py.duckdb-backup for rollback.

Public API is unchanged so callers don't change:
  - insert/read/query/write/update/soft_delete/execute  (psycopg2-native %(name)s)
  - get_conn(): context manager yielding a connection wrapper whose .execute()
    translates DuckDB-style `?` placeholders → `%s`, so the raw callers
    (dao.graph, search_utils, sources, highlights, graph router, …) work unchanged.

Concurrency: a ThreadedConnectionPool replaces the old single-writer+lock — real
concurrent connections (one of the reasons for moving off DuckDB).
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

# Return JSON/JSONB columns as RAW STRINGS, matching DuckDB's behaviour, so the
# many callers that do `json.loads(col)` (DAOs, dao.graph, …) work unchanged.
# Without this psycopg2 auto-parses jsonb into dict/list → json.loads() would fail.
psycopg2.extras.register_default_jsonb(globally=True, loads=lambda x: x)
psycopg2.extras.register_default_json(globally=True, loads=lambda x: x)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _dsn_kwargs() -> dict[str, Any]:
    return {
        "host": os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("STRATUM_PG_PORT", "5435")),
        "user": os.environ.get("STRATUM_PG_USER", "aii"),
        "password": os.environ.get("STRATUM_PG_PASSWORD", ""),
        "dbname": os.environ.get("STRATUM_PG_DB", "aii_kg"),
        # Resolve unqualified table names to the stratum schema (aii.* stays explicit).
        "options": "-c search_path=stratum",
    }


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    int(os.environ.get("STRATUM_PG_POOL_MIN", "1")),
                    int(os.environ.get("STRATUM_PG_POOL_MAX", "10")),
                    **_dsn_kwargs(),
                )
    return _pool


class _ConnWrapper:
    """Mimics the DuckDB connection surface used by raw callers.

    `.execute(sql, params)` translates `?` → `%s` (DuckDB → psycopg2 positional),
    runs on a fresh cursor, and returns that cursor (so `.fetchone()/.fetchall()`
    chaining keeps working). Autocommit is on, matching DuckDB's per-statement
    semantics the callers were written against.
    """

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Any = None) -> Any:
        if params is not None and "?" in sql:
            sql = sql.replace("?", "%s")
        cur = self._raw.cursor()
        cur.execute(sql, params)
        return cur


@contextmanager
def _conn():
    """Yield a pooled PG connection (wrapped) in autocommit mode."""
    pool = _get_pool()
    raw = pool.getconn()
    try:
        raw.autocommit = True
        yield _ConnWrapper(raw)
    finally:
        pool.putconn(raw)


get_conn = _conn


def _serialize(v: Any) -> Any:
    """Dicts → jsonb (psycopg2 Json adapter); lists pass through as PG arrays."""
    if isinstance(v, dict):
        return psycopg2.extras.Json(v)
    return v


def _prep(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize(v) for k, v in data.items()}


def _rows(cursor: Any) -> list[dict[str, Any]]:
    """Materialise all rows from a psycopg2 cursor as list-of-dicts."""
    if cursor.description is None:
        return []
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@contextmanager
def _cursor(commit: bool = False):
    pool = _get_pool()
    raw = pool.getconn()
    try:
        raw.autocommit = True
        cur = raw.cursor()
        try:
            yield cur
        finally:
            cur.close()
    finally:
        pool.putconn(raw)


def insert(table: str, data: dict[str, Any], returning: str = "id") -> Any:
    """INSERT a row and return the value of `returning` column."""
    d = _prep(data)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(f"%({k})s" for k in d)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING {returning}"
    with _cursor() as cur:
        cur.execute(sql, d)
        row = cur.fetchone()
        return row[0] if row else None


def read(table: str, rid: str, id_column: str = "id") -> dict[str, Any] | None:
    """SELECT a single row by id."""
    sql = f"SELECT * FROM {table} WHERE {id_column} = %(rid)s LIMIT 1"
    with _cursor() as cur:
        cur.execute(sql, {"rid": rid})
        rows = _rows(cur)
        return rows[0] if rows else None


def query(
    sql: str,
    params: dict[str, Any] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Execute a SELECT and return a list of dicts. Appends LIMIT when absent.

    Router SQL is already psycopg2 `%(name)s` pyformat, so no conversion is needed.
    """
    if limit and "limit" not in sql.lower():
        sql = sql.rstrip(" ;") + f" LIMIT {limit}"
    with _cursor() as cur:
        cur.execute(sql, params)
        return _rows(cur)


def write(
    table: str,
    data: dict[str, Any],
    conflict_on: list[str] | None = None,
) -> Any:
    """INSERT … ON CONFLICT DO UPDATE (upsert), return id."""
    d = _prep(data)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(f"%({k})s" for k in d)
    if conflict_on:
        conflict_cols = ", ".join(conflict_on)
        updates = ", ".join(f"{k} = EXCLUDED.{k}" for k in d if k not in conflict_on)
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
            f" ON CONFLICT ({conflict_cols}) DO UPDATE SET {updates}"
            f" RETURNING id"
        )
    else:
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING id"
    with _cursor() as cur:
        cur.execute(sql, d)
        row = cur.fetchone()
        return row[0] if row else None


def update(table: str, rid: str, data: dict[str, Any], id_column: str = "id") -> None:
    """UPDATE a row by id."""
    d = _prep(data)
    sets = ", ".join(f"{k} = %({k})s" for k in d)
    sql = f"UPDATE {table} SET {sets} WHERE {id_column} = %(___id)s"
    with _cursor() as cur:
        cur.execute(sql, {**d, "___id": rid})


def soft_delete(table: str, rid: str, deleted_at_column: str = "deleted_at") -> None:
    """SET deleted_at = NOW() for a row."""
    sql = f"UPDATE {table} SET {deleted_at_column} = NOW() WHERE id = %(rid)s"
    with _cursor() as cur:
        cur.execute(sql, {"rid": rid})


def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    """Run a raw DML statement (UPDATE/DELETE) with no return value."""
    with _cursor() as cur:
        cur.execute(sql, params)
