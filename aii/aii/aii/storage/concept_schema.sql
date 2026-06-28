-- concept_schema.sql — concept + ku_concept tables (Pipeline concept index)
-- 红线: concept 是 KU 零件索引, 不带 grade, 不当知识, 不做 concept 间关系图
-- Run once:
--   docker exec aii-postgres psql -U aii -d aii_kg -f /path/to/concept_schema.sql

CREATE TABLE IF NOT EXISTS aii.concept (
    concept_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text        UNIQUE NOT NULL,
    ku_count   int         NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS aii.ku_concept (
    ku_id      uuid NOT NULL REFERENCES aii.ku(ku_id)          ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES aii.concept(concept_id) ON DELETE CASCADE,
    PRIMARY KEY (ku_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_ku_concept_concept ON aii.ku_concept(concept_id);
