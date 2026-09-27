-- 027: reviewable merge ledger for legacy Concept/Relation convergence.
-- No legacy row is merged by this migration.  The planner emits candidates;
-- a human approval manifest is required before any canonical write.

CREATE TABLE IF NOT EXISTS stratum.legacy_knowledge_merge_ledger (
    id                   TEXT PRIMARY KEY,
    batch_id             TEXT NOT NULL,
    source_kind          TEXT NOT NULL CHECK (source_kind IN ('concept', 'relation')),
    source_table         TEXT NOT NULL,
    source_id            TEXT NOT NULL,
    candidate_group_id   TEXT NOT NULL,
    target_table         TEXT NOT NULL CHECK (target_table IN ('stratum.concepts', 'stratum.concept_relations')),
    target_id            TEXT,
    user_id              TEXT,
    status               TEXT NOT NULL CHECK (
        status IN ('candidate', 'approved', 'applied', 'skipped_conflict', 'blocked', 'rolled_back', 'rollback_blocked')
    ),
    payload_hash         TEXT NOT NULL,
    payload_json         JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason               TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (batch_id, source_kind, source_table, source_id)
);

CREATE INDEX IF NOT EXISTS idx_legacy_merge_batch
    ON stratum.legacy_knowledge_merge_ledger(batch_id, status, source_kind);
CREATE INDEX IF NOT EXISTS idx_legacy_merge_group
    ON stratum.legacy_knowledge_merge_ledger(candidate_group_id);
CREATE INDEX IF NOT EXISTS idx_legacy_merge_source
    ON stratum.legacy_knowledge_merge_ledger(source_table, source_id);

CREATE OR REPLACE FUNCTION stratum.reject_legacy_knowledge_merge_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'legacy knowledge merge ledger is append-only';
    END IF;
    IF NEW.id <> OLD.id
       OR NEW.batch_id <> OLD.batch_id
       OR NEW.source_kind <> OLD.source_kind
       OR NEW.source_table <> OLD.source_table
       OR NEW.source_id <> OLD.source_id
       OR NEW.candidate_group_id <> OLD.candidate_group_id
       OR NEW.target_table <> OLD.target_table
       OR NEW.target_id IS DISTINCT FROM OLD.target_id
       OR NEW.user_id IS DISTINCT FROM OLD.user_id
       OR NEW.payload_hash <> OLD.payload_hash
       OR NEW.payload_json <> OLD.payload_json
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'legacy knowledge merge identity/payload is immutable';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS legacy_knowledge_merge_append_only
    ON stratum.legacy_knowledge_merge_ledger;
CREATE TRIGGER legacy_knowledge_merge_append_only
    BEFORE UPDATE OR DELETE ON stratum.legacy_knowledge_merge_ledger
    FOR EACH ROW EXECUTE FUNCTION stratum.reject_legacy_knowledge_merge_mutation();
