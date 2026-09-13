-- Runtime metadata for the derived translation-fragment projection.
ALTER TABLE stratum.translation_fragment_projection
    ADD COLUMN IF NOT EXISTS id TEXT,
    ADD COLUMN IF NOT EXISTS user_id TEXT,
    ADD COLUMN IF NOT EXISTS source_id TEXT,
    ADD COLUMN IF NOT EXISTS alignment_status TEXT,
    ADD COLUMN IF NOT EXISTS alignment_method TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE stratum.translation_fragment_projection fp
SET id = md5(fp.translation_id || ':' || fp.original_fragment_id),
    user_id = tp.user_id,
    source_id = tp.source_id,
    alignment_status = COALESCE(fp.alignment_status, 'aligned'),
    alignment_method = COALESCE(fp.alignment_method, 'legacy')
FROM stratum.translation_projection tp
WHERE tp.id = fp.translation_id
  AND (fp.id IS NULL OR fp.user_id IS NULL OR fp.source_id IS NULL);

ALTER TABLE stratum.translation_fragment_projection
    ALTER COLUMN id SET NOT NULL,
    ALTER COLUMN user_id SET NOT NULL,
    ALTER COLUMN source_id SET NOT NULL,
    ALTER COLUMN alignment_status SET DEFAULT 'unresolved';

CREATE UNIQUE INDEX IF NOT EXISTS uq_translation_fragment_projection_id
    ON stratum.translation_fragment_projection(id);
CREATE INDEX IF NOT EXISTS idx_translation_fragment_projection_owner
    ON stratum.translation_fragment_projection(user_id, source_id, translation_id);
