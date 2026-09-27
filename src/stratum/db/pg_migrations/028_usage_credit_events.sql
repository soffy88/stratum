-- 028: idempotent usage events for retry-safe credit charging.
-- The aggregate usage_credits row remains the fast allowance counter; this
-- event table prevents the same user operation from charging twice on retry.
CREATE TABLE IF NOT EXISTS stratum.usage_credit_events (
    idempotency_key TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    period          TEXT NOT NULL,
    capability      TEXT NOT NULL,
    units           INTEGER NOT NULL CHECK (units > 0),
    credits         INTEGER NOT NULL CHECK (credits > 0),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'charged', 'denied')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_usage_credit_events_user_period
    ON stratum.usage_credit_events (user_id, period, created_at DESC);

CREATE OR REPLACE FUNCTION stratum.reject_usage_credit_event_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'pending' THEN
            RAISE EXCEPTION 'new stratum.usage_credit_events must start as pending';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE'
       OR OLD.user_id <> NEW.user_id
       OR OLD.idempotency_key <> NEW.idempotency_key
       OR OLD.period <> NEW.period
       OR OLD.capability <> NEW.capability
       OR OLD.units <> NEW.units
       OR OLD.credits <> NEW.credits
       OR OLD.status <> 'pending'
       OR NEW.status NOT IN ('charged', 'denied') THEN
        RAISE EXCEPTION 'stratum.usage_credit_events is immutable after terminal transition';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS usage_credit_events_append_only ON stratum.usage_credit_events;
CREATE TRIGGER usage_credit_events_append_only
    BEFORE INSERT OR UPDATE OR DELETE ON stratum.usage_credit_events
    FOR EACH ROW EXECUTE FUNCTION stratum.reject_usage_credit_event_mutation();
