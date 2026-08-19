-- 015: flashcards (闪卡 + 间隔复习)
CREATE TABLE IF NOT EXISTS stratum.flashcards (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    source_kind   TEXT NOT NULL DEFAULT 'substrate',   -- substrate | note
    source_id     TEXT NOT NULL,
    source_title  TEXT,
    front         TEXT NOT NULL,
    back          TEXT NOT NULL,
    tags          TEXT[] NOT NULL DEFAULT '{}',
    -- SRS 状态 (SM-2)
    repetitions   INTEGER NOT NULL DEFAULT 0,
    easiness      DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days DOUBLE PRECISION NOT NULL DEFAULT 0,
    due_at        TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_flashcards_user_due
    ON stratum.flashcards (user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_flashcards_user_source
    ON stratum.flashcards (user_id, source_id);
