-- 090: drop the frozen BGE-M3 vector(1024) columns left by 089 (aii_kg).
--
-- Run ONLY after the cutover is verified (services on AII_EMBED_BACKEND=eg2,
-- search/health smoke-tested).  Irreversible: the BGE-M3 vectors are gone.
-- Guarded per table: acts only when the live column is already vector(768);
-- missing tables are skipped.  Follow with VACUUM (ANALYZE) of the tables.
DO $$
DECLARE
    t   record;
    rel regclass;
    has_data boolean;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('aii', 'ku_onto', 'embedding'),
            ('aii', 'bu_onto', 'embedding'),
            ('aii', 'kc_onto', 'embedding'),
            ('aii', 'concept_onto', 'vector'),
            ('aii', 'invariant', 'vector'),
            ('aii', 'hyperedge', 'embedding'),
            ('aii', 'platform_content_chunk', 'embedding'),
            ('stratum', 'ku_layers', 'embedding'),
            ('stratum', 'substrate_layers', 'embedding'),
            ('stratum', 'substrate_chunk', 'embedding'),
            ('stratum', 'tenant_ann_vectors', 'embedding'),
            ('stratum', 'graph_entities', 'embedding'),
            ('stratum', 'platform_content_chunk', 'embedding')
        ) AS v(sch, tbl, col)
    LOOP
        rel := to_regclass(format('%I.%I', t.sch, t.tbl));
        CONTINUE WHEN rel IS NULL;
        -- only after the cutover: the live column must already be the 768-d one
        CONTINUE WHEN (SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                       WHERE attrelid = rel AND attname = t.col AND NOT attisdropped)
                      IS DISTINCT FROM 'vector(768)';
        CONTINUE WHEN NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = rel
                                  AND attname = t.col || '_bge1024' AND NOT attisdropped);
        -- interlock: with real data in the frozen column, only drop after the
        -- operator recorded the verified cutover:
        --   CREATE TABLE public.eg2_cutover_verified(at timestamptz DEFAULT now());
        IF to_regclass('public.eg2_cutover_verified') IS NULL THEN
            EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I WHERE %I IS NOT NULL)',
                           t.sch, t.tbl, t.col || '_bge1024') INTO has_data;
            IF has_data THEN
                RAISE EXCEPTION 'refusing to drop %.%_bge1024: cutover not marked verified (public.eg2_cutover_verified missing)',
                    t.tbl, t.col;
            END IF;
        END IF;
        -- drops the column and every index on it
        EXECUTE format('ALTER TABLE %I.%I DROP COLUMN IF EXISTS %I',
                       t.sch, t.tbl, t.col || '_bge1024');
    END LOOP;
    -- stratum.multimodal_assets was not cut over (kept on its own embedder): drop its unused 768 column
    IF to_regclass('stratum.multimodal_assets') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE stratum.multimodal_assets DROP COLUMN IF EXISTS embedding_768';
    END IF;
END $$;

DROP TABLE IF EXISTS public.eg2_backfill_ledger;
DROP TABLE IF EXISTS public.eg2_cutover_allow_gaps;
