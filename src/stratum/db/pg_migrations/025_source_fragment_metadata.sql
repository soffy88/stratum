-- 025_source_fragment_metadata.sql
-- Close the canonical Source/Fragment schema gap used by parser provenance.
-- Existing rows receive conservative defaults; no source content is rewritten.

ALTER TABLE stratum.substrates
    ADD COLUMN IF NOT EXISTS license TEXT;

-- Fresh bootstrap historically omitted substrate_chunk.sql, so make the
-- canonical Fragment table available here as well as in the schema snapshot.
CREATE TABLE IF NOT EXISTS stratum.substrate_chunk (
    id            TEXT PRIMARY KEY,
    substrate_id  TEXT NOT NULL,
    chunk_idx     INTEGER NOT NULL,
    text          TEXT NOT NULL,
    embedding     vector(1024),
    version       INTEGER NOT NULL DEFAULT 1,
    anchor_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    parser_version TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE stratum.substrate_chunk
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE stratum.substrate_chunk
    ADD COLUMN IF NOT EXISTS anchor_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE stratum.substrate_chunk
    ADD COLUMN IF NOT EXISTS parser_version TEXT;

CREATE INDEX IF NOT EXISTS idx_substrate_chunk_sub_version
    ON stratum.substrate_chunk(substrate_id, version, chunk_idx);
