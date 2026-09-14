CREATE SEQUENCE IF NOT EXISTS stratum.changefeed_seq;

CREATE TABLE IF NOT EXISTS stratum.changefeed (
    seq BIGINT PRIMARY KEY DEFAULT nextval('stratum.changefeed_seq'),
    event_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL DEFAULT 'server',
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    processed BOOLEAN DEFAULT FALSE
);

ALTER TABLE stratum.changefeed
    ALTER COLUMN timestamp SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_cf_user_seq ON changefeed(user_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_cf_type ON changefeed(event_type);
