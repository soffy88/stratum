-- Canonical Fragment authority used by the parser and KnowledgeView.
-- Kept separate from the legacy platform_content_chunk projection.
CREATE TABLE IF NOT EXISTS stratum.substrate_chunk (
    id              TEXT PRIMARY KEY,
    substrate_id    TEXT NOT NULL REFERENCES stratum.substrates(id),
    chunk_idx       INTEGER NOT NULL,
    text            TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    anchor_json     JSONB,
    parser_version  TEXT,
    embedding       VECTOR(1024),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (substrate_id, chunk_idx)
);

CREATE INDEX IF NOT EXISTS idx_substrate_chunk_substrate
    ON stratum.substrate_chunk (substrate_id, chunk_idx);

CREATE INDEX IF NOT EXISTS idx_substrate_chunk_embedding
    ON stratum.substrate_chunk USING ivfflat (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
