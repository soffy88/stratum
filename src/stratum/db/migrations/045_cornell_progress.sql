-- 康奈尔学习进度(云端同步, 与 localStorage 并集合并)
CREATE TABLE IF NOT EXISTS cornell_progress (
    user_id     VARCHAR NOT NULL,
    topic_id    VARCHAR NOT NULL,
    note_id     VARCHAR,
    state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- state: {version, mastered, collapsed, selfTest, showAnswers, updatedAt, drills?}
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_cornell_progress_user
  ON cornell_progress (user_id, updated_at DESC);
