CREATE TABLE IF NOT EXISTS platform_content (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT DEFAULT 'hevi',
    body_markdown TEXT,
    body_html TEXT,
    audio_url TEXT,
    duration_seconds INT,
    published_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    version INT DEFAULT 1,
    domain TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    related_content_ids TEXT[] DEFAULT '{}',
    related_concepts TEXT[] DEFAULT '{}',
    access_tier TEXT NOT NULL DEFAULT 'free',
    deleted_at TIMESTAMP NULL
);

CREATE INDEX IF NOT EXISTS idx_pc_published
    ON platform_content(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_pc_domain
    ON platform_content USING GIN(domain);

CREATE INDEX IF NOT EXISTS idx_pc_search
    ON platform_content
    USING GIN(to_tsvector('simple',
        coalesce(title, '') || ' ' || coalesce(body_markdown, '')
    ));

CREATE TABLE IF NOT EXISTS platform_content_chunk (
    id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL REFERENCES platform_content(id) ON DELETE CASCADE,
    chunk_idx INT NOT NULL,
    text TEXT NOT NULL,
    chunk_meta JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_chunk_content
    ON platform_content_chunk(content_id);

CREATE TABLE IF NOT EXISTS platform_concepts (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    type TEXT NOT NULL,
    definition TEXT,
    hevi_perspective TEXT,
    applicability TEXT,
    common_mistakes TEXT,
    related_concept_ids TEXT[] DEFAULT '{}',
    domain TEXT[] DEFAULT '{}',
    version INT DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_content_interaction (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    content_id TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uci_user_content
    ON user_content_interaction(user_id, content_id);

CREATE INDEX IF NOT EXISTS idx_uci_type
    ON user_content_interaction(interaction_type);
