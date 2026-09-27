-- 023: append-only cross-object learning event ledger.
-- The old cx.learning_progress.attempts JSONB remains readable for legacy AII
-- flows; new Stratum interactions use this event-level audit surface.

CREATE TABLE IF NOT EXISTS stratum.learning_events (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    object_type  TEXT NOT NULL,
    object_id    TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    result       JSONB NOT NULL DEFAULT '{}'::jsonb,
    source       TEXT NOT NULL DEFAULT 'api',
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_events_user_time
    ON stratum.learning_events (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_events_object_time
    ON stratum.learning_events (object_type, object_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_events_type_time
    ON stratum.learning_events (user_id, event_type, occurred_at DESC);

-- Keep the ledger append-only even for accidental direct SQL writes.  The
-- service exposes only INSERT/SELECT; this trigger makes that contract
-- enforceable at the database boundary as well.
CREATE OR REPLACE FUNCTION stratum.reject_learning_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'stratum.learning_events is append-only';
END;
$$;

DROP TRIGGER IF EXISTS learning_events_append_only ON stratum.learning_events;
CREATE TRIGGER learning_events_append_only
    BEFORE UPDATE OR DELETE ON stratum.learning_events
    FOR EACH ROW EXECUTE FUNCTION stratum.reject_learning_event_mutation();
