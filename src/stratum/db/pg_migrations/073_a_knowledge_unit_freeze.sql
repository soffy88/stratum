-- 073: A Repository P4 — Frozen Knowledge Unit
--
-- Rules respected: additive only; never edits migrations 060-072.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: promote a VERIFIED knowledge unit into a Frozen Knowledge
--   Unit — a stable projection that can be cited by id.
--   A Frozen KU is a projection of a verified candidate. It is a
--   referenceable object, not a judgement that the world is true.
--   Grouping these units into concepts is another repository's work.
--
-- ADDITIVE ONLY:
--   one new table, no existing table altered, no data backfilled, no
--   INSERT of any kind. Rows arrive only through the freeze service.
--
-- Authority chain (073 adds the final link):
--   SourceVersion -> ReadingEvidence -> KUCandidate -> KUVerification
--                 -> KnowledgeUnit (FROZEN)
--
-- Authority priority: Evidence > Verification > Frozen KU.

-- ── knowledge_unit ──────────────────────────────────────────────────────────
-- A frozen knowledge unit.
--
-- statement / canonical_text carry two different things on purpose:
--   statement       the extracted proposition, as the candidate worded it
--   canonical_text  the verbatim span the verification anchored it to
-- Storing both keeps the unit citable without ever restating the source.
--
-- content_hash is the identity of the unit: sha256(statement, evidence
-- fingerprint). It is stored as well as folded into the id because it is
-- what guarantees one unit per evidence-plus-candidate pair, even if two
-- statements ever hash to the same id prefix.
CREATE TABLE IF NOT EXISTS stratum.knowledge_unit (
    id TEXT PRIMARY KEY,

    -- Authority links, all ON DELETE RESTRICT.
    --
    -- RESTRICT, not CASCADE. A frozen unit is meant to outlast the rows
    -- that produced it: cascading would let a deleted evidence row take a
    -- frozen unit with it, which is exactly the rewrite this table exists
    -- to prevent. Deleting a verification that has been frozen is refused
    -- by the database, not by a convention.
    verification_id TEXT NOT NULL
        REFERENCES stratum.ku_verification(id) ON DELETE RESTRICT,
    candidate_id TEXT NOT NULL
        REFERENCES stratum.ku_candidate(id) ON DELETE RESTRICT,
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    title TEXT NOT NULL,
    statement TEXT NOT NULL,

    -- The anchored source span. NOT NULL because a unit that could not be
    -- anchored is not freezable and is never given a row.
    canonical_text TEXT NOT NULL,

    evidence_count INTEGER NOT NULL CHECK (evidence_count >= 1),
    verification_score FLOAT NOT NULL
        CHECK (verification_score >= 0.0 AND verification_score <= 1.0),

    -- Content-derived identity. Never a random UUID, never a sequence, never
    -- a timestamp: the same evidence and the same candidate must always
    -- produce the same unit id.
    content_hash TEXT NOT NULL,

    freeze_status TEXT NOT NULL
        CHECK (freeze_status IN (
            'VERIFIED', 'FREEZE_PENDING', 'FROZEN', 'REJECTED'
        )),

    freeze_version TEXT NOT NULL,

    -- frozen_at is set when the unit becomes FROZEN and is NULL before
    -- that. The row exists from the moment its verification passed, so the
    -- column cannot be NOT NULL from creation.
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    frozen_at TIMESTAMP,

    -- One freeze per verification, and one per candidate. Together these
    -- are what make a replay a no-op rather than a second copy.
    CONSTRAINT knowledge_unit_verification_uniq UNIQUE (verification_id),
    CONSTRAINT knowledge_unit_candidate_uniq UNIQUE (candidate_id),
    CONSTRAINT knowledge_unit_content_hash_uniq UNIQUE (content_hash),

    -- A frozen unit is dated. An unfrozen one is not.
    CONSTRAINT knowledge_unit_frozen_at_required
        CHECK (freeze_status <> 'FROZEN' OR frozen_at IS NOT NULL)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_knowledge_unit_status
    ON stratum.knowledge_unit(freeze_status);

CREATE INDEX IF NOT EXISTS idx_knowledge_unit_source_version
    ON stratum.knowledge_unit(source_version_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_unit_created_at
    ON stratum.knowledge_unit(created_at);

-- ── freeze lifecycle ────────────────────────────────────────────────────────
--   VERIFIED ──> FREEZE_PENDING ──> FROZEN   (terminal)
--                    └───────────> REJECTED  (terminal)
--
-- FROZEN -> VERIFIED, FROZEN -> MODIFY and FROZEN -> DELETE are all
-- refused. The terminal guarantee is enforced in the freeze service
-- (FreezeViolation) and asserted by the architecture tests; here it is
-- backed by the RESTRICT foreign keys and by there being no UPDATE path
-- in this migration at all.
--
-- A revision is never an update. A corrected unit is a new row under a new
-- freeze_version, leaving the frozen row intact and still citable.
--
-- 073_a_knowledge_unit_freeze.sql is applied to a staging database only.
-- It was never executed against a production or development data database.