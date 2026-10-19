-- 092_note_revisions.sql
-- AII Notes version history (append-only).
--
-- Each successful PUT /api/v1/notes/{id} snapshots the pre-edit title and
-- content_markdown as a new row here (cause=edit); restoring an old
-- version inserts another row (cause=restore) and then rewrites the
-- current notes_sl row — history is never modified in place.
--
-- Semantics:
--   * Rows are INSERT-only. No code path may UPDATE or DELETE a revision row.
--   * version = per-note monotonic counter (MAX(version) + 1 at write time).
--     Row N captures the note content *before* transition N, so the live
--     notes_sl row always holds the content *after* the latest transition.
--   * superseded_by is reserved for a forward chain link; it stays NULL
--     because backfilling it would require UPDATEs, which append-only forbids.
--   * A hard purge of the note (DELETE ...?purge=true) cascades and removes
--     its revisions with it (ON DELETE CASCADE) — true delete means no trace.
--
-- Additive and idempotent (IF NOT EXISTS everywhere). No existing row or
-- table is touched.

CREATE TABLE IF NOT EXISTS stratum.note_revisions (
    id               TEXT PRIMARY KEY,
    note_id          TEXT NOT NULL REFERENCES stratum.notes_sl(id) ON DELETE CASCADE,
    version          INT NOT NULL,
    title            TEXT,
    content_markdown TEXT,
    author_user_id   TEXT,
    cause            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by    TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_note_revisions_note_version
    ON stratum.note_revisions (note_id, version DESC);
