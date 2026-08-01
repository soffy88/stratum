-- 康奈尔笔记：机器从 B仓 refined_ku 自动生成 + 人类笔记共存
-- source=machine 对所有登录用户可见; source=human 仅本人
CREATE TABLE IF NOT EXISTS cornell_notes (
    id                VARCHAR PRIMARY KEY,
    topic_id          VARCHAR NOT NULL,
    title             VARCHAR NOT NULL,
    subject           VARCHAR,
    source            VARCHAR NOT NULL DEFAULT 'machine',  -- machine | human
    refined_ku_ids    JSONB NOT NULL DEFAULT '[]'::jsonb,
    refined_concept_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    content           JSONB NOT NULL,  -- {version,cues,modules,summary,oneLiner,...}
    user_id           VARCHAR,         -- null=系统/共享机器笔记
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cornell_topic_source_user
  ON cornell_notes (topic_id, source, COALESCE(user_id, ''));

CREATE INDEX IF NOT EXISTS idx_cornell_source_alive
  ON cornell_notes (source, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_cornell_user_alive
  ON cornell_notes (user_id, updated_at DESC)
  WHERE deleted_at IS NULL AND user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cornell_subject
  ON cornell_notes (subject)
  WHERE deleted_at IS NULL;
