-- 024: reconcile the legacy platform-content highlight target with the
-- canonical stratum.highlights table created by the generated base schema.
-- Migration 007 only created a table when absent, so existing deployments
-- never received content_id after the base table won the name collision.

ALTER TABLE stratum.highlights
    ADD COLUMN IF NOT EXISTS content_id TEXT;

CREATE INDEX IF NOT EXISTS idx_highlights_user_content
    ON stratum.highlights (user_id, content_id)
    WHERE content_id IS NOT NULL;
