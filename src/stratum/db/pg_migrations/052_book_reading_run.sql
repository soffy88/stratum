-- 052: Book Understanding 2.0 P2 - Reading Evidence Foundation

CREATE TABLE IF NOT EXISTS stratum.book_reading_run (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT,
    status TEXT NOT NULL CHECK (status IN ('planned', 'in_progress', 'paused', 'completed', 'failed', 'needs_repair')),
    current_pass INTEGER NOT NULL DEFAULT 1,
    parser_version TEXT,
    reader_version TEXT,
    extractor_version TEXT,
    verifier_version TEXT,
    coverage_json JSONB NOT NULL DEFAULT '{}'::jsonb, -- ReadingCoverage, EvidenceCoverage, UnderstandingCoverage separated
    open_gaps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (source_id) REFERENCES stratum.substrates(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_book_reading_run_source ON stratum.book_reading_run (user_id, source_id);

CREATE TABLE IF NOT EXISTS stratum.reading_ledger (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('chapter', 'section', 'page', 'fragment', 'figure', 'table', 'equation')),
    item_identifier TEXT NOT NULL, -- e.g., page number, section id
    status TEXT NOT NULL CHECK (status IN ('UNSEEN', 'PARSED', 'READ', 'INTERPRETED', 'RECONCILED', 'VERIFIED', 'UNREADABLE', 'NEEDS_VISUAL_REVIEW')),
    locator_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    page_number INTEGER,
    expected BOOLEAN NOT NULL DEFAULT true, -- part of full source accounting
    trace_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, item_type, item_identifier)
);

CREATE INDEX IF NOT EXISTS idx_reading_ledger_run_status ON stratum.reading_ledger (run_id, status);

