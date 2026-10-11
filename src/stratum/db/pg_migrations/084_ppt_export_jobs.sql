-- 084: book -> editable PPT export jobs (luobo-ppt engine).
-- One row per generation request. user_id holds the hashed owner id
-- (stratum.utils.user_id_hash), the same form substrates.user_id uses; every
-- read filters on it, so a job id alone never grants access.

CREATE TABLE IF NOT EXISTS stratum.ppt_export_jobs (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    substrate_id  TEXT NOT NULL REFERENCES stratum.substrates(id) ON DELETE CASCADE,
    run_id        TEXT,
    chapter_id    TEXT,
    style         TEXT NOT NULL,
    pages         INTEGER NOT NULL CHECK (pages BETWEEN 1 AND 60),
    options_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status        TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    stage         TEXT,
    progress      INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    title         TEXT,
    language      TEXT,
    file_path     TEXT,
    file_size     BIGINT,
    slide_count   INTEGER,
    preview_count INTEGER NOT NULL DEFAULT 0,
    qa_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    model         TEXT,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ppt_export_jobs_owner
    ON stratum.ppt_export_jobs (user_id, substrate_id, created_at DESC);
