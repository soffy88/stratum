-- src/stratum/db/migrations/030_graph_relations.sql
CREATE TABLE IF NOT EXISTS graph_relations (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_entity_id VARCHAR NOT NULL,
    target_entity_id VARCHAR NOT NULL,
    relation_type VARCHAR DEFAULT 'related',
    description VARCHAR,
    weight FLOAT DEFAULT 1.0,
    source_substrate_ids JSON DEFAULT '[]',
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_relations_user ON graph_relations(user_id);
CREATE INDEX IF NOT EXISTS idx_graph_relations_source ON graph_relations(user_id, source_entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_relations_target ON graph_relations(user_id, target_entity_id);
