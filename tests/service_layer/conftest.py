"""DuckDB test fixture for service-layer route tests.

Creates a fresh DuckDB database (with the SL schema from migration 020) in a
temp directory and points STRATUM_DB_PATH at it for the duration of each test.
Tables are renamed to their final production names (mirrors §M6 Step 2) so that
the routes (which reference 'notes', 'agent_runs', etc.) find the right tables.
"""

import os

import duckdb
import pytest

_MIGRATION_020 = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../src/stratum/db/migrations/020_sl_tables.sql")
)


@pytest.fixture(autouse=True)
def duckdb_test_db(tmp_path, monkeypatch):
    """Fresh per-test DuckDB with SL schema + §M6 renames; STRATUM_DB_PATH redirected."""
    db_path = str(tmp_path / "test.duckdb")
    monkeypatch.setenv("STRATUM_DB_PATH", db_path)

    conn = duckdb.connect(db_path)
    with open(_MIGRATION_020) as f:
        conn.execute(f.read())

    # Mirror §M6 Step 2: drop _sl indexes (they block rename in DuckDB 1.5.2)
    # then rename tables to final production names so routes find correct tables.
    for idx in (
        "idx_arsl_user",
        "idx_arsl_status",
        "idx_notes_sl_user",
        "idx_notes_sl_alive",
        "idx_sjsl_enabled",
        "idx_sjrsl_job",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {idx}")
    conn.execute("ALTER TABLE notes_sl RENAME TO notes")
    conn.execute("ALTER TABLE agent_runs_sl RENAME TO agent_runs")
    conn.execute("ALTER TABLE scheduled_jobs_sl RENAME TO scheduled_jobs")
    conn.execute("ALTER TABLE scheduled_job_runs_sl RENAME TO scheduled_job_runs")
    conn.close()

    yield db_path
