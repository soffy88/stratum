-- 067_bu2_p10_status_authority.sql
--
-- Spec BU2 P10 §5.2: one status authority. Three places disagreed:
--   model       PipelineRunState in bu_v2_models.py (10 values)
--   migration   book_reading_run_status_check (10 values, migration 065)
--   pipeline    book_reading.py wrote the literal "planned", which is in
--               neither of the above, so create_reading_run raised
--               CheckViolation on its first insert against production.
--
-- The spec (§5.1) names a lifecycle vocabulary that migration 065 does not
-- contain: PLANNED, RUNNING, COMPLETED. Those three are what a reading
-- runtime actually needs between CREATED and PERCEIVED, and "planned" was
-- an early attempt at exactly PLANNED.
--
-- Resolution: widen the CHECK to the union of the spec's lifecycle and the
-- existing pipeline vocabulary. Nothing is removed, so every state the
-- frozen contract tests assert remains legal, and the spec's states become
-- legal. One vocabulary, one authority.
--
-- ADDITIVE ONLY: adds states to a CHECK constraint and adds columns. No DROP,
-- no DELETE, no data rewrite. No row changes status.

ALTER TABLE stratum.book_reading_run
    DROP CONSTRAINT IF EXISTS book_reading_run_status_check;

ALTER TABLE stratum.book_reading_run
    ADD CONSTRAINT book_reading_run_status_check CHECK (
        status IN (
            -- Spec §5.1 reading-runtime lifecycle
            'CREATED',
            'PLANNED',
            'RUNNING',
            'COMPLETED',
            -- BU2 pipeline vocabulary (migration 065, frozen contract tests)
            'PERCEIVED',
            'INSPECTED',
            'DEEP_READ_COMPLETE',
            'CHAPTER_MODELLED',
            'BOOK_INTEGRATED',
            'COMPRESSION_TESTED',
            -- Shared terminal states
            'VERIFICATION_PENDING',
            'VERIFIED',
            'FAILED'
        )
    );

-- Spec §5.1 requires one authority for the reading run's identity. A run also
-- records which pass it is on, so a producer can resume without inferring
-- position from status alone.
ALTER TABLE stratum.book_reading_run
    ADD COLUMN IF NOT EXISTS engine_version TEXT NOT NULL DEFAULT 'p10';

-- §9 requires chapter persistence to be unique per (run, chapter). Without
-- this a re-run of one chapter would append a second row for the same
-- chapter, and book integration would double-count it.
CREATE UNIQUE INDEX IF NOT EXISTS uq_chapter_understandings_run_chapter
    ON stratum.chapter_understandings (run_id, chapter_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_chapter_deltas_run_chapter
    ON stratum.chapter_deltas (run_id, chapter_id);

-- §10.4 forbids whole-book understanding from being chapter summaries
-- concatenated. An integration must be able to record which chapters it
-- actually consumed, so the claim is checkable rather than asserted.
ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS integrated_chapter_ids TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS integration_method TEXT NOT NULL DEFAULT '';

-- §13 requires a book expression artifact. It is deliberately NOT a table:
-- an expression is a rendering of a verified BU, and giving it storage would
-- create a second authority for what the book says. It is produced from the
-- BU on demand, and the BU remains the only thing persisted.