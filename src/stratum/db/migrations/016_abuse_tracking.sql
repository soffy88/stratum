-- 016_abuse_tracking.sql
-- Abuse detection: blocked IPs + auth event log

CREATE TABLE IF NOT EXISTS blocked_ips (
    ip_address      VARCHAR PRIMARY KEY,
    reason          VARCHAR NOT NULL,
    blocked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP NOT NULL,
    blocked_count   INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_blocked_ips_expires ON blocked_ips(expires_at);

CREATE TABLE IF NOT EXISTS auth_events (
    id              VARCHAR PRIMARY KEY,
    event_type      VARCHAR NOT NULL,
    ip_address      VARCHAR NOT NULL,
    user_id         VARCHAR,
    user_agent      VARCHAR,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_json       VARCHAR DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_auth_events_ip ON auth_events(ip_address, created_at);
CREATE INDEX IF NOT EXISTS idx_auth_events_user ON auth_events(user_id, created_at);
