-- AII feedback loop 去重表：记录每个 need 的处理历史 + 护栏计数
CREATE TABLE IF NOT EXISTS aii_processed_needs (
    id           VARCHAR   PRIMARY KEY,
    need_hash    VARCHAR   NOT NULL,        -- sha256(topic+reason) 用于去重
    topic        VARCHAR,
    source_type  VARCHAR,
    sub_id       VARCHAR,                   -- 创建的 subscription id（可为空）
    result       VARCHAR   DEFAULT 'ok',   -- 'ok' | 'needs_human_review' | 'skipped' | 'error'
    miss_rounds  INTEGER   DEFAULT 0,      -- 连续找到=0 的轮数（护栏G5）
    notes        VARCHAR,
    processed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aii_needs_hash ON aii_processed_needs(need_hash);
CREATE INDEX IF NOT EXISTS idx_aii_needs_day  ON aii_processed_needs(processed_at);
