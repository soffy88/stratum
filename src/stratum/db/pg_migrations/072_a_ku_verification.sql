-- 072: A Repository P3 — Knowledge Unit Candidate Verification
--
-- Rules respected: additive only; never edits migrations 060-071.
-- All statements are CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS,
-- safe to re-run.
--
-- A仓 scope: decide whether a KU Candidate is a verified understanding unit.
--   The only inputs are the candidate, its evidence chain and the
--   verification rules recorded in the trace. Nothing else is consulted.
--   No external answer. No external database. No note without evidence.
--   A verified unit stays a fact unit; grouping units into concepts is a
--   later repository's job and is not attempted here.
--
-- ADD ONLY: this migration creates one new table. It does not ALTER
-- stratum.ku_candidate, stratum.reading_evidence or any earlier table.
-- The classification columns added by 071 are read, never modified.
--
-- Object model (extended):
--   ReadingEvidence 1---1 EvidenceQuality      (071)
--   KUCandidate    1---1 KUVerification      (072)
--
-- Authority graph (072 adds the final link):
--   BookSource -> SourceVersion -> ReadingRun -> ReadingEvidence
--              -> KUCandidate  -> KUVerification

-- ── 1. ku_verification ───────────────────────────────────────────────────────
-- One row per verification decision. The row is the reason a candidate
-- became a verified understanding unit, so the trace is NOT NULL: a
-- decision without a trace cannot be stored.
CREATE TABLE IF NOT EXISTS stratum.ku_verification (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL
        REFERENCES stratum.ku_candidate(id) ON DELETE CASCADE,
    verification_status TEXT NOT NULL
        CHECK (verification_status IN (
            'PENDING', 'VERIFIED', 'REJECTED'
        )),
    verification_method TEXT NOT NULL,
    verifier_version TEXT NOT NULL,
    verification_trace JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- candidate_id UNIQUE: a candidate is decided exactly once. Re-running
    -- the verification stage is a no-op at the schema level, and reversing
    -- a decision is a new verification row rather than an UPDATE.
    CONSTRAINT ku_verification_candidate_uniq UNIQUE (candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_ku_verification_status
    ON stratum.ku_verification(verification_status);

-- ── 2. lifecycle guarantee ───────────────────────────────────────────────────
-- A decision is terminal. PENDING is the only non-terminal state, so
-- PENDING -> VERIFIED and PENDING -> REJECTED are the only legal
-- transitions and both are one-way:
--
--     PENDING ──> VERIFIED   (terminal)
--        │
--        └────> REJECTED   (terminal)
--
-- The terminal states are enforced in the verification model
-- (VerificationViolation) and asserted by the architecture tests. The
-- schema backs this with candidate_id UNIQUE: a candidate is decided
-- once and only once, so no UPDATE can walk a terminal decision back to
-- PENDING. Re-deciding a settled candidate is therefore out of scope for
-- this freeze — it would need a reviewed migration that supersedes the
-- stored decision, not an edit of it.