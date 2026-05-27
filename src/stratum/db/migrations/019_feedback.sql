-- 019_feedback.sql

CREATE TABLE IF NOT EXISTS feedback (
    id          VARCHAR PRIMARY KEY,
    user_id     VARCHAR NOT NULL,
    content     VARCHAR NOT NULL,
    page_url    VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);
