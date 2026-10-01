-- 058: Book Understanding 2.0 P4-P9 Repair Round 2 (D5/D6/D7/D8)
--
-- Rules respected: never edits historical migrations 052-057.
-- All statements are IF NOT EXISTS / additive + backfill, safe to re-run.
--
-- book_id provenance contract:
--   book_id = the canonical book identity, REFERENCES stratum.substrates(id).
--   BookReadingRun.source_id already REFERENCES stratum.substrates(id): the book
--   being read. BookUnderstandingV2.book_id MUST equal the substrate row that is
--   the book; substrate_id may point at the same row (or a versioned derivative
--   substrate). VerificationArtifact.book_id MUST equal the BU book_id of its run.

-- ── D6: canonical verification_artifacts table ────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.verification_artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES stratum.substrates(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL', 'BLOCKED')),
    checked_artifacts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_gap_count INTEGER NOT NULL DEFAULT 0,
    verification_timestamp TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_verification_artifacts_run
    ON stratum.verification_artifacts(run_id);

-- ── D5: BookUnderstandingV2.book_id provenance ────────────────────────────────
ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS book_id TEXT REFERENCES stratum.substrates(id) ON DELETE CASCADE;

-- Backfill legacy rows: the book is the substrate the BU was built from.
UPDATE stratum.book_understandings_v2
SET book_id = substrate_id
WHERE book_id IS NULL;

ALTER TABLE stratum.book_understandings_v2
    ALTER COLUMN book_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_book_understandings_v2_book
    ON stratum.book_understandings_v2(book_id);
CREATE INDEX IF NOT EXISTS idx_book_understandings_v2_run
    ON stratum.book_understandings_v2(run_id);

-- ── D7: converge understanding_gaps.status with GapStatus model ───────────────
-- Canonical lifecycle: OPEN -> TARGETED_REREAD_REQUIRED -> REREAD_IN_PROGRESS
-- -> RESOLVED, plus REJECTED triage path. Legacy TARGETED_REREAD_DISPATCHED /
-- RECONCILED / WONTFIX values are preserved for already-persisted rows.
ALTER TABLE stratum.understanding_gaps
    DROP CONSTRAINT IF EXISTS understanding_gaps_status_check;

ALTER TABLE stratum.understanding_gaps
    ADD CONSTRAINT understanding_gaps_status_check CHECK (status IN (
        'OPEN',
        'TARGETED_REREAD_REQUIRED',
        'REREAD_IN_PROGRESS',
        'TARGETED_REREAD_DISPATCHED',
        'RESOLVED',
        'RECONCILED',
        'REJECTED',
        'WONTFIX'
    ));

CREATE INDEX IF NOT EXISTS idx_understanding_gaps_run_status
    ON stratum.understanding_gaps(run_id, status);

-- ── D8: direct run/book provenance on learning_objects ────────────────────────
-- (RetrievalItem traces via learning_objects -> book_understandings_v2 chain.)
ALTER TABLE stratum.learning_objects
    ADD COLUMN IF NOT EXISTS run_id TEXT REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE;

ALTER TABLE stratum.learning_objects
    ADD COLUMN IF NOT EXISTS book_id TEXT REFERENCES stratum.substrates(id) ON DELETE CASCADE;

-- Backfill legacy rows through the BU they were projected from.
UPDATE stratum.learning_objects lo
SET run_id = bu.run_id,
    book_id = bu.book_id
FROM stratum.book_understandings_v2 bu
WHERE lo.bu_id = bu.id
  AND (lo.run_id IS NULL OR lo.book_id IS NULL);

CREATE INDEX IF NOT EXISTS idx_learning_objects_run
    ON stratum.learning_objects(run_id);
CREATE INDEX IF NOT EXISTS idx_learning_objects_book
    ON stratum.learning_objects(book_id);
