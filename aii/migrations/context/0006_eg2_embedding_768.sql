-- 0006: EmbeddingGemma2 (768-d) parallel columns for the C仓 (aii_context).
-- See src/stratum/db/pg_migrations/087 for the scheme.
ALTER TABLE cx.decision_case ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE cx.lesson_pattern ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE cx.methodology ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
CREATE TABLE IF NOT EXISTS public.eg2_backfill_ledger (
    tbl TEXT NOT NULL, pk TEXT NOT NULL, text_md5 TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (tbl, pk));
