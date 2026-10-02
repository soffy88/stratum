-- 019: FSRS scheduler state, user retention preference, and Evidence fields.
-- Non-destructive: the legacy SM-2 columns stay available for old exports and
-- clients while new reviews write the canonical FSRS state.

ALTER TABLE stratum.flashcards
    ADD COLUMN IF NOT EXISTS fsrs_state SMALLINT NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS fsrs_step INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS stability DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS difficulty DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS last_review_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS desired_retention DOUBLE PRECISION NOT NULL DEFAULT 0.9;

CREATE TABLE IF NOT EXISTS stratum.learning_preferences (
    user_id TEXT PRIMARY KEY,
    desired_retention DOUBLE PRECISION NOT NULL DEFAULT 0.9
        CHECK (desired_retention >= 0.5 AND desired_retention <= 0.99),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE stratum.highlights
    ADD COLUMN IF NOT EXISTS text TEXT,
    ADD COLUMN IF NOT EXISTS location_json JSONB,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS quote_hash TEXT,
    ADD COLUMN IF NOT EXISTS locator_json JSONB;

CREATE INDEX IF NOT EXISTS idx_highlights_quote_hash
    ON stratum.highlights (quote_hash);

-- Older 007_highlights used a required `anchor` column.  The canonical
-- locator_json field supersedes it; make old rows writable without deleting
-- the column or its historical data.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'stratum' AND table_name = 'highlights' AND column_name = 'anchor'
    ) THEN
        ALTER TABLE stratum.highlights ALTER COLUMN anchor DROP NOT NULL;
    END IF;
END $$;
