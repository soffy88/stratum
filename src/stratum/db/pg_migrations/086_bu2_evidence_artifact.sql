-- 086_bu2_evidence_artifact.sql
-- Traceability: every ev_* id a chapter understanding cites must resolve to a
-- stored span of the book. Until now EvidenceArtifact lived only in memory, so
-- persisted runs carried evidence ids with no quote or locator behind them.
-- Additive and idempotent.

CREATE TABLE IF NOT EXISTS stratum.bu2_evidence_artifact (
    id            TEXT NOT NULL,
    run_id        TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    chapter_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,
    locator       TEXT NOT NULL,
    quote         TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    strength      TEXT,
    verified      BOOLEAN,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, id),
    CHECK (length(btrim(quote)) > 0),
    CHECK (length(btrim(locator)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_bu2_evidence_artifact_run_chapter
    ON stratum.bu2_evidence_artifact (run_id, chapter_id);
