-- src/stratum/db/migrations/035_channel_subscriptions.sql
CREATE TABLE IF NOT EXISTS channel_subscriptions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    channel_url VARCHAR NOT NULL,
    channel_title VARCHAR,
    rules_json JSON DEFAULT '{}',         -- FilterRules
    status VARCHAR DEFAULT 'active',      -- active | paused
    last_check TIMESTAMP,
    scan_status VARCHAR DEFAULT 'idle',   -- idle | scanning | completed | error
    found_count INTEGER DEFAULT 0,
    ingested_count INTEGER DEFAULT 0,
    current_video VARCHAR DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS channel_processed_videos (
    subscription_id VARCHAR NOT NULL,
    video_id VARCHAR NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (subscription_id, video_id)
);
