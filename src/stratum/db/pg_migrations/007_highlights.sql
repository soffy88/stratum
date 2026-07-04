CREATE TABLE IF NOT EXISTS highlights (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    content_id TEXT,
    substrate_id TEXT,
    anchor JSONB NOT NULL,
    color TEXT DEFAULT 'yellow',
    note TEXT,
    status TEXT DEFAULT 'active',
    status_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT hl_target_check CHECK (
        content_id IS NOT NULL OR substrate_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_hl_user ON highlights(user_id);

CREATE INDEX IF NOT EXISTS idx_hl_substrate
    ON highlights(substrate_id) WHERE substrate_id IS NOT NULL;
