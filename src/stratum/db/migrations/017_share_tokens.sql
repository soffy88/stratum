-- 017_share_tokens.sql

CREATE TABLE IF NOT EXISTS share_tokens (
    token           VARCHAR PRIMARY KEY,
    resource_type   VARCHAR NOT NULL,
    resource_id     VARCHAR NOT NULL,
    corpus_id       VARCHAR NOT NULL,
    created_by      VARCHAR NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP,
    revoked_at      TIMESTAMP,
    access_count    INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    allow_anonymous BOOLEAN DEFAULT TRUE,
    meta_json       VARCHAR DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_share_tokens_resource ON share_tokens(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_share_tokens_created_by ON share_tokens(created_by, created_at);
