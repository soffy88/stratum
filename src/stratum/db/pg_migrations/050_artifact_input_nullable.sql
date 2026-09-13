-- ArtifactInput is a typed union: exactly one or more reference dimensions
-- may be populated (Source/Fragment/Evidence/Claim/parent artifact).
-- Nullable dimensions are required for parent-artifact-only lineage and are
-- still protected by the writer's owner and reference checks.
ALTER TABLE stratum.artifact_input DROP CONSTRAINT IF EXISTS artifact_input_pkey;
ALTER TABLE stratum.artifact_input ALTER COLUMN source_id DROP NOT NULL;
ALTER TABLE stratum.artifact_input ALTER COLUMN fragment_id DROP NOT NULL;
ALTER TABLE stratum.artifact_input ALTER COLUMN evidence_id DROP NOT NULL;
ALTER TABLE stratum.artifact_input ALTER COLUMN claim_id DROP NOT NULL;
ALTER TABLE stratum.artifact_input ALTER COLUMN artifact_parent_id DROP NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_artifact_input_typed
    ON stratum.artifact_input (
        artifact_id,
        COALESCE(source_id, ''),
        COALESCE(fragment_id, ''),
        COALESCE(evidence_id, ''),
        COALESCE(claim_id, ''),
        COALESCE(artifact_parent_id, '')
    );
