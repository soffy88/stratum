-- 075: A Repository P5 — KU lifecycle evolution
--
-- Rules respected: additive only; never edits migrations 060-074.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: let a frozen knowledge unit change without ever being
--   rewritten. P4 froze the unit; P4.1 made it durable. This migration
--   gives it a history: a status that moves, a revision that is appended
--   beside the row it replaces, a review that cites what it read, a
--   confidence series that only grows, and factual relations.
--
-- ADDITIVE ONLY:
--   four new tables, no existing table altered, no data backfilled, no
--   INSERT of any kind. Rows arrive only through the evolution service.
--
-- Why four tables and not columns on knowledge_unit:
--   knowledge_unit.freeze_status is immutable and terminal at FROZEN, and
--   `knowledge_unit_frozen_at_required` plus the RESTRICT foreign keys
--   make an UPDATE of a frozen row the thing this repository exists to
--   prevent. A lifecycle that can only be expressed as an UPDATE would
--   therefore be a lifecycle this schema refuses to have. So the status
--   lives in the event log and is derived by folding it — the same way a
--   bank balance is derived from its ledger rather than stored twice.
--
-- Authority chain (075 adds four side tables, no new link upward):
--   KnowledgeUnit --REVISES--> KnowledgeUnit
--   KnowledgeUnit --reviewed by--> ReadingEvidence
--   KnowledgeUnit --anchored in--> ReadingEvidence
--
-- Authority priority is unchanged: SourceVersion > Evidence > Frozen KU.
-- Nothing here may be read as an assertion that a unit is true.

-- ── ku_revision ─────────────────────────────────────────────────────────────
-- One row per revision. The prior unit stays exactly as it was and stays
-- citable; this row records that a successor exists.
--
-- UNIQUE(prior_unit_id) is the load-bearing constraint: a unit is
-- superseded at most once, so a unit's revision history is a chain and
-- never a tree. It is also what makes the SUPERSEDED event in 074
-- emittable exactly once per unit, which its
-- UNIQUE(knowledge_unit_id, event_type) already required.
--
-- Both endpoints reference knowledge_unit ON DELETE RESTRICT: a revision
-- must not be able to delete either the row it replaces or its successor.
CREATE TABLE IF NOT EXISTS stratum.ku_revision (
    id TEXT PRIMARY KEY,

    -- The unit being replaced. Never modified, never deleted.
    prior_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    -- The newly appended unit that supersedes it. Append-only: this is a
    -- new row under a new freeze_version, not an edit of the prior one.
    revised_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    -- 1 for the first revision of a unit, 2 for a revision of a revision.
    revision_index INTEGER NOT NULL CHECK (revision_index >= 1),

    -- The review that authorised the revision, quoted. Audit text only:
    -- it records what the reviewer said, never a new claim about the book.
    revision_basis TEXT NOT NULL
        CHECK (length(btrim(revision_basis)) > 0),

    -- Deterministic fingerprint, so replaying a revision collides here
    -- and writes nothing instead of appending the same revision twice.
    revision_hash TEXT NOT NULL,

    lifecycle_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT ku_revision_prior_uniq UNIQUE (prior_unit_id),
    CONSTRAINT ku_revision_revised_uniq UNIQUE (revised_unit_id),
    CONSTRAINT ku_revision_hash_uniq UNIQUE (revision_hash),

    -- A unit does not revise itself.
    CONSTRAINT ku_revision_not_self
        CHECK (prior_unit_id <> revised_unit_id)
);

-- ── ku_review_event ─────────────────────────────────────────────────────────
-- One immutable row per review decision about one unit.
--
-- evidence_id is NOT NULL and RESTRICT. A review with no evidence is not a
-- review, it is an opinion: the whole point of recording it here is that a
-- later reader can go and check the span the reviewer was looking at.
--
-- The status vocabulary is the lifecycle, and neither endpoint is ever
-- rewritten — status_of() folds this log. from_status = to_status is
-- legal and normal: CONFIRMED and CHALLENGED record a signal without
-- moving the unit out of ACTIVE.
CREATE TABLE IF NOT EXISTS stratum.ku_review_event (
    id TEXT PRIMARY KEY,

    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    review_type TEXT NOT NULL
        CHECK (review_type IN (
            'CONFIRMED', 'CHALLENGED', 'QUARANTINED', 'RELEASED',
            'SUPERSEDED'
        )),

    -- The lifecycle before and after this review, as the fold saw it when
    -- the row was written. The CHECK admits only the vocabulary; whether
    -- from_status agrees with the preceding row is the service's job to get
    -- right and is what sequence ordering is there to make checkable.
    from_status TEXT NOT NULL
        CHECK (from_status IN ('ACTIVE', 'QUARANTINED', 'SUPERSEDED')),
    to_status TEXT NOT NULL
        CHECK (to_status IN ('ACTIVE', 'QUARANTINED', 'SUPERSEDED')),

    -- Why. Mandatory and non-blank: an unreasoned review is refused.
    rationale TEXT NOT NULL
        CHECK (length(btrim(rationale)) > 0),

    -- What the reviewer actually read. See above.
    evidence_id TEXT NOT NULL
        REFERENCES stratum.reading_evidence(id) ON DELETE RESTRICT,

    review_hash TEXT NOT NULL,

    lifecycle_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Ordering within one unit's history. The fold reads in this order, so
    -- the status a unit ends in does not depend on insertion order or on
    -- which process wrote the row.
    sequence INTEGER NOT NULL CHECK (sequence >= 1),

    -- Idempotency comes from review_hash, not from (unit, type): a unit may
    -- legitimately be quarantined, released and quarantined again, and
    -- refusing the second quarantine would make that real lifecycle
    -- inexpressible. An identical replay still collides on the hash.
    CONSTRAINT ku_review_event_seq_uniq UNIQUE (knowledge_unit_id, sequence),
    CONSTRAINT ku_review_event_hash_uniq UNIQUE (review_hash)
);

-- ── ku_confidence_evolution ─────────────────────────────────────────────────
-- One immutable measurement per step of a unit's confidence history.
--
-- Confidence here is a measurement of how well the unit is supported, not
-- a probability that the world is as it says. Nothing in this table may be
-- read as a truth score, and the service never lowers a unit's status on
-- its own: only a review moves a unit, and this table records what the
-- review found.
--
-- measured_confidence is bounded by the column CHECK as well as by the
-- service, because a row that could hold 4.0 would be read as a claim.
CREATE TABLE IF NOT EXISTS stratum.ku_confidence_evolution (
    id TEXT PRIMARY KEY,

    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    sequence INTEGER NOT NULL CHECK (sequence >= 1),

    measured_confidence FLOAT NOT NULL
        CHECK (measured_confidence >= 0.0 AND measured_confidence <= 1.0),

    -- What the measurement was taken from. A closed vocabulary, so a
    -- reading of this table always names its own method.
    basis TEXT NOT NULL
        CHECK (basis IN (
            'VERIFICATION_SCORE', 'REVIEW_SIGNAL', 'EVIDENCE_QUALITY'
        )),

    -- Deterministic fingerprint of the observation.
    observation_hash TEXT NOT NULL,

    lifecycle_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT ku_confidence_seq_uniq UNIQUE (knowledge_unit_id, sequence),
    CONSTRAINT ku_confidence_hash_uniq UNIQUE (observation_hash)
);

-- ── ku_relation ─────────────────────────────────────────────────────────────
-- Factual relations between two units.
--
-- The vocabulary is the whole design. Every value below is a comparison a
-- machine can make by reading two rows — same evidence row, same cited
-- span under the same source version, one revises the other. There is no
-- value meaning "these say the same thing" or "these are in tension",
-- because deciding either is a semantic judgement: it belongs to B仓, and
-- A仓 has no authority to make it. A relation here never merges, never
-- dedups and never retires a unit; it only records a fact about two rows
-- that already exist.
--
-- CHECK (from_unit_id < to_unit_id) canonicalises the pair, so an
-- undirected relation is stored once no matter which side was discovered
-- first, which is what keeps a replay from appending its mirror.
CREATE TABLE IF NOT EXISTS stratum.ku_relation (
    id TEXT PRIMARY KEY,

    from_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,
    to_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    relation_type TEXT NOT NULL
        CHECK (relation_type IN (
            'SHARES_EVIDENCE', 'SAME_SOURCE_SPAN', 'REVISES'
        )),

    relation_hash TEXT NOT NULL,

    lifecycle_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT ku_relation_uniq
        UNIQUE (from_unit_id, to_unit_id, relation_type),
    CONSTRAINT ku_relation_hash_uniq UNIQUE (relation_hash),

    -- Canonical ordering plus self-exclusion in one constraint.
    CONSTRAINT ku_relation_ordered CHECK (from_unit_id < to_unit_id)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ku_revision_prior
    ON stratum.ku_revision(prior_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_revision_revised
    ON stratum.ku_revision(revised_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_review_event_unit
    ON stratum.ku_review_event(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_review_event_type
    ON stratum.ku_review_event(review_type);

CREATE INDEX IF NOT EXISTS idx_ku_review_event_evidence
    ON stratum.ku_review_event(evidence_id);

CREATE INDEX IF NOT EXISTS idx_ku_confidence_unit
    ON stratum.ku_confidence_evolution(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_from
    ON stratum.ku_relation(from_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_to
    ON stratum.ku_relation(to_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_type
    ON stratum.ku_relation(relation_type);

-- ── KU lifecycle ────────────────────────────────────────────────────────────
--   ACTIVE ──> QUARANTINED ──> ACTIVE
--      │             │
--      └─────────────┴──────> SUPERSEDED   (terminal)
--
-- A frozen unit is ACTIVE the moment it is persisted. QUARANTINED means a
-- reviewer found a fidelity defect and the unit is still citable but no
-- longer to be relied on without reading its review; RELEASED returns it
-- to ACTIVE. SUPERSEDED means a successor unit exists, and is terminal
-- because UNIQUE(prior_unit_id) allows one successor only.
--
-- None of these is a mutation of knowledge_unit. The status is the fold of
-- ku_review_event, so a unit's row never changes and every step of its
-- history stays on the record.
--
-- ── confidence ──────────────────────────────────────────────────────────────
-- Confidence grows as an append-only series keyed by (unit, sequence).
-- It is never overwritten and never deleted, so the measurement that
-- lowered a unit is still there beside the one that raised it.
--
-- ── relations ───────────────────────────────────────────────────────────────
-- Factual only. See the vocabulary note above the table: no value asserts
-- that two units mean the same thing, and none retires or merges anything.
--
-- 075_a_ku_evolution.sql is applied to a staging database only. It was
-- never executed against a production or development data database.
