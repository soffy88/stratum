-- P1.4: per-chunk vectors for substrate content, BGE-M3 1024-dim (matches AII → cross-search).
-- Replaces the LanceDB(Qwen3) vector index. HNSW index created at end of the re-embed batch.
CREATE TABLE IF NOT EXISTS stratum.substrate_chunk (
    id           TEXT PRIMARY KEY,          -- {substrate_id}#{chunk_idx}
    substrate_id TEXT NOT NULL,
    chunk_idx    INTEGER NOT NULL,
    text         TEXT NOT NULL,
    embedding    vector(1024),
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_substrate_chunk_sub ON stratum.substrate_chunk(substrate_id);
