-- 025_derivative_table.sql
-- Create missing derivative table for service layer.
-- Found missing during E2E R-3 verification.

CREATE TABLE IF NOT EXISTS derivative (
    id             VARCHAR PRIMARY KEY,
    substrate_id   VARCHAR NOT NULL,
    kind           VARCHAR NOT NULL,
    seq            INT DEFAULT 0,
    content        VARCHAR,
    embedding_id   VARCHAR,
    embedding_dim  INT,
    meta_json      JSON DEFAULT '{}',
    created_at     TIMESTAMP DEFAULT NOW(),
    corpus_id      VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_derivative_substrate ON derivative(substrate_id);
CREATE INDEX IF NOT EXISTS idx_derivative_corpus    ON derivative(corpus_id);

-- ── changefeed_local (SPEC v0.3 logic used by some components) ──────────────

CREATE TABLE IF NOT EXISTS changefeed_local (
    seq        BIGINT DEFAULT nextval('changefeed_seq') PRIMARY KEY,
    table_name VARCHAR NOT NULL,
    row_id     VARCHAR NOT NULL,
    op         VARCHAR NOT NULL,
    payload    JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
