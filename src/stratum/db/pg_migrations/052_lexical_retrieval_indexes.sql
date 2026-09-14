-- Native lexical retrieval projections.
--
-- Retrieval must never materialise the canonical corpus just to score text in
-- Python.  pg_trgm gives PostgreSQL an indexable operator for both Latin and
-- CJK substring terms; the query layer computes the small match score in SQL.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_substrate_chunk_text_trgm
    ON stratum.substrate_chunk USING gin (text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_substrates_title_trgm
    ON stratum.substrates USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_substrates_source_path_trgm
    ON stratum.substrates USING gin (source_path gin_trgm_ops);

DO $$
BEGIN
    IF to_regclass('stratum.substrate_layers') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS idx_substrate_layers_content_trgm
            ON stratum.substrate_layers USING gin (content gin_trgm_ops);
    END IF;
END $$;
