"""Shared test fixtures for Stratum tests."""
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
"""


@pytest.fixture
def db():
    """In-memory DuckDB with full schema for testing."""
    conn = duckdb.connect(":memory:")
    conn.execute(SCHEMA_SQL)
    yield conn
    conn.close()
