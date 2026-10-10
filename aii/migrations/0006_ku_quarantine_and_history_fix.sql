-- 0006: ku_onto is missing is_quarantined (multiple PgBackend methods already
-- SELECT/filter on it — quarantine_ku() was a documented no-op because of this
-- gap). ku_state_history.ku_id was UUID while live ku_onto.ku_id is free-text
-- (e.g. "advmath_tongji_full::10::三重积分") — every record_state_change() call
-- against real data would fail to cast and roll back. Table was empty (0 rows)
-- so this is a pure type correction, no data migration needed.

ALTER TABLE aii.ku_state_history ALTER COLUMN ku_id TYPE TEXT;

ALTER TABLE aii.ku_onto ADD COLUMN IF NOT EXISTS is_quarantined BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_ku_onto_quarantined ON aii.ku_onto(is_quarantined) WHERE is_quarantined = TRUE;
