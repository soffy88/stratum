-- 0007: contradiction detection (scripts/detect_contradictions.py --apply)
-- writes rows to aii.ku_contradiction but nothing ever read/acted on them —
-- detection with no resolution loop. Adds status tracking so /governance
-- routes can list pending contradictions and record how each was resolved.

ALTER TABLE aii.ku_contradiction ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE aii.ku_contradiction ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
ALTER TABLE aii.ku_contradiction ADD COLUMN IF NOT EXISTS resolution_note TEXT;

CREATE INDEX IF NOT EXISTS idx_ku_contradiction_status ON aii.ku_contradiction(status) WHERE status = 'pending';
