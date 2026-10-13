-- 0006: EmbeddingGemma2 (768-d) parallel columns for the B仓 (aii_refined).
-- Same scheme as src/stratum/db/pg_migrations/087: add nullable 768-d columns
-- next to the legacy BGE-M3 vector(1024) ones; scripts/eg2_backfill_refined.py
-- fills them; the cutover (0007) swaps names; old columns are dropped later.
ALTER TABLE rf.refined_ku ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE rf.refined_concept ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE rf.refined_hyperedge ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE rf.refined_theme_kc ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE rf.refined_cross_domain_relation ADD COLUMN IF NOT EXISTS embedding_768 vector(768);
ALTER TABLE rf.refined_invariant ADD COLUMN IF NOT EXISTS invariant_vector_768 vector(768);
CREATE TABLE IF NOT EXISTS public.eg2_backfill_ledger (
    tbl TEXT NOT NULL, pk TEXT NOT NULL, text_md5 TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (tbl, pk));
