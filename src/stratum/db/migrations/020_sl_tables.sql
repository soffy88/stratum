-- 020_sl_tables.sql
-- DB merge: PG service-layer schema → DuckDB-compatible DDL
--
-- R1 (SPEC v1.1): changefeed uses explicit SEQUENCE, not BIGSERIAL/rowid.
-- DuckDB 1.5.2 adaptations:
--   JSONB          → JSON
--   TEXT[]         → VARCHAR[]
--   GIN indexes    → omitted (not supported)
--   Partial indexes (WHERE ...) → regular indexes (not supported in 1.5.2)
--   ivfflat        → omitted; embedding stored as FLOAT[1024]
--   UUID           → VARCHAR (all user_id columns)
--   BIGSERIAL      → BIGINT + explicit SEQUENCE
--   ON DELETE CASCADE syntax accepted; FK not enforced by DuckDB
--
-- Naming: tables that collide with existing DuckDB schema get _sl suffix.
--   agent_runs → agent_runs_sl   (DuckDB has: agent_runs)
--   notes      → notes_sl        (DuckDB has: note)
--   views      → user_views      (DuckDB has: views)
--   scheduled_jobs/runs → *_sl   (DuckDB has both)
--   substrates, concepts — distinct names, created directly

-- ── agent_runs_sl (from PG 002_agent_runs_trace) ─────────────────────────────

CREATE TABLE IF NOT EXISTS agent_runs_sl (
    id               VARCHAR PRIMARY KEY,
    user_id          VARCHAR NOT NULL,
    corpus_id        VARCHAR,
    agent_name       VARCHAR NOT NULL,
    params           JSON DEFAULT '{}',
    status           VARCHAR NOT NULL DEFAULT 'pending',
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP,
    total_input_tokens  INT DEFAULT 0,
    total_output_tokens INT DEFAULT 0,
    cost_usd         FLOAT DEFAULT 0.0,
    error            VARCHAR,
    trace            JSON,
    citations        JSON,
    files_generated  JSON
);

CREATE INDEX IF NOT EXISTS idx_arsl_user   ON agent_runs_sl(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_arsl_status ON agent_runs_sl(status);

-- ── substrates (from PG 003_substrate_pin) ───────────────────────────────────
-- DuckDB has singular 'substrate'; this is the SL copy.

CREATE TABLE IF NOT EXISTS substrates (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR NOT NULL,
    title        VARCHAR,
    mime         VARCHAR,
    source_path  VARCHAR,
    file_hash    VARCHAR,
    byte_size    BIGINT,
    page_count   INT,
    parser       VARCHAR,
    language     VARCHAR,
    has_cjk      BOOLEAN DEFAULT FALSE,
    is_scanned   BOOLEAN DEFAULT FALSE,
    is_pinned    BOOLEAN DEFAULT FALSE,
    pinned_at    TIMESTAMP,
    pin_priority INT DEFAULT 0,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW(),
    meta_json    JSON DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_substrates_user ON substrates(user_id, created_at DESC);
-- Partial index (WHERE is_pinned = TRUE) omitted — DuckDB 1.5.2 not supported.
CREATE INDEX IF NOT EXISTS idx_substrates_pinned ON substrates(user_id, is_pinned, pinned_at DESC);

-- ── user_views (from PG 004_views) ───────────────────────────────────────────
-- Renamed: DuckDB has a 'views' table already.

CREATE TABLE IF NOT EXISTS user_views (
    id                    VARCHAR PRIMARY KEY,
    user_id               VARCHAR NOT NULL,
    name                  VARCHAR NOT NULL,
    description           VARCHAR,
    default_filter        JSON DEFAULT '{}',
    default_llm           JSON DEFAULT '{}',
    default_system_prompt VARCHAR,
    default_agents        JSON DEFAULT '[]',
    icon                  VARCHAR,
    is_default            BOOLEAN DEFAULT FALSE,
    created_at            TIMESTAMP DEFAULT NOW(),
    updated_at            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_views_user ON user_views(user_id);

-- ── platform_content (from PG 005_platform_content) ──────────────────────────

CREATE TABLE IF NOT EXISTS platform_content (
    id                   VARCHAR PRIMARY KEY,
    type                 VARCHAR NOT NULL,
    title                VARCHAR NOT NULL,
    author               VARCHAR DEFAULT 'hevi',
    body_markdown        VARCHAR,
    body_html            VARCHAR,
    audio_url            VARCHAR,
    duration_seconds     INT,
    published_at         TIMESTAMP NOT NULL,
    updated_at           TIMESTAMP,
    version              INT DEFAULT 1,
    domain               VARCHAR[],
    tags                 VARCHAR[],
    related_content_ids  VARCHAR[],
    related_concepts     VARCHAR[],
    access_tier          VARCHAR NOT NULL DEFAULT 'free',
    deleted_at           TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pc_published ON platform_content(published_at DESC);
-- GIN indexes (idx_pc_domain, idx_pc_search) omitted — not supported in DuckDB.

-- ── platform_content_chunk (from PG 005 + 006 pgvector→FLOAT[1024]) ──────────

CREATE TABLE IF NOT EXISTS platform_content_chunk (
    id          VARCHAR PRIMARY KEY,
    content_id  VARCHAR NOT NULL REFERENCES platform_content(id),
    chunk_idx   INT NOT NULL,
    text        VARCHAR NOT NULL,
    chunk_meta  JSON DEFAULT '{}',
    embedding   FLOAT[1024]   -- pgvector vector(1024) → DuckDB FLOAT[1024]
);

CREATE INDEX IF NOT EXISTS idx_chunk_content ON platform_content_chunk(content_id);
-- ivfflat ANN index (idx_chunk_embedding) omitted — not supported in DuckDB.

-- ── platform_concepts (from PG 005_platform_content) ─────────────────────────

CREATE TABLE IF NOT EXISTS platform_concepts (
    id                  VARCHAR PRIMARY KEY,
    label               VARCHAR NOT NULL,
    type                VARCHAR NOT NULL,
    definition          VARCHAR,
    hevi_perspective    VARCHAR,
    applicability       VARCHAR,
    common_mistakes     VARCHAR,
    related_concept_ids VARCHAR[],
    domain              VARCHAR[],
    version             INT DEFAULT 1,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ── user_content_interaction (from PG 005_platform_content) ──────────────────

CREATE TABLE IF NOT EXISTS user_content_interaction (
    id               VARCHAR PRIMARY KEY,
    user_id          VARCHAR NOT NULL,
    content_id       VARCHAR NOT NULL,
    interaction_type VARCHAR NOT NULL,
    payload          JSON DEFAULT '{}',
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uci_user_content ON user_content_interaction(user_id, content_id);
CREATE INDEX IF NOT EXISTS idx_uci_type          ON user_content_interaction(interaction_type);

-- ── highlights (from PG 007_highlights) — CHECK constraint preserved ──────────

CREATE TABLE IF NOT EXISTS highlights (
    id             VARCHAR PRIMARY KEY,
    user_id        VARCHAR NOT NULL,
    content_id     VARCHAR,
    substrate_id   VARCHAR,
    anchor         JSON NOT NULL,
    color          VARCHAR DEFAULT 'yellow',
    note           VARCHAR,
    status         VARCHAR DEFAULT 'active',
    status_message VARCHAR,
    created_at     TIMESTAMP DEFAULT NOW(),
    CONSTRAINT hl_target_check CHECK (
        content_id IS NOT NULL OR substrate_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_hl_user      ON highlights(user_id);
-- Partial indexes converted to regular (WHERE ... not supported):
CREATE INDEX IF NOT EXISTS idx_hl_content   ON highlights(content_id);
CREATE INDEX IF NOT EXISTS idx_hl_substrate ON highlights(substrate_id);

-- ── subscriptions (from PG 008_subscriptions) ────────────────────────────────

CREATE TABLE IF NOT EXISTS subscriptions (
    id               VARCHAR PRIMARY KEY,
    user_id          VARCHAR NOT NULL,
    tier             VARCHAR NOT NULL DEFAULT 'free',
    plan             VARCHAR NOT NULL,
    status           VARCHAR NOT NULL DEFAULT 'active',
    started_at       TIMESTAMP NOT NULL,
    expires_at       TIMESTAMP,
    cancelled_at     TIMESTAMP,
    payment_provider VARCHAR,
    payment_ref      VARCHAR,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);

-- ── changefeed (from PG 009_changefeed) — R1: explicit SEQUENCE ──────────────
-- DROP first: a legacy changefeed_seq may exist from old DuckDB-based changefeed_events.
-- The changefeed TABLE is new in this migration, so dropping the seq is safe.

DROP SEQUENCE IF EXISTS changefeed_seq;
CREATE SEQUENCE changefeed_seq START 1;

CREATE TABLE IF NOT EXISTS changefeed (
    seq        BIGINT  DEFAULT nextval('changefeed_seq') PRIMARY KEY,
    event_id   VARCHAR NOT NULL UNIQUE,
    user_id    VARCHAR NOT NULL,
    device_id  VARCHAR NOT NULL DEFAULT 'server',
    timestamp  TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type VARCHAR NOT NULL,
    payload    JSON DEFAULT '{}',
    processed  BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_cf_user_seq ON changefeed(user_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_cf_type     ON changefeed(event_type);

-- ── recommendations (from PG 010_recommendations) ────────────────────────────

CREATE TABLE IF NOT EXISTS recommendations (
    id         VARCHAR PRIMARY KEY,
    user_id    VARCHAR NOT NULL,
    content_id VARCHAR NOT NULL,
    score      FLOAT NOT NULL DEFAULT 0.0,
    reason     VARCHAR,
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rec_user ON recommendations(user_id, created_at DESC);

-- ── notes_sl (from PG 011_notes) — renamed, DuckDB has 'note' ────────────────

CREATE TABLE IF NOT EXISTS notes_sl (
    id               VARCHAR PRIMARY KEY,
    user_id          VARCHAR NOT NULL,
    title            VARCHAR NOT NULL,
    content_markdown VARCHAR,
    substrate_refs   VARCHAR[],
    concept_refs     VARCHAR[],
    content_refs     VARCHAR[],
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW(),
    deleted_at       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notes_sl_user ON notes_sl(user_id, updated_at DESC);
-- Partial index (WHERE deleted_at IS NULL) omitted — DuckDB 1.5.2 not supported.
CREATE INDEX IF NOT EXISTS idx_notes_sl_alive ON notes_sl(user_id);

-- ── concepts (from PG 012_concepts) — DuckDB has 'concept' singular ───────────

CREATE TABLE IF NOT EXISTS concepts (
    id                  VARCHAR PRIMARY KEY,
    user_id             VARCHAR NOT NULL,
    name                VARCHAR NOT NULL,
    type                VARCHAR NOT NULL DEFAULT 'concept_idea',
    aliases             VARCHAR[],
    wikilink            VARCHAR,
    substrate_refs      VARCHAR[],
    related_concept_ids VARCHAR[],
    created_at          TIMESTAMP DEFAULT NOW(),
    deleted_at          TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts(user_id, name);

-- ── scheduled_jobs_sl (from PG 013_scheduled_job_runs) ───────────────────────

CREATE TABLE IF NOT EXISTS scheduled_jobs_sl (
    id              VARCHAR PRIMARY KEY,
    user_id         VARCHAR NOT NULL,
    name            VARCHAR NOT NULL,
    agent_name      VARCHAR NOT NULL,
    cron_expression VARCHAR NOT NULL DEFAULT '0 8 * * *',
    timezone        VARCHAR NOT NULL DEFAULT 'Asia/Shanghai',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    max_items       INT DEFAULT 20,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sjsl_enabled ON scheduled_jobs_sl(enabled);

-- ── scheduled_job_runs_sl (from PG 013_scheduled_job_runs) ───────────────────

CREATE TABLE IF NOT EXISTS scheduled_job_runs_sl (
    id           VARCHAR PRIMARY KEY,
    job_id       VARCHAR NOT NULL,
    status       VARCHAR NOT NULL DEFAULT 'pending',
    started_at   TIMESTAMP,
    completed_at TIMESTAMP,
    error        JSON,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sjrsl_job ON scheduled_job_runs_sl(job_id, created_at DESC);
