-- 093: AII Notes lexical projection — pg_trgm GIN index over the note
-- title + Markdown body, so user-authored note content can enter the single
-- KnowledgeView retrieval plane (scope "user-authored").
--
-- Lock note: run_pg_migrations applies each file inside one transaction
-- (_apply_migration runs the SQL, then the tracking INSERT, then a single
-- commit), so CREATE INDEX CONCURRENTLY is NOT allowed here — PostgreSQL
-- rejects it inside a transaction block.  This therefore uses a plain
-- CREATE INDEX, which takes a SHARE lock on stratum.notes_sl for the
-- duration of the build and blocks concurrent writes to the table.
-- Accepted trade-off: notes are small user-authored rows, the build is a
-- single pass, and the statement is idempotent (IF NOT EXISTS), so a failed
-- run can simply be retried.  A large-table backfill would instead need an
-- out-of-band CONCURRENTLY build.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_notes_sl_title_body_trgm
    ON stratum.notes_sl USING gin (
        (title || ' ' || COALESCE(content_markdown, '')) gin_trgm_ops
    );
