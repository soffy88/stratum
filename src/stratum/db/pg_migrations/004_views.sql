CREATE TABLE IF NOT EXISTS views (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    default_filter JSONB DEFAULT '{}',
    default_llm JSONB DEFAULT '{}',
    default_system_prompt TEXT,
    default_agents JSONB DEFAULT '[]',
    icon TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_views_user ON views(user_id);
