CREATE TABLE IF NOT EXISTS changefeed (
    seq BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL,
    device_id TEXT NOT NULL DEFAULT 'server',
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_cf_user_seq ON changefeed(user_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_cf_type ON changefeed(event_type);
