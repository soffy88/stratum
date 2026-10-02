-- 021: monthly high-compute usage ledger.
CREATE TABLE IF NOT EXISTS stratum.usage_credits (
    user_id      TEXT NOT NULL,
    period       TEXT NOT NULL,
    credits_used INTEGER NOT NULL DEFAULT 0 CHECK (credits_used >= 0),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period)
);
