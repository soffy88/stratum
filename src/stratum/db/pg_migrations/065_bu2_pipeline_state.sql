-- 057: Pipeline State Machine Hardening

-- Update the status enum for book_reading_run to match BU2 Pipeline states
ALTER TABLE stratum.book_reading_run DROP CONSTRAINT IF EXISTS book_reading_run_status_check;

ALTER TABLE stratum.book_reading_run ADD CONSTRAINT book_reading_run_status_check CHECK (
    status IN (
        'CREATED',
        'PERCEIVED',
        'INSPECTED',
        'DEEP_READ_COMPLETE',
        'CHAPTER_MODELLED',
        'BOOK_INTEGRATED',
        'VERIFICATION_PENDING',
        'VERIFIED',
        'COMPRESSION_TESTED',
        'FAILED'
    )
);

-- Add failure_reason for persistence of failure state
ALTER TABLE stratum.book_reading_run ADD COLUMN IF NOT EXISTS failure_reason TEXT;
