"""PG service-layer integration test — real aii-postgres (stratum schema).

Unlike the rest of the suite (which runs against in-memory/temp DuckDB via the
conftest fixtures), this test connects to the live PostgreSQL store the
service-layer routes actually use after the DB convergence (P1.5): the `stratum`
schema in the aii-postgres container.

It exercises the real glue the routes sit on:
  - psycopg2 connection to aii-postgres with `search_path=stratum`
  - `stratum.db._ConnWrapper` DuckDB-`?` → psycopg2-`%s` placeholder translation
  - `SubstrateDAO` CRUD + user-isolation post-filter (the security-critical path
    behind /api/search and the substrates routes) against real PG

Isolation: everything runs inside a single transaction with autocommit OFF, and
the fixture ROLLS BACK in teardown — no row is ever committed, so the real data
is never touched. If aii-postgres is unreachable (e.g. CI without the container)
the test SKIPS rather than fails (sk:pif-no-testdb).
"""

from __future__ import annotations

import os

import psycopg2
import pytest

from stratum.db import _ConnWrapper
from stratum.dao.substrate import SubstrateDAO
from stratum.utils.user_id_hash import hash_user_id


def _pg_dsn() -> dict:
    return {
        "host": os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("STRATUM_PG_PORT", "5435")),
        "user": os.environ.get("STRATUM_PG_USER", "aii"),
        "password": os.environ.get("STRATUM_PG_PASSWORD", "aii_safe_pass"),
        "dbname": os.environ.get("STRATUM_PG_DB", "aii_kg"),
        "options": "-c search_path=stratum",
    }


@pytest.fixture
def pg_conn():
    """Dedicated non-autocommit PG connection, rolled back after the test.

    Uses its own connection (NOT the app's autocommit pool) so every write can be
    discarded via ROLLBACK — guaranteeing the live store is never polluted.
    """
    try:
        raw = psycopg2.connect(**_pg_dsn())
    except psycopg2.OperationalError as e:
        pytest.skip(f"aii-postgres not reachable — sk:pif-no-testdb ({e})")
    raw.autocommit = False
    try:
        yield _ConnWrapper(raw)
    finally:
        raw.rollback()
        raw.close()


def test_substrate_crud_and_isolation_on_pg(pg_conn):
    """End-to-end round-trip of SubstrateDAO against real PG, then rolled back."""
    owner = "pg-it-user-owner"
    other = "pg-it-user-other"
    sid = "pg-it-substrate-0001"

    # INSERT via the wrapper's `?` translation (same path routes/DAOs use).
    pg_conn.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?, ?, ?)",
        (sid, hash_user_id(owner), "PG integration probe"),
    )

    dao = SubstrateDAO(pg_conn)

    # get_substrate: owner sees it, hashing round-trips through real PG.
    got = dao.get_substrate(substrate_id=sid, user_id=owner)
    assert got is not None
    assert got.id == sid
    assert got.title == "PG integration probe"

    # list_substrates: the row appears for the owner.
    owned_ids = [s.id for s in dao.list_substrates(user_id=owner)]
    assert sid in owned_ids

    # Corpus isolation: a different user must NOT be able to read it.
    assert dao.get_substrate(substrate_id=sid, user_id=other) is None
    assert sid not in [s.id for s in dao.list_substrates(user_id=other)]
