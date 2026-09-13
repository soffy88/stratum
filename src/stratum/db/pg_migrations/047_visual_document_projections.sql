-- Rebuildable projections only.  Canonical substrates/chunks remain the
-- authority; these tables contain pointers and derived data.
CREATE TABLE IF NOT EXISTS stratum.visual_region_projection (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fragment_id TEXT,
    page_number INTEGER NOT NULL CHECK (page_number >= 1),
    region_index INTEGER NOT NULL CHECK (region_index >= 0),
    bbox_json JSONB NOT NULL,
    tile_uri TEXT NOT NULL,
    tile_hash TEXT NOT NULL,
    render_hash TEXT NOT NULL,
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    embedding vector,
    embedding_model TEXT,
    embedding_dim INTEGER,
    projection_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_visual_region_owner_source
    ON stratum.visual_region_projection(user_id, source_id, page_number)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS stratum.translation_projection (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    target_language TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    translated_artifact_uri TEXT,
    artifact_hash TEXT,
    alignment_version TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_translation_projection_request
    ON stratum.translation_projection(user_id, source_id, source_version, target_language, provider);
CREATE TABLE IF NOT EXISTS stratum.translation_fragment_projection (
    translation_id TEXT NOT NULL REFERENCES stratum.translation_projection(id) ON DELETE CASCADE,
    original_fragment_id TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    page_number INTEGER,
    alignment_score DOUBLE PRECISION,
    translated_range JSONB,
    original_range JSONB,
    PRIMARY KEY (translation_id, original_fragment_id)
);

CREATE TABLE IF NOT EXISTS stratum.derived_artifact (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    content_uri TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    producer_type TEXT NOT NULL,
    producer_name TEXT NOT NULL,
    producer_version TEXT,
    model TEXT,
    prompt_hash TEXT,
    environment_hash TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    supersedes_id TEXT REFERENCES stratum.derived_artifact(id)
);
CREATE INDEX IF NOT EXISTS idx_derived_artifact_owner ON stratum.derived_artifact(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS stratum.artifact_input (
    artifact_id TEXT NOT NULL REFERENCES stratum.derived_artifact(id) ON DELETE CASCADE,
    source_id TEXT,
    fragment_id TEXT,
    evidence_id TEXT,
    claim_id TEXT,
    artifact_parent_id TEXT REFERENCES stratum.derived_artifact(id),
    PRIMARY KEY (artifact_id, source_id, fragment_id, evidence_id, claim_id, artifact_parent_id)
);
