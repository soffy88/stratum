-- 071: A Repository P2 — Evidence Quality + KU Candidate Classification
--
-- Rules respected: additive only; never edits migrations 060-066 or 070.
-- All statements are IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, safe to re-run.
--
-- A仓 scope: evidence quality control + candidate classification.
--   Quality rows are scored from the evidence's own locator and span.
--   Classification assigns a type; it compares no two candidates.
--   No conclusion about the world is stored here.
--   Original evidence is never replaced or rewritten.
--
-- Object model (extended):
--   ReadingEvidence 1---1 EvidenceQuality
--   ReadingEvidence 1---N KUCandidate (classification metadata only)

-- ── 1. evidence_quality ────────────────────────────────────────────────────
-- Append-only quality record. One row per evidence row.
-- evidence_id UNIQUE enforces exactly-once scoring: re-running the
-- quality stage is idempotent at the schema level, and correcting a
-- score requires a new quality_version rather than an UPDATE.
CREATE TABLE IF NOT EXISTS stratum.evidence_quality (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL UNIQUE
        REFERENCES stratum.reading_evidence(id) ON DELETE CASCADE,
    source_trace_score FLOAT NOT NULL
        CHECK (source_trace_score >= 0.0 AND source_trace_score <= 1.0),
    locator_score FLOAT NOT NULL
        CHECK (locator_score >= 0.0 AND locator_score <= 1.0),
    completeness_score FLOAT NOT NULL
        CHECK (completeness_score >= 0.0 AND completeness_score <= 1.0),
    confidence_score FLOAT NOT NULL
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    quality_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_quality_evidence
    ON stratum.evidence_quality(evidence_id);

CREATE INDEX IF NOT EXISTS idx_evidence_quality_version
    ON stratum.evidence_quality(quality_version);

-- ── 2. ku_candidate classification metadata (additive extension) ──────────
-- Classification ONLY. Assigns a type; merges nothing, compares nothing.
ALTER TABLE stratum.ku_candidate
    ADD COLUMN IF NOT EXISTS classification TEXT
        CHECK (classification IS NULL OR classification IN (
            'FACT', 'EVENT', 'CONCEPT', 'RELATION', 'ARGUMENT'
        ));

ALTER TABLE stratum.ku_candidate
    ADD COLUMN IF NOT EXISTS classified_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_ku_candidate_classification
    ON stratum.ku_candidate(classification);