-- 089: EmbeddingGemma2 (768-d) cutover for aii_kg (aii.* + stratum.*).
--
-- Swaps the parallel columns filled by scripts/eg2_backfill.py into the
-- canonical names the readers/writers use (`embedding` / `vector`).
-- stratum.multimodal_assets is NOT cut over: its vectors come from the
-- multimodal extractor's own embedder (0 rows today); 090 drops its unused
-- embedding_768 column.
--
-- Idempotent: per table it acts only when the `<col>_768` column exists AND the
-- live `<col>` is still vector(1024); a re-run (or a DB already cut over, or a
-- bare CI DB without these tables) is a no-op.  Legacy indexes on the 1024-d
-- column get a `_bge1024` suffix; the frozen column is kept as `<col>_bge1024`
-- until the cleanup migration drops it.  Run with the writers stopped.
--
-- ── Manual rollback (before the cleanup migration has run) ──────────────────
--   BEGIN;
--   -- per table, e.g. aii.ku_onto:
--   ALTER TABLE aii.ku_onto RENAME COLUMN embedding TO embedding_768;
--   ALTER TABLE aii.ku_onto RENAME COLUMN embedding_bge1024 TO embedding;
--   -- optional: ALTER INDEX <legacy_idx>_bge1024 RENAME TO <legacy_idx>;
--   COMMIT;
--   then set AII_EMBED_BACKEND=bge on the services and restart them.
--   (tenant_ann_vectors: renaming the parent column renames it in every partition.)
DO $$
DECLARE
    t        record;
    r        record;
    rel      regclass;
    old_type text;
    idx_name text;
    has_new_idx boolean;
    gaps     bigint;
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
        -- guard 1: the 768-d column created by the parallel-column migration exists
        CONTINUE WHEN NOT EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = rel AND attname = t.col || '_768' AND NOT attisdropped);
        -- guard 2: the live column is still the legacy vector(1024) (else: already cut over)
        SELECT format_type(atttypid, atttypmod) INTO old_type
        FROM pg_attribute WHERE attrelid = rel AND attname = t.col AND NOT attisdropped;
        CONTINUE WHEN old_type IS DISTINCT FROM 'vector(1024)';
        -- interlock: refuse to cut over while the backfill still has gaps (rows
        -- with a legacy vector but no 768-d vector).  Override deliberately with
        -- CREATE TABLE public.eg2_cutover_allow_gaps();
        EXECUTE format('SELECT count(*) FROM %I.%I WHERE %I IS NOT NULL AND %I IS NULL',
                       t.sch, t.tbl, t.col, t.col || '_768') INTO gaps;
        IF gaps > 0 AND to_regclass('public.eg2_cutover_allow_gaps') IS NULL THEN
            RAISE EXCEPTION 'eg2 cutover refused: %.% has % rows without a 768-d vector (run the backfill catch-up first)',
                t.sch, t.tbl, gaps;
        END IF;

        -- 1) legacy indexes on the 1024-d column (table + partitions) → *_bge1024
        FOR r IN
            SELECT ic.oid AS idx_oid, ic.relname AS idx, n.nspname AS nsp
            FROM pg_index i
            JOIN pg_class ic ON ic.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = ic.relnamespace
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attname = t.col
                               AND a.attnum = ANY (i.indkey::int2[])
            WHERE i.indrelid = rel
               OR i.indrelid IN (SELECT inhrelid FROM pg_inherits WHERE inhparent = rel)
        LOOP
            CONTINUE WHEN r.idx LIKE '%\_bge1024';
            EXECUTE format('ALTER INDEX %I.%I RENAME TO %I',
                           r.nsp, r.idx, left(r.idx, 55) || '_bge1024');
        END LOOP;

        -- 2) swap the columns (partitions follow the parent automatically)
        EXECUTE format('ALTER TABLE %I.%I RENAME COLUMN %I TO %I',
                       t.sch, t.tbl, t.col, t.col || '_bge1024');
        EXECUTE format('ALTER TABLE %I.%I RENAME COLUMN %I TO %I',
                       t.sch, t.tbl, t.col || '_768', t.col);

        -- 3) make sure the now-canonical 768-d column has an HNSW cosine index
        --    (aii_kg: built ahead of time by 088; B/C 仓: built here).
        --    Partitioned parents are skipped: their partitions carry the index.
        CONTINUE WHEN (SELECT relkind FROM pg_class WHERE oid = rel) = 'p';
        SELECT EXISTS (
            SELECT 1 FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attname = t.col
                               AND a.attnum = ANY (i.indkey::int2[])
            WHERE i.indrelid = rel) INTO has_new_idx;
        IF NOT has_new_idx THEN
            idx_name := left(format('idx_%s_%s', t.tbl, t.col), 59) || '_eg2';
            EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I.%I USING hnsw (%I vector_cosine_ops) '
                           'WITH (m = 16, ef_construction = 64)', idx_name, t.sch, t.tbl, t.col);
        END IF;
    END LOOP;
END $$;
