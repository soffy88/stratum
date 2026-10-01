-- 077: A Repository P5.0 — condition / boundary candidate layer
--
-- Rules respected: additive only; never edits migrations 060-076.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: let a frozen knowledge unit carry source-grounded condition
--   and boundary *candidates*.
--
-- ADDITIVE ONLY:
--   two new tables, indexes, one foreign key each. knowledge_unit,
--   ku_candidate, ku_verification, required_slots(), SemanticIntegrity and
--   the P3 verification logic are all untouched. There is no UPDATE path
--   here and no backfill: a row in either table is never rewritten.
--
-- WHY A SEPARATE LAYER AND NOT TWO COLUMNS ON ku_candidate
--   A condition is not an input to a verification decision. It is
--   interpretation enrichment applied *after* a unit is frozen, which is
--   why the data flow forks here:
--
--       Source -> Evidence -> KU Candidate -> Verification -> Frozen KU
--                                                          |
--                                          Condition/Boundary Extractor
--                                                          |
--                                          Condition/Boundary Candidate
--
--   Adding these to the candidate would have put them inside the
--   verification denominator. Measured, that is not hypothetical: today's
--   FACT requires 4 slots, so a perfect candidate scores 4/4 = 1.0; two
--   more required slots would drop the same candidate to 4/6 = 0.6667,
--   which is below the 0.8 threshold and would flip all 11 currently
--   VERIFIED candidates to REJECTED while their units are already frozen
--   and persisted. These tables exist so that cannot happen.
--
-- Authority chain (077 adds side tables, no new link upward):
--   KnowledgeUnit <--ku_condition_candidate-- ReadingEvidence
--   KnowledgeUnit <--ku_boundary_candidate-- ReadingEvidence
--
-- Authority priority unchanged: SourceVersion > Evidence > Verification >
-- Frozen KU. Nothing here may be read as an assertion that a claim is true.

-- ── ku_condition_candidate ──────────────────────────────────────────────────
-- A source-grounded qualifier under which a frozen claim holds.
--
-- condition_type is a closed vocabulary of TWO values in this version.
-- Measured on the frozen pilot: ACTOR markers are present in 5/10 spans and
-- TIME markers in 4/10, but three of the five factors the wider proposal
-- named have no extractor at all — STATE, LOCATION and PREREQUISITE score
-- 0/18. Admitting them to the CHECK would mean admitting factor names that
-- nothing can produce or check. They stay out until an extractor exists.
--
-- Every statement here is a verbatim substring of the unit's anchored
-- span. A statement that cannot be pointed at in the source does not get a
-- row: hedged qualifiers ("通常", "一般", "可能") and causal connectives
-- ("因为", "所以", "导致") are refused by the writer, because neither is a
-- checkable condition — the first is a tendency and the second belongs to
-- the mechanism layer.
CREATE TABLE IF NOT EXISTS stratum.ku_condition_candidate (
    id TEXT PRIMARY KEY,

    -- The frozen unit this qualifies. RESTRICT: a condition must not be
    -- able to delete, or be orphaned by, the unit it was read from.
    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    condition_type TEXT NOT NULL
        CHECK (condition_type IN (
            'ACTOR', 'TIME'
        )),

    -- Verbatim from the unit's anchored span. Never paraphrased.
    statement TEXT NOT NULL
        CHECK (length(btrim(statement)) > 0),

    -- Evidence this candidate was read from. Always at least one.
    --
    -- TEXT[] rather than a join table, so there is no foreign key on this
    -- column: an array cannot carry one. The consequence is stated plainly
    -- — ORPHAN=0 is enforced by the writer and read by a gate, not by the
    -- database. That is a real weakening of the other three tables in this
    -- repository and is deliberate: the schema was frozen with this shape.
    -- cardinality(), not array_length(). Measured against a live database:
    -- array_length(ARRAY[]::text[], 1) is NULL, and a CHECK constraint
    -- passes when its expression is NULL, so an array_length guard accepts
    -- the empty array it exists to reject. cardinality() returns 0 there,
    -- so 0 >= 1 is false and the row is refused.
    evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(evidence_ids) >= 1),

    extractor_version TEXT NOT NULL,

    confidence NUMERIC NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- Deterministic fingerprint of this candidate: unit, type, statement,
    -- evidence and extractor version. Re-running the extractor collides here
    -- and appends nothing, which is what makes replay a no-op rather than a
    -- second copy of the same reading.
    condition_hash TEXT NOT NULL,

    -- No VERIFIED. A condition is an interpretation of a span, and A仓 has
    -- no authority to declare an interpretation true. SUPPORTED means the
    -- span was re-read and holds, not that the inference does.
    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    created_at TIMESTAMP NOT NULL,

    CONSTRAINT ku_condition_candidate_hash_uniq UNIQUE (condition_hash)
);

-- ── ku_boundary_candidate ───────────────────────────────────────────────────
-- A source-grounded statement of where a frozen claim stops applying.
--
-- boundary_type declares four values and admits two. TIME_LIMIT and
-- ACTOR_LIMIT are detectable from span markers; SCOPE_LIMIT and EXCEPTION
-- were found in 0/10 frozen spans, so admitting them would leave two values
-- that no extractor can ever produce.
--
-- On the frozen pilot this table is EMPTY, and that is the correct result
-- rather than a shortfall: no span in the pilot states a limit. A gate
-- asserts the row count is 0 and the runner reports it.
CREATE TABLE IF NOT EXISTS stratum.ku_boundary_candidate (
    id TEXT PRIMARY KEY,

    knowledge_unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    boundary_type TEXT NOT NULL
        CHECK (boundary_type IN (
            'TIME_LIMIT', 'ACTOR_LIMIT'
        )),

    -- Verbatim from the anchored span, same rule as a condition.
    statement TEXT NOT NULL
        CHECK (length(btrim(statement)) > 0),

    -- cardinality(), not array_length(). Measured against a live database:
    -- array_length(ARRAY[]::text[], 1) is NULL, and a CHECK constraint
    -- passes when its expression is NULL, so an array_length guard accepts
    -- the empty array it exists to reject. cardinality() returns 0 there,
    -- so 0 >= 1 is false and the row is refused.
    evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(evidence_ids) >= 1),

    extractor_version TEXT NOT NULL,

    confidence NUMERIC NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),

    boundary_hash TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    created_at TIMESTAMP NOT NULL,

    CONSTRAINT ku_boundary_candidate_hash_uniq UNIQUE (boundary_hash)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
-- Reading a unit's conditions, which is the only query the layer serves.
CREATE INDEX IF NOT EXISTS idx_ku_condition_candidate_unit
    ON stratum.ku_condition_candidate(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_condition_candidate_type
    ON stratum.ku_condition_candidate(condition_type);

-- Containment lookups for evidence_ids, which have no foreign key.
CREATE INDEX IF NOT EXISTS idx_ku_condition_candidate_evidence
    ON stratum.ku_condition_candidate USING GIN (evidence_ids);

CREATE INDEX IF NOT EXISTS idx_ku_boundary_candidate_unit
    ON stratum.ku_boundary_candidate(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_boundary_candidate_type
    ON stratum.ku_boundary_candidate(boundary_type);

CREATE INDEX IF NOT EXISTS idx_ku_boundary_candidate_evidence
    ON stratum.ku_boundary_candidate USING GIN (evidence_ids);

-- ── what this layer deliberately does not contain ───────────────────────────
-- No status of VERIFIED.  A condition and a boundary are readings of a
-- span. Promoting one to a verdict would make A仓 the authority on its own
-- interpretation, which is the role B仓 exists for.
--
-- No UPDATE, no DELETE, no merge, no dedup. Two candidates that read alike
-- stay two rows; deciding they are the same reading is a judgement about
-- meaning, and A仓 has no authority to make it.
--
-- No causal vocabulary. "因为" / "所以" / "导致" belong to the mechanism
-- layer, which is not built and must not be pre-empted here.
--
-- No hedged vocabulary. "通常" / "一般" / "可能" are tendencies. A tendency
-- belongs to a constraint candidate, which this layer is not — see the
-- guard that keeps the two vocabularies disjoint.
--
-- 077_a_condition_boundary.sql is applied to a staging database only. It was
-- never executed against a production or development data database.
