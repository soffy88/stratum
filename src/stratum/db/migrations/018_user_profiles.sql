-- 018_user_profiles.sql

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id         VARCHAR PRIMARY KEY,
    display_name    VARCHAR,
    avatar_url      VARCHAR,
    bio             VARCHAR,
    location        VARCHAR,
    website         VARCHAR,
    timezone        VARCHAR DEFAULT 'Asia/Shanghai',
    locale          VARCHAR DEFAULT 'zh-CN',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
