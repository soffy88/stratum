-- 088: HNSW cosine indexes for the EmbeddingGemma2 768-d columns added in 087.
-- Built after the backfill (bulk HNSW build is far cheaper than incremental).
-- Not partial: readers use plain `ORDER BY col <=> $1`, which a partial index
-- (WHERE col IS NOT NULL) would not serve; HNSW skips NULLs anyway.
DO $$
DECLARE
    t record;
    p record;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('aii', 'ku_onto', 'embedding_768', 'idx_ku_onto_embedding_768'),
            ('aii', 'bu_onto', 'embedding_768', 'idx_bu_onto_embedding_768'),
            ('aii', 'kc_onto', 'embedding_768', 'idx_kc_onto_embedding_768'),
            ('aii', 'concept_onto', 'vector_768', 'idx_concept_onto_vector_768'),
            ('aii', 'invariant', 'vector_768', 'idx_invariant_vector_768'),
            ('aii', 'hyperedge', 'embedding_768', 'idx_hyperedge_embedding_768'),
            ('aii', 'platform_content_chunk', 'embedding_768', 'idx_aii_chunk_embedding_768'),
            ('stratum', 'ku_layers', 'embedding_768', 'idx_ku_layers_embedding_768'),
            ('stratum', 'substrate_layers', 'embedding_768', 'idx_substrate_layers_embedding_768'),
            ('stratum', 'substrate_chunk', 'embedding_768', 'idx_substrate_chunk_embedding_768'),
            ('stratum', 'graph_entities', 'embedding_768', 'idx_graph_entities_embedding_768'),
            ('stratum', 'multimodal_assets', 'embedding_768', 'idx_multimodal_embedding_768'),
            ('stratum', 'platform_content_chunk', 'embedding_768', 'idx_chunk_embedding_768')
        ) AS v(sch, tbl, col, idx)
    LOOP
        IF to_regclass(format('%I.%I', t.sch, t.tbl)) IS NOT NULL THEN
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON %I.%I USING hnsw (%I vector_cosine_ops) '
                'WITH (m = 16, ef_construction = 64)',
                t.idx, t.sch, t.tbl, t.col);
        END IF;
    END LOOP;

    -- tenant_ann_vectors is list-partitioned per tenant; index each partition
    -- the same way the legacy projection does.
    IF to_regclass('stratum.tenant_ann_vectors') IS NOT NULL THEN
        FOR p IN
            SELECT c.relname FROM pg_inherits i
            JOIN pg_class c ON c.oid = i.inhrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE i.inhparent = 'stratum.tenant_ann_vectors'::regclass AND n.nspname = 'stratum'
        LOOP
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON stratum.%I USING hnsw (embedding_768 vector_cosine_ops) '
                'WITH (m = 16, ef_construction = 64)',
                p.relname || '_hnsw768', p.relname);
        END LOOP;
    END IF;
END $$;
