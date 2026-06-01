CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    content_id TEXT NOT NULL,
    score FLOAT NOT NULL DEFAULT 0.0,
    reason TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rec_user
    ON recommendations(user_id, created_at DESC);
