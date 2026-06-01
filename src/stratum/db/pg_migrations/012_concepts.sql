CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'concept_idea',
    aliases TEXT[] DEFAULT '{}',
    wikilink TEXT,
    substrate_refs TEXT[] DEFAULT '{}',
    related_concept_ids TEXT[] DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts(user_id, name);
