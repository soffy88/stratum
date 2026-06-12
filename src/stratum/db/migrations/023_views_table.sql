-- Saved Views: user-defined filter+sort+display combos.
-- NOTE: DuckDB reserves the name "views" → table named "user_saved_views"

CREATE TABLE IF NOT EXISTS user_saved_views (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR NOT NULL,
    name         VARCHAR NOT NULL,
    description  VARCHAR,
    is_preset    BOOLEAN DEFAULT FALSE,
    icon         VARCHAR,
    filter_json  JSON DEFAULT '{}',
    sort_by      VARCHAR DEFAULT 'created_at',
    sort_order   VARCHAR DEFAULT 'desc',
    display_mode VARCHAR DEFAULT 'list',
    position     INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_views_user ON user_saved_views(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_views_pos ON user_saved_views(user_id, position);
