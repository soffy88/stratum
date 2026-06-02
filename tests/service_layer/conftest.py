"""DuckDB test fixture for service-layer route tests.

Creates a fresh DuckDB database (with the SL schema from migration 020) in a
temp directory and points STRATUM_DB_PATH at it for the duration of each test.
This replaces the old mock-based approach so the routes run against real SQL.
"""

import os

import duckdb
import pytest

_MIGRATION_020 = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../src/stratum/db/migrations/020_sl_tables.sql")
)


@pytest.fixture(autouse=True)
def duckdb_test_db(tmp_path, monkeypatch):
    """Fresh per-test DuckDB with all SL tables; STRATUM_DB_PATH redirected."""
    db_path = str(tmp_path / "test.duckdb")
    monkeypatch.setenv("STRATUM_DB_PATH", db_path)

    conn = duckdb.connect(db_path)
    with open(_MIGRATION_020) as f:
        conn.execute(f.read())
    conn.close()

    yield db_path
