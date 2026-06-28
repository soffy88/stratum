"""Stratum DB helpers — DuckDB service-layer store.

Replaces psycopg2 after §M3 DB merge.
R2 (SPEC v1.1): query() pushes LIMIT into SQL — no fetchmany clipping.
R3 (§20): singleton connection + lock — eliminates 'Conflicting lock' IOException
  that occurs when concurrent API handlers each open a new write connection.
  DuckDB is single-writer; one long-lived connection shared under a threading.Lock
  is the correct concurrency model for an in-process DuckDB deployment.
"""

from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from typing import Any

import duckdb

_PYFORMAT_RE = re.compile(r"%\((\w+)\)s")

# Singleton write connection and its lock.
# All DB access is serialized through this lock — DuckDB autocommit means
# each execute() is atomic, so lock granularity per _conn() call is correct.
_db_lock = threading.Lock()
_db_conn: duckdb.DuckDBPyConnection | None = None


def _get_db_path() -> str:
    return os.path.expanduser(os.environ.get("STRATUM_DB_PATH", "~/.stratum/meta.duckdb"))


def _get_singleton() -> duckdb.DuckDBPyConnection:
    global _db_conn
    if _db_conn is None:
        _db_conn = duckdb.connect(_get_db_path())
        # Compact WAL on startup — reclaims disk space accumulated from MVCC
        # versions that were never checkpointed during the previous run.
        try:
            _db_conn.execute("CHECKPOINT")
        except Exception:
            pass
    return _db_conn


@contextmanager
def _conn():
    """Yield the shared DuckDB connection under a threading lock.

    Exported so routes can run raw DML (e.g. bulk UPDATE) directly.
    DuckDB operates in autocommit mode; each execute() is its own transaction.
    The singleton connection is kept alive for the process lifetime — no close().
    """
    with _db_lock:
        yield _get_singleton()


get_conn = _conn


def _serialize(v: Any) -> Any:
    """Dicts → JSON strings for JSON columns; lists pass through for VARCHAR[]."""
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return v


def _prep(data: dict[str, Any]) -> dict[str, Any]:
    return {k: _serialize(v) for k, v in data.items()}


def _pyformat_to_duckdb(
    sql: str, params: dict[str, Any] | None
) -> tuple[str, dict[str, Any] | None]:
    """Convert psycopg2-style %(key)s → DuckDB $key named parameters."""
    if params is None:
        return sql, None
    converted = _PYFORMAT_RE.sub(lambda m: f"${m.group(1)}", sql)
    return converted, params


def _rows(cursor: Any) -> list[dict[str, Any]]:
    """Materialise all rows from a DuckDB cursor as list-of-dicts."""
    if cursor.description is None:
        return []
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def insert(table: str, data: dict[str, Any], returning: str = "id") -> Any:
    """INSERT a row and return the value of `returning` column."""
    d = _prep(data)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(f"${k}" for k in d)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING {returning}"
    with _conn() as conn:
        row = conn.execute(sql, d).fetchone()
        return row[0] if row else None


def read(table: str, rid: str, id_column: str = "id") -> dict[str, Any] | None:
    """SELECT a single row by id."""
    sql = f"SELECT * FROM {table} WHERE {id_column} = $rid LIMIT 1"
    with _conn() as conn:
        rows = _rows(conn.execute(sql, {"rid": rid}))
        return rows[0] if rows else None


def query(
    sql: str,
    params: dict[str, Any] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Execute a SELECT and return a list of dicts.

    R2: appends LIMIT {limit} to SQL when the SQL has no LIMIT clause, so the
    limit is applied server-side rather than via fetchmany clipping.
    """
    sql, params = _pyformat_to_duckdb(sql, params)
    if limit and "limit" not in sql.lower():
        sql = sql.rstrip(" ;") + f" LIMIT {limit}"
    with _conn() as conn:
        cursor = conn.execute(sql, params) if params else conn.execute(sql)
        return _rows(cursor)


def write(
    table: str,
    data: dict[str, Any],
    conflict_on: list[str] | None = None,
) -> Any:
    """INSERT … ON CONFLICT DO UPDATE (upsert), return id."""
    d = _prep(data)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(f"${k}" for k in d)
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
    with _conn() as conn:
        row = conn.execute(sql, d).fetchone()
        return row[0] if row else None


def update(table: str, rid: str, data: dict[str, Any], id_column: str = "id") -> None:
    """UPDATE a row by id."""
    d = _prep(data)
    sets = ", ".join(f"{k} = ${k}" for k in d)
    # ___id avoids collision with any data column named 'id'
    sql = f"UPDATE {table} SET {sets} WHERE {id_column} = $___id"
    with _conn() as conn:
        conn.execute(sql, {**d, "___id": rid})


def soft_delete(table: str, rid: str, deleted_at_column: str = "deleted_at") -> None:
    """SET deleted_at = NOW() for a row."""
    sql = f"UPDATE {table} SET {deleted_at_column} = NOW() WHERE id = $rid"
    with _conn() as conn:
        conn.execute(sql, {"rid": rid})


def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    """Run a raw DML statement (UPDATE/DELETE) with no return value."""
    sql, params = _pyformat_to_duckdb(sql, params)
    with _conn() as conn:
        conn.execute(sql, params) if params else conn.execute(sql)
