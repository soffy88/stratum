-- 087: EmbeddingGemma2 (768-d) parallel embedding columns.
--
-- AII is unifying on the shared EmbeddingGemma2 service (768-d, Matryoshka).
-- This migration only ADDs nullable columns next to the legacy BGE-M3
-- vector(1024) columns, so it is safe to apply while the old vectors are live:
-- no rewrite, no lock beyond a brief ACCESS EXCLUSIVE for the catalog change.
-- scripts/eg2_backfill.py fills the new columns; 088 builds their indexes and
-- the cutover migration later swaps names.  Tables that do not exist in a
-- given deployment (e.g. the aii.* schema in a bare CI database) are skipped.
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('aii', 'ku_onto', 'embedding_768'),
            ('aii', 'bu_onto', 'embedding_768'),
            ('aii', 'kc_onto', 'embedding_768'),
            ('aii', 'concept_onto', 'vector_768'),
            ('aii', 'invariant', 'vector_768'),
            ('aii', 'hyperedge', 'embedding_768'),
            ('aii', 'platform_content_chunk', 'embedding_768'),
            ('stratum', 'ku_layers', 'embedding_768'),
            ('stratum', 'substrate_layers', 'embedding_768'),
            ('stratum', 'substrate_chunk', 'embedding_768'),
            ('stratum', 'tenant_ann_vectors', 'embedding_768'),
            ('stratum', 'graph_entities', 'embedding_768'),
            ('stratum', 'multimodal_assets', 'embedding_768'),
            ('stratum', 'platform_content_chunk', 'embedding_768')
        ) AS v(sch, tbl, col)
    LOOP
        IF to_regclass(format('%I.%I', t.sch, t.tbl)) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS %I vector(768)',
                           t.sch, t.tbl, t.col);
        END IF;
    END LOOP;
END $$;

-- Backfill bookkeeping: which source text each 768-d vector was computed from.
-- Lets the backfill resume, skip unchanged rows and re-embed rows whose text
-- changed (or were inserted by the legacy writer) since the last pass.
-- Dropped together with the legacy columns once the cutover is verified.
CREATE TABLE IF NOT EXISTS public.eg2_backfill_ledger (
    tbl        TEXT NOT NULL,
    pk         TEXT NOT NULL,
    text_md5   TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tbl, pk)
);
