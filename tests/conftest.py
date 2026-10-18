"""Shared test fixtures for Stratum tests."""

import os
from pathlib import Path

# Inject test-only secrets before any module that reads them at import time.
# setdefault leaves real env vars (e.g. from CI) untouched.
os.environ.setdefault("JWT_SECRET", "test-only-insecure-key-do-not-use-in-prod-padding")
os.environ.setdefault("COOKIE_SECRET", "test-only-cookie-secret-do-not-use-in-prod-pad")
os.environ.setdefault("ADMIN_SECRET", "test-admin-secret-do-not-use-in-prod-padding00")
# Test Postgres credentials come from the environment (CI secrets), falling back
# to the dev box's untracked key file. Never hard-code a password here.
# stratum.db defaults to 127.0.0.1:5435 user=aii dbname=aii_kg (the disposable
# bu2q-test-pg container), never the production aii-postgres on 5437.
_TEST_PG_ENV_FILE = Path(
    os.environ.get("STRATUM_TEST_PG_ENV_FILE", str(Path.home() / ".config/keys/aii-test-pg.env"))
)
if "STRATUM_PG_PASSWORD" not in os.environ and _TEST_PG_ENV_FILE.is_file():
    for _line in _TEST_PG_ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

import pytest
import duckdb


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY, email VARCHAR UNIQUE NOT NULL, username VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL, corpus_id VARCHAR UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE, is_active BOOLEAN DEFAULT TRUE,
    is_suspended BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_login_at TIMESTAMP, meta_json VARCHAR DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL, refresh_token_hash VARCHAR UNIQUE NOT NULL,
    user_agent VARCHAR, ip_address VARCHAR, expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS substrate (
    id VARCHAR PRIMARY KEY, ulid VARCHAR, corpus_id VARCHAR NOT NULL, title VARCHAR,
    mime VARCHAR, source_path VARCHAR, file_hash VARCHAR, byte_size INTEGER,
    page_count INTEGER, parser VARCHAR, language VARCHAR, has_cjk BOOLEAN,
    is_scanned BOOLEAN, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, meta_json VARCHAR DEFAULT '{}',
    is_pinned BOOLEAN DEFAULT FALSE, pinned_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS substrates (
    id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL, title VARCHAR,
    mime VARCHAR, source_path VARCHAR, file_hash VARCHAR, byte_size BIGINT,
    page_count INTEGER, parser VARCHAR, language VARCHAR, has_cjk BOOLEAN,
    is_scanned BOOLEAN, is_pinned BOOLEAN DEFAULT FALSE, pinned_at TIMESTAMP,
    pin_priority INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, meta_json JSON DEFAULT '{}',
    source VARCHAR, published_at TIMESTAMP, parse_quality VARCHAR
);
CREATE TABLE IF NOT EXISTS user_saved_views (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR NOT NULL,
    name         VARCHAR NOT NULL,
    description  VARCHAR,
    is_preset    BOOLEAN DEFAULT FALSE,
    icon         VARCHAR,
    filter_json  JSON DEFAULT '{}',
    sort_by      VARCHAR DEFAULT 'created_at',
    sort_order   VARCHAR DEFAULT 'desc',
    display_mode VARCHAR DEFAULT 'list',
    position     INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS highlights (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    substrate_id VARCHAR NOT NULL,
    color VARCHAR DEFAULT 'yellow',
    text VARCHAR NOT NULL,
    note VARCHAR,
    location_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS note (
    id VARCHAR PRIMARY KEY, corpus_id VARCHAR NOT NULL, title VARCHAR, content VARCHAR,
    wikilinks VARCHAR, substrate_id VARCHAR, meta_json VARCHAR DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS concept (
    id VARCHAR PRIMARY KEY, name VARCHAR, aliases VARCHAR, description VARCHAR,
    wikilink VARCHAR, source_ids VARCHAR, meta_json VARCHAR DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    corpus_id VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS derivative (
    id VARCHAR PRIMARY KEY, substrate_id VARCHAR, kind VARCHAR, seq INTEGER,
    content VARCHAR, embedding_id VARCHAR, embedding_dim INTEGER,
    meta_json VARCHAR DEFAULT '{}', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    corpus_id VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS views (
    id VARCHAR PRIMARY KEY, user_id VARCHAR, corpus_id VARCHAR NOT NULL, name VARCHAR,
    description VARCHAR, default_filter VARCHAR, default_llm VARCHAR,
    default_system_prompt VARCHAR, icon VARCHAR, is_default BOOLEAN DEFAULT FALSE,
    is_builtin BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR PRIMARY KEY, user_id VARCHAR, corpus_id VARCHAR NOT NULL, text VARCHAR,
    completed BOOLEAN DEFAULT FALSE, due_date DATE, scheduled_date DATE,
    tags VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS templates (
    id VARCHAR PRIMARY KEY, user_id VARCHAR, corpus_id VARCHAR NOT NULL, name VARCHAR,
    content VARCHAR, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS share_tokens (
    token VARCHAR PRIMARY KEY, resource_type VARCHAR NOT NULL, resource_id VARCHAR NOT NULL,
    corpus_id VARCHAR NOT NULL, created_by VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP,
    revoked_at TIMESTAMP, access_count INTEGER DEFAULT 0, last_accessed_at TIMESTAMP,
    allow_anonymous BOOLEAN DEFAULT TRUE, meta_json VARCHAR DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id VARCHAR PRIMARY KEY, display_name VARCHAR, avatar_url VARCHAR,
    bio VARCHAR, location VARCHAR, website VARCHAR,
    timezone VARCHAR DEFAULT 'Asia/Shanghai', locale VARCHAR DEFAULT 'zh-CN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id VARCHAR PRIMARY KEY, user_id VARCHAR, corpus_id VARCHAR NOT NULL,
    name VARCHAR, agent_name VARCHAR, agent_params VARCHAR,
    cron_expression VARCHAR, timezone VARCHAR DEFAULT 'Asia/Shanghai',
    enabled BOOLEAN DEFAULT TRUE, notify_on_completion BOOLEAN DEFAULT FALSE,
    notify_on_failure BOOLEAN DEFAULT FALSE, max_runtime_seconds INTEGER DEFAULT 300,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id VARCHAR PRIMARY KEY, user_id VARCHAR, corpus_id VARCHAR NOT NULL,
    agent_name VARCHAR, params VARCHAR, status VARCHAR DEFAULT 'pending',
    trace VARCHAR, citations VARCHAR, output VARCHAR,
    total_input_tokens INTEGER DEFAULT 0, total_output_tokens INTEGER DEFAULT 0,
    cost_usd DOUBLE DEFAULT 0.0, started_at TIMESTAMP, completed_at TIMESTAMP,
    error_message VARCHAR
);
CREATE TABLE IF NOT EXISTS feedback (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    content VARCHAR NOT NULL,
    page_url VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS book_reading_run (
    id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL, source_id VARCHAR NOT NULL,
    source_version VARCHAR, status VARCHAR NOT NULL, current_pass INTEGER DEFAULT 1,
    parser_version VARCHAR, reader_version VARCHAR, extractor_version VARCHAR,
    verifier_version VARCHAR, coverage_json JSON DEFAULT '{}', open_gaps_json JSON DEFAULT '[]',
    started_at TIMESTAMP, completed_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reading_ledger (
    id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL, item_type VARCHAR NOT NULL,
    item_identifier VARCHAR NOT NULL, status VARCHAR NOT NULL, locator_json JSON DEFAULT '{}',
    page_number INTEGER, expected BOOLEAN DEFAULT TRUE, trace_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, item_type, item_identifier)
);
"""


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate limiter windows are process-global; clear them between tests.

    The middleware keeps sliding-window counters in module-level dicts, so a
    full-suite run would otherwise accumulate requests across tests and trip
    the per-user/per-IP limits (429).
    """
    from stratum.middleware.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield


@pytest.fixture
def db():
    """In-memory DuckDB with full schema for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def canonical_source_writer(db):
    """Use the production ownership-enforced Source writer in test fixtures."""
    from stratum.services.canonical_source_writer import CanonicalSourceWriter

    return CanonicalSourceWriter(db)


_PROD_PG_PORT = "5437"


def _targets_production_pg() -> bool:
    dsn = os.environ.get("STRATUM_DATABASE_DSN", "")
    return (
        os.environ.get("STRATUM_PG_PORT", "5435") == _PROD_PG_PORT
        or f":{_PROD_PG_PORT}/" in dsn
        or f"port={_PROD_PG_PORT}" in dsn
    )


@pytest.fixture(scope="session", autouse=True)
def _pg_test_schema_up_to_date():
    """Bring the test Postgres schema to head before any test runs.

    Refuses to touch the production database (port 5437). If no test PG is
    reachable (e.g. CI without Postgres) the PG-backed tests fail on their own;
    the DuckDB-only suite still runs.
    """
    if _targets_production_pg():
        pytest.exit("tests must not run migrations against production PG (5437)", returncode=2)
    try:
        import psycopg2
        from stratum.db import run_pg_migrations

        run_pg_migrations.upgrade()
    except SystemExit as exc:  # upgrade() exits non-zero when a migration fails
        if exc.code not in (0, None):
            pytest.exit(f"test PG migration failed (exit {exc.code})", returncode=2)
    except psycopg2.OperationalError as exc:
        import warnings

        warnings.warn(f"test PG unavailable, skipping migrations: {exc}")
    yield
