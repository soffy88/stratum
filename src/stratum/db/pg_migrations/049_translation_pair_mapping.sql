-- Adapter-owned N:M provenance between captured provider calls and canonical
-- fragments.  It never creates or replaces canonical knowledge objects.
ALTER TABLE stratum.translation_projection
    ADD COLUMN IF NOT EXISTS artifact_id TEXT REFERENCES stratum.derived_artifact(id);

CREATE TABLE IF NOT EXISTS stratum.translation_pair_mapping (
    translation_id TEXT NOT NULL REFERENCES stratum.translation_projection(id) ON DELETE CASCADE,
    pair_ordinal INTEGER NOT NULL CHECK (pair_ordinal >= 0),
    original_fragment_id TEXT NOT NULL,
    fragment_overlap_start INTEGER NOT NULL CHECK (fragment_overlap_start >= 0),
    fragment_overlap_end INTEGER NOT NULL CHECK (fragment_overlap_end >= fragment_overlap_start),
    pair_overlap_start INTEGER NOT NULL CHECK (pair_overlap_start >= 0),
    pair_overlap_end INTEGER NOT NULL CHECK (pair_overlap_end >= pair_overlap_start),
    alignment_method TEXT NOT NULL,
    alignment_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (translation_id, pair_ordinal, original_fragment_id)
);
CREATE INDEX IF NOT EXISTS idx_translation_pair_mapping_fragment
    ON stratum.translation_pair_mapping(translation_id, original_fragment_id);
