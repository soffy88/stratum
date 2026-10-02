-- 072: A Repository P3 — Knowledge Unit Verification
--
-- Rules respected: additive only; never edits migrations 060-071.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: decide whether a KU Candidate is a verified knowledge unit.
--   The decision is the product of the candidate, its evidence chain and
--   the four checks below. Nothing else may influence it.
--   A verified unit stays a fact unit. Grouping units into concepts is
--   another repository's work and is not attempted here.
--
-- ADD ONLY: one new table. No existing table is altered. The
-- classification columns added by 071 are read here, never modified.
--
-- Authority chain (072 adds the final link):
--   BookSource -> SourceVersion -> ReadingRun -> ReadingEvidence
--              -> KUCandidate  -> KUVerification

-- ── ku_verification ─────────────────────────────────────────────────────────
-- One row per verification decision. The row records why a candidate may
-- be treated as a verified knowledge unit.
--
-- verification_score is the minimum of the four underlying checks, so the
-- weakest link decides. A decision is only VERIFIED at or above the
-- verifier's threshold; storing the score makes the verdict auditable
-- without re-running the verifier.
CREATE TABLE IF NOT EXISTS stratum.ku_verification (
    id TEXT PRIMARY KEY,

    -- Authority link. ON DELETE CASCADE: a candidate's decisions belong to
    -- the candidate, and a candidate removed with its evidence takes its
    -- verdicts with it rather than leaving them orphaned.
    candidate_id TEXT NOT NULL
        REFERENCES stratum.ku_candidate(id) ON DELETE CASCADE,

    verification_status TEXT NOT NULL
        CHECK (verification_status IN (
            'PENDING', 'VERIFYING', 'VERIFIED', 'REJECTED'
        )),

    verification_score FLOAT NOT NULL
        CHECK (verification_score >= 0.0 AND verification_score <= 1.0),

    -- The four checks. Each is true exactly when its own score met the
    -- verifier threshold, so a false check plus the score states the whole
    -- reason for a rejection without a separate narrative column.
    definition_check BOOLEAN NOT NULL,
    trace_check BOOLEAN NOT NULL,
    source_check BOOLEAN NOT NULL,
    quality_check BOOLEAN NOT NULL,

    -- The quote that anchored the decision. Set only when the quote was
    -- found inside the evidence content; a generated or paraphrased quote
    -- is never stored here, so an empty value means the unit was not
    -- anchored.
    verified_quote TEXT,

    verifier_version TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- A candidate is decided once and only once, which is what makes the
    -- terminal states terminal: no UPDATE can walk a settled verdict back
    -- to PENDING or VERIFYING.
    CONSTRAINT ku_verification_candidate_uniq UNIQUE (candidate_id)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ku_verification_candidate
    ON stratum.ku_verification(candidate_id);

CREATE INDEX IF NOT EXISTS idx_ku_verification_status
    ON stratum.ku_verification(verification_status);

CREATE INDEX IF NOT EXISTS idx_ku_verification_created_at
    ON stratum.ku_verification(created_at);

-- ── lifecycle ───────────────────────────────────────────────────────────────
-- Four states, one path out of PENDING:
--
--     PENDING ──> VERIFYING ──> VERIFIED   (terminal)
--                    └───────> REJECTED   (terminal)
--
-- VERIFIED -> REJECTED, VERIFIED -> PENDING and REJECTED -> VERIFIED are
-- all refused: a settled verdict is final. Enforced in the verification
-- model and asserted by the architecture tests; candidate_id UNIQUE backs
-- it at the schema level.
--
-- Re-deciding a settled candidate would need a reviewed migration that
-- supersedes the stored verdict, never an edit of it.
--
-- 072_a_ku_verification.sql is applied to a staging database only. It was
-- never executed against a production or development data database.