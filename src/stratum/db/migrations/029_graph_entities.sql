-- src/stratum/db/migrations/029_graph_entities.sql
CREATE TABLE IF NOT EXISTS graph_entities (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    entity_type VARCHAR DEFAULT 'concept',
    description VARCHAR,
    aliases JSON DEFAULT '[]',
    source_substrate_ids JSON DEFAULT '[]',
    mention_count INTEGER DEFAULT 1,
    embedding_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_graph_entities_user ON graph_entities(user_id);
CREATE INDEX IF NOT EXISTS idx_graph_entities_name ON graph_entities(user_id, name);
