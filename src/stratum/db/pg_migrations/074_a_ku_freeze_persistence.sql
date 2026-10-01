-- 074: A Repository P4.1 — KU durable persistence
--
-- Rules respected: additive only; never edits migrations 060-073.
--   NO DROP. NO ALTER of any existing A table. No foreign key into
--   another repository.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: make a frozen knowledge unit durable — recoverable across
--   processes and across runs — and record every immutable state change
--   it goes through.
--
-- 073 is NOT recreated here. Audited before this migration was written:
-- every column of the canonical knowledge_unit schema is already present,
-- so nothing needs an ALTER. 073 additionally carries title and
-- evidence_count, which are kept.
--
-- 073 already declares UNIQUE(verification_id), UNIQUE(candidate_id) and
-- UNIQUE(content_hash). Those are what make a replay a no-op rather than a
-- second copy, so the writer relies on them and does not re-declare them.
--
-- Authority chain (074 records the last transitions):
--   KnowledgeUnit --CREATED--> KnowledgeUnit --FROZEN--> KnowledgeUnit

-- ── ku_freeze_event ─────────────────────────────────────────────────────────
-- An immutable record of one state change of one knowledge unit.
--
-- The event row and its unit row are written in ONE transaction. A unit
-- without its event, or an event without its unit, is not a state this
-- database is allowed to be in: the writer rolls back rather than commit
-- half of it.
--
-- There is no UPDATE path here. A row in this table is never rewritten.
CREATE TABLE IF NOT EXISTS stratum.ku_freeze_event (
    id TEXT PRIMARY KEY,

    -- ON DELETE RESTRICT, matching 073. An event outlives attempts to
    -- delete the unit it describes; that is the point of recording it.
    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'CREATED', 'FROZEN', 'SUPERSEDED'
        )),

    from_status TEXT,
    to_status TEXT NOT NULL
        CHECK (to_status IN (
            'FREEZE_PENDING', 'FROZEN', 'FAILED'
        )),

    -- Deterministic fingerprint of this event, so re-running a freeze
    -- produces the same value instead of a second, different event.
    event_hash TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- One event per type per unit. A replay that recomputes the same
    -- transition collides here and writes nothing.
    CONSTRAINT ku_freeze_event_uniq UNIQUE (knowledge_unit_id, event_type),

    -- A unit's creation and its freeze are distinct facts and must not
    -- carry the same fingerprint.
    CONSTRAINT ku_freeze_event_hash_uniq UNIQUE (event_hash)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ku_freeze_event_unit
    ON stratum.ku_freeze_event(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_freeze_event_type
    ON stratum.ku_freeze_event(event_type);

CREATE INDEX IF NOT EXISTS idx_ku_freeze_event_created_at
    ON stratum.ku_freeze_event(created_at);

-- Persistence indexes for knowledge_unit that 073 does not already carry.
-- 073 indexes status, source_version and created_at, and its three UNIQUE
-- constraints provide indexes on verification_id, candidate_id and
-- content_hash. What a durability query still lacked: which units are
-- actually frozen, and which freeze version wrote them.
CREATE INDEX IF NOT EXISTS idx_knowledge_unit_frozen_at
    ON stratum.knowledge_unit(frozen_at);

CREATE INDEX IF NOT EXISTS idx_knowledge_unit_freeze_version
    ON stratum.knowledge_unit(freeze_version);

-- ── persistence lifecycle ───────────────────────────────────────────────────
--   FREEZE_PENDING ──> FROZEN
--          └───────> FAILED
--
-- FROZEN -> MODIFY and FROZEN -> DELETE are refused by the writer, and by
-- the RESTRICT foreign keys above.
--
-- FAILED is deliberately NOT a value of knowledge_unit.freeze_status, whose
-- CHECK admits only VERIFIED, FREEZE_PENDING, FROZEN and REJECTED. A failed
-- freeze leaves no unit row at all — the transaction rolls back — so there
-- is nothing for FAILED to describe. It is a terminal outcome of an
-- attempt, not a state a unit is left in.
--
-- SUPERSEDED is reserved for a later stage. No writer emits it yet and no
-- test exercises it: a revision is a new unit under a new freeze_version,
-- and that stage has not been built.
--
-- 074_a_ku_freeze_persistence.sql is applied to a staging database only.
-- It was never executed against a production or development data database.