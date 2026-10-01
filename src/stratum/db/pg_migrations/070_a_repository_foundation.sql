-- 070: A Repository Foundation — Stratum A仓真实书籍理解事实仓
--
-- Rules respected: additive only; never edits migrations 060-066.
-- All statements are CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS,
-- safe to re-run.
--
-- A仓 scope: raw book understanding facts only.
--   No B仓 concept deduplication.
--   No C仓 derivation.
--   No automatic merging of Knowledge Units.
--
-- Object model:
--   BookSource -> SourceVersion -> ReadingRun -> ReadingEvidence -> KUCandidate

-- ── 1. book_source ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.book_source (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    publisher TEXT,
    isbn TEXT,
    language TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_book_source_title
    ON stratum.book_source(title);

-- ── 2. source_version ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.source_version (
    id TEXT PRIMARY KEY,
    book_source_id TEXT NOT NULL REFERENCES stratum.book_source(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    storage_uri TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_version_book
    ON stratum.source_version(book_source_id);

CREATE INDEX IF NOT EXISTS idx_source_version_file_hash
    ON stratum.source_version(file_hash);

-- ── 3. reading_run ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.reading_run (
    id TEXT PRIMARY KEY,
    source_version_id TEXT NOT NULL REFERENCES stratum.source_version(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'CREATED',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_reading_run_source_version
    ON stratum.reading_run(source_version_id);

CREATE INDEX IF NOT EXISTS idx_reading_run_status
    ON stratum.reading_run(status);

-- ── 4. reading_evidence ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.reading_evidence (
    id TEXT PRIMARY KEY,
    reading_run_id TEXT NOT NULL REFERENCES stratum.reading_run(id) ON DELETE CASCADE,
    page_number INTEGER,
    location JSONB NOT NULL DEFAULT '{}'::jsonb,
    content TEXT,
    evidence_type TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reading_evidence_run
    ON stratum.reading_evidence(reading_run_id);

CREATE INDEX IF NOT EXISTS idx_reading_evidence_page
    ON stratum.reading_evidence(reading_run_id, page_number);

-- ── 5. ku_candidate ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.ku_candidate (
    id TEXT PRIMARY KEY,
    reading_run_id TEXT NOT NULL REFERENCES stratum.reading_run(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES stratum.reading_evidence(id) ON DELETE CASCADE,
    content TEXT,
    candidate_type TEXT,
    confidence FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ku_candidate_run
    ON stratum.ku_candidate(reading_run_id);

CREATE INDEX IF NOT EXISTS idx_ku_candidate_evidence
    ON stratum.ku_candidate(evidence_id);
