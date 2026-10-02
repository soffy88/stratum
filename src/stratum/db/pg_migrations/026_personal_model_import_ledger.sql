-- 026: auditable cross-database import ledger for the Personal Model.
-- The ledger is intentionally separate from the canonical objects: a dry-run
-- may record candidates without claiming that a user/object mapping is valid.

CREATE TABLE IF NOT EXISTS stratum.personal_model_import_ledger (
    id                   TEXT PRIMARY KEY,
    batch_id             TEXT NOT NULL,
    source_database      TEXT NOT NULL,
    source_table         TEXT NOT NULL,
    source_id            TEXT NOT NULL,
    target_table         TEXT NOT NULL,
    target_id            TEXT,
    user_id              TEXT,
    status               TEXT NOT NULL CHECK (
        status IN ('candidate', 'applied', 'skipped_conflict', 'blocked', 'rolled_back', 'rollback_blocked')
    ),
    payload_hash         TEXT NOT NULL,
    payload_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason               TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, source_database, source_table, source_id, target_table)
);

CREATE INDEX IF NOT EXISTS idx_personal_model_import_batch
    ON stratum.personal_model_import_ledger(batch_id, status);
CREATE INDEX IF NOT EXISTS idx_personal_model_import_source
    ON stratum.personal_model_import_ledger(source_database, source_table, source_id);
CREATE INDEX IF NOT EXISTS idx_personal_model_import_user
    ON stratum.personal_model_import_ledger(user_id, created_at DESC)
    WHERE user_id IS NOT NULL;

-- Ledger rows are never physically deleted. Rollback is represented by a
-- status transition so the original candidate/application decision remains.
CREATE OR REPLACE FUNCTION stratum.reject_personal_model_import_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'stratum.personal_model_import_ledger is append-only; use rolled_back status';
    END IF;
    IF NEW.id <> OLD.id
       OR NEW.batch_id <> OLD.batch_id
       OR NEW.source_database <> OLD.source_database
       OR NEW.source_table <> OLD.source_table
       OR NEW.source_id <> OLD.source_id
       OR NEW.target_table <> OLD.target_table
       OR NEW.target_id IS DISTINCT FROM OLD.target_id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.payload_hash <> OLD.payload_hash
       OR NEW.payload_json <> OLD.payload_json
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'personal model import identity/payload is immutable';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS personal_model_import_ledger_append_only
    ON stratum.personal_model_import_ledger;
CREATE TRIGGER personal_model_import_ledger_append_only
    BEFORE UPDATE OR DELETE ON stratum.personal_model_import_ledger
    FOR EACH ROW EXECUTE FUNCTION stratum.reject_personal_model_import_delete();
