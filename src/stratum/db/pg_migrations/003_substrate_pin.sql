-- Create substrates if it doesn't exist (service-layer copy; DuckDB has its own).
CREATE TABLE IF NOT EXISTS substrates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    mime TEXT,
    source_path TEXT,
    file_hash TEXT,
    byte_size BIGINT,
    page_count INT,
    parser TEXT,
    language TEXT,
    has_cjk BOOLEAN DEFAULT FALSE,
    is_scanned BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    pinned_at TIMESTAMP NULL,
    pin_priority INT DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    meta_json JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_substrate_user ON substrates(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_substrate_pinned
    ON substrates(user_id, is_pinned, pinned_at DESC)
    WHERE is_pinned = TRUE;
