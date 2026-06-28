-- AII-PMS-SCHEMA-001
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS aii;

-- 1. KU Table
CREATE TABLE IF NOT EXISTS aii.ku (
    ku_id UUID PRIMARY KEY,
    project_id TEXT NOT NULL DEFAULT 'default',
    natural_text TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,
    symbolic_form JSONB,
    embedding VECTOR(1024),
    grade TEXT NOT NULL DEFAULT 'unverified',
    source TEXT,
    verified BOOLEAN DEFAULT FALSE,
    is_quarantined BOOLEAN DEFAULT FALSE,
    valid_from TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMPTZ,
    superseded_by UUID REFERENCES aii.ku(ku_id),
    provenance JSONB,
    fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ku_fingerprint ON aii.ku(fingerprint) WHERE (is_quarantined IS FALSE);
CREATE INDEX IF NOT EXISTS idx_ku_embedding ON aii.ku USING hnsw (embedding vector_cosine_ops);

-- 2. KU Candidate Table (Temporary storage for extraction)
CREATE TABLE IF NOT EXISTS aii.ku_candidate (
    candidate_id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    natural_text TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,
    payload JSONB,
    source_doc_id TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. KU Defeater Table (Counter-evidence)
CREATE TABLE IF NOT EXISTS aii.ku_defeater (
    defeater_id UUID PRIMARY KEY,
    subject_ku_id UUID REFERENCES aii.ku(ku_id),
    defeater_text TEXT NOT NULL,
    strength FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Edge Table (Relationships)
CREATE TABLE IF NOT EXISTS aii.edge (
    src_id UUID NOT NULL,
    relation TEXT NOT NULL,
    dst_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (src_id, relation, dst_id)
);

-- 5. KU State History (Audit Log)
CREATE TABLE IF NOT EXISTS aii.ku_state_history (
    id BIGSERIAL PRIMARY KEY,
    ku_id UUID NOT NULL REFERENCES aii.ku(ku_id),
    from_grade TEXT,
    to_grade TEXT NOT NULL,
    trigger TEXT,
    decision_trail JSONB,
    at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Episode Table (Events/Logs)
CREATE TABLE IF NOT EXISTS aii.episode (
    episode_id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. Solution Strategy Table
CREATE TABLE IF NOT EXISTS aii.solution_strategy (
    strategy_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    steps JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
