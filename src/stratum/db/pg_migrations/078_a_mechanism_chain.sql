-- 078: A Repository P5.1 — mechanism chain
--
-- Rules respected: additive only; never edits migrations 060-077.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: persist a mechanism *candidate* — an ordered structure of
--   evidence-linked nodes, each pointing at a frozen knowledge unit of this
--   same book.
--
--   mechanism -> mechanism_node -> knowledge_unit -> evidence
--
--   Nothing else. No BU2, no B仓, no C仓. A mechanism records a structure
--   the book describes, never an interpretation of why it matters.
--
-- ADDITIVE ONLY:
--   two new tables, indexes, two foreign keys. knowledge_unit,
--   ku_candidate, ku_verification, required_slots(), SemanticIntegrity and
--   every table inherited from 070-077 are untouched.
--
-- ── two deviations from the review spec, both measured ─────────────────────
--
-- 1. mechanism_node.mechanism_id is ON DELETE RESTRICT, not CASCADE.
--
--    Measured across the A chain: ON DELETE CASCADE appears only in 070-072,
--    the extraction chain (book_source -> source_version -> reading_run ->
--    reading_evidence -> ku_candidate), where a deleted book should take its
--    evidence with it. Every frozen or derived artifact from 073 onward uses
--    RESTRICT — ten RESTRICT references to knowledge_unit alone. 073 states
--    the position in the migration itself:
--
--      RESTRICT, not CASCADE. A frozen unit is meant to outlast the rows
--      that produced it: cascading would let a deleted evidence row take a
--      frozen unit with it, which is exactly the rewrite this table exists
--      to prevent.
--
--    A mechanism chain is a frozen artifact, so CASCADE would make this the
--    first frozen table in A仓 where deleting a parent silently takes its
--    children. The chain's shape is part of what was recorded; losing nodes
--    to a parent delete is a rewrite, not a cleanup.
--
-- 2. No freeze event is written.
--
--    The review spec's transaction contract lists a freeze event as step 3.
--    That is unsatisfiable against the frozen 074 vocabulary: ku_freeze_event
--    admits event_type CREATED/FROZEN/SUPERSEDED and to_status
--    FREEZE_PENDING/FROZEN/FAILED, and a mechanism has its own status
--    vocabulary that fits neither. Writing a FROZEN event would also claim
--    the mechanism was frozen by the P3 freeze service, which it was not.
--
--    The P5.0 layer already settled this pattern: six candidate rows, zero
--    events, lifecycle carried in the candidate's own `status`. This stage
--    follows it, and the mechanism's status transitions are gated in the
--    service rather than recorded in another table's vocabulary.

-- ── mechanism_candidate ─────────────────────────────────────────────────────
-- One mechanism chain, as a candidate.
--
-- mechanism_hash is the replay identity. It covers the source version, the
-- ordered node fingerprints and the extractor version, and therefore the
-- evidence too — a node's fingerprint includes its evidence_ids, so the
-- coverage is transitive. UNIQUE is what turns a replay into a no-op rather
-- than a second copy of the same chain.
--
-- status has no VERIFIED and no CONFIRMED. VERIFIED is the success value of
-- ku_verification.verification_status, and a mechanism is not a verified
-- proposition; CONFIRMED would be a second word for that same fact.
CREATE TABLE IF NOT EXISTS stratum.mechanism_candidate (
    id TEXT PRIMARY KEY,

    -- The book this chain belongs to. RESTRICT: a chain must not be able to
    -- take its book with it, and must not be attachable to a version that
    -- does not exist.
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    mechanism_hash TEXT NOT NULL,

    -- GENERATED -> SUPPORTED | REJECTED, and no edge leaves SUPPORTED.
    -- A supported chain is final: A仓 corrects by appending a new chain
    -- under a new hash, never by downgrading this one.
    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    -- 'mechanism_extractor_v1' for a real extraction, 'pilot-declared' for a
    -- pilot chain. The two are never interchangeable: pilot data is not
    -- evidence that the extractor works.
    extractor_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL,

    CONSTRAINT mechanism_candidate_hash_uniq UNIQUE (mechanism_hash)
);

-- ── mechanism_node ──────────────────────────────────────────────────────────
-- One step of a chain.
--
-- The node is what carries the unit reference and the evidence, so the
-- chain is evidence-linked at every step rather than only at its ends.
CREATE TABLE IF NOT EXISTS stratum.mechanism_node (
    id TEXT PRIMARY KEY,

    -- RESTRICT, per the deviation note above.
    mechanism_id TEXT NOT NULL
        REFERENCES stratum.mechanism_candidate(id) ON DELETE RESTRICT,

    -- Each node sits on a frozen unit of the same book. RESTRICT: a unit
    -- that has been read into a chain must not be deletable out from under
    -- it.
    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    node_role TEXT NOT NULL
        CHECK (node_role IN ('TRIGGER', 'TRANSITION', 'RESULT')),

    -- Chain order, explicit. A mechanism whose order has to be inferred from
    -- array position is not a recorded structure.
    sequence_order INTEGER NOT NULL
        CHECK (sequence_order >= 1),

    -- cardinality(), not array_length(). Measured while applying 077:
    -- array_length(ARRAY[]::text[], 1) is NULL and a CHECK passes on NULL,
    -- so an array_length guard accepts the empty array it exists to reject.
    evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(evidence_ids) >= 1),

    created_at TIMESTAMP NOT NULL,

    -- One node per position. Without this, two nodes can share a
    -- sequence_order and the chain order becomes ambiguous — which is the
    -- thing the column exists to prevent.
    CONSTRAINT mechanism_node_order_uniq
        UNIQUE (mechanism_id, sequence_order)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_mechanism_candidate_source_version
    ON stratum.mechanism_candidate(source_version_id);

CREATE INDEX IF NOT EXISTS idx_mechanism_candidate_status
    ON stratum.mechanism_candidate(status);

CREATE INDEX IF NOT EXISTS idx_mechanism_candidate_extractor
    ON stratum.mechanism_candidate(extractor_version);

CREATE INDEX IF NOT EXISTS idx_mechanism_node_mechanism
    ON stratum.mechanism_node(mechanism_id);

CREATE INDEX IF NOT EXISTS idx_mechanism_node_unit
    ON stratum.mechanism_node(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_mechanism_node_role
    ON stratum.mechanism_node(node_role);

-- Containment lookups for evidence_ids, which carry no foreign key.
CREATE INDEX IF NOT EXISTS idx_mechanism_node_evidence
    ON stratum.mechanism_node USING GIN (evidence_ids);

-- ── what the database does and does not guarantee ───────────────────────────
-- Guaranteed here:
--   foreign key integrity (source_version, mechanism, knowledge_unit)
--   node ordering uniqueness
--   evidence reference non-empty
--   closed vocabularies for status and node_role
--   replay hash uniqueness
--
-- NOT guaranteed, and not guaranteeable in a CHECK — a CHECK cannot count
--   rows in another table:
--   chain completeness. Nothing here stops a mechanism row with zero nodes,
--   or with only a TRIGGER.
--
-- That is the service gate's job, recorded in the freeze report as
-- KNOWN_LIMITATION 5, and it must be read by a test rather than assumed.
--
-- 078_a_mechanism_chain.sql is applied to a staging database only. It was
-- never executed against a production or development data database.
