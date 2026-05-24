CREATE TABLE IF NOT EXISTS sessions (
    id              VARCHAR PRIMARY KEY,
    user_id         VARCHAR NOT NULL,
    refresh_token_hash VARCHAR UNIQUE NOT NULL,
    user_agent      VARCHAR,
    ip_address      VARCHAR,
    expires_at      TIMESTAMP NOT NULL,
    revoked_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE UNIQUE INDEX idx_sessions_refresh_hash ON sessions(refresh_token_hash);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
