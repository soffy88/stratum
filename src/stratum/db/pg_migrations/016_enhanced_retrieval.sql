-- 016_enhanced_retrieval.sql
-- Migration for enhanced retrieval features:
--   1. purge_journal table (document deletion audit)
--   2. multimodal_assets table (images, tables, formulas)
--   3. substrate_layers UNIQUE constraint fix (substrate_id, layer)
--   4. Add embedding column to graph_entities (for KG-enhanced retrieval)

-- ── 1. purge_journal table ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stratum.purge_journal (
    id          TEXT PRIMARY KEY,
    substrate_id TEXT NOT NULL,
    action      TEXT NOT NULL,          -- 'soft_delete' | 'hard_delete' | 'restore'
    reason      TEXT,
    details     JSONB DEFAULT '{}',     -- Per-table deletion counts
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purge_journal_substrate
    ON stratum.purge_journal(substrate_id);

CREATE INDEX IF NOT EXISTS idx_purge_journal_created
    ON stratum.purge_journal(created_at DESC);

-- ── 2. multimodal_assets table ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stratum.multimodal_assets (
    id              TEXT PRIMARY KEY,
    substrate_id    TEXT NOT NULL REFERENCES stratum.substrates(id),
    asset_type      TEXT NOT NULL,      -- 'image' | 'table' | 'formula'
    page_num        INTEGER,
    position        INTEGER,
    bbox            TEXT,               -- JSON: [x0, y0, x1, y1]
    width           INTEGER,
    height          INTEGER,
    format          TEXT,               -- 'png' | 'jpeg' | 'svg' | 'latex' | 'markdown'
    content         TEXT,               -- OCR text / markdown table / LaTeX
    html_content    TEXT,               -- HTML version (for tables)
    description     TEXT,               -- VLM-generated description
    embedding       VECTOR(1024),       -- Embedding of description for search
    thumbnail_b64   TEXT,               -- Base64 thumbnail (for images)
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_multimodal_substrate
    ON stratum.multimodal_assets(substrate_id);

CREATE INDEX IF NOT EXISTS idx_multimodal_type
    ON stratum.multimodal_assets(asset_type);

CREATE INDEX IF NOT EXISTS idx_multimodal_embedding
    ON stratum.multimodal_assets USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- ── 3. Ensure substrate_layers has UNIQUE constraint ───────────────────────

DO $$
BEGIN
    -- Check if unique constraint exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_substrate_layers_substrate_layer'
    ) THEN
        -- First, deduplicate: keep only the latest row per (substrate_id, layer)
        DELETE FROM stratum.substrate_layers a
        USING stratum.substrate_layers b
        WHERE a.substrate_id = b.substrate_id
          AND a.layer = b.layer
          AND a.id != b.id
          AND a.generated_at < b.generated_at;

        -- Then add the unique constraint
        ALTER TABLE stratum.substrate_layers
            ADD CONSTRAINT uq_substrate_layers_substrate_layer
            UNIQUE (substrate_id, layer);
    END IF;
END $$;

-- Same for ku_layers
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_ku_layers_ku_layer'
    ) THEN
        DELETE FROM stratum.ku_layers a
        USING stratum.ku_layers b
        WHERE a.ku_id = b.ku_id
          AND a.layer = b.layer
          AND a.id != b.id
          AND a.generated_at < b.generated_at;

        ALTER TABLE stratum.ku_layers
            ADD CONSTRAINT uq_ku_layers_ku_layer
            UNIQUE (ku_id, layer);
    END IF;
END $$;

-- ── 4. Add embedding column to graph_entities (KG-enhanced retrieval) ───────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'stratum'
          AND table_name = 'graph_entities'
          AND column_name = 'embedding'
    ) THEN
        ALTER TABLE stratum.graph_entities
            ADD COLUMN embedding VECTOR(1024);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_graph_entities_embedding
    ON stratum.graph_entities USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

-- ── 5. Add deleted_at to derivative table (soft delete support) ─────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'stratum'
          AND table_name = 'derivative'
          AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE stratum.derivative
            ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END $$;

-- ── 6. Add deleted_at to highlights table ──────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'stratum'
          AND table_name = 'highlights'
          AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE stratum.highlights
            ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END $$;
