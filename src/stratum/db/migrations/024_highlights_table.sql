-- 024_highlights_table.sql
-- Destructive upgrade: Drop Phase 15 highlights table from 020 to use Phase 17.12 version.

DROP TABLE IF EXISTS highlights;

CREATE TABLE highlights (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    substrate_id VARCHAR NOT NULL,
    color VARCHAR DEFAULT 'yellow',
    text VARCHAR NOT NULL,           -- 高亮原文
    note VARCHAR,                    -- 用户笔记
    location_json JSON DEFAULT '{}', -- 位置信息（页码/偏移）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_highlights_user ON highlights(user_id);
CREATE INDEX idx_highlights_substrate ON highlights(substrate_id);
