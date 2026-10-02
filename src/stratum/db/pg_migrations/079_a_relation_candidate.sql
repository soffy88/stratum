-- 079: A Repository P5.2 — relation candidate (PRECEDES only)
--
-- Rules respected: additive only; never edits migrations 060-078.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: persist a *relation candidate* — two frozen knowledge units of
-- the same book, in an explicitly declared order, each with its own evidence.
--
--   relation_candidate ──> knowledge_unit (x2, same source version)
--                       └─> evidence (left and right, as arrays)
--
-- Nothing else. No BU2, no B仓, no C仓. A relation here records a comparison
-- the book makes between two of its own rows. It never decides what the
-- comparison means.
--
-- ── relationship to the frozen 075 relation layer ───────────────────────────
--
-- stratum.ku_relation (075_a_ku_evolution.sql) already stores factual relations
-- between two units, frozen, with vocabulary SHARES_EVIDENCE / SAME_SOURCE_SPAN
-- / REVISES and 2 live rows. It is left completely untouched: no ALTER, no DROP,
-- no vocabulary change, no merge. 079 is a *second*, differently-scoped layer:
--
--   ku_relation         undirected, machine-comparable facts about two rows
--                       (same evidence row, same cited span, one revises the
--                       other), no evidence columns of its own
--   relation_candidate  directed PRECEDES, both sides evidence-linked, and
--                       carrying a source_version_id
--
-- The two vocabularies are disjoint by design, so a row in one is never a row
-- in the other and there is no precedence rule between them. See
-- A_P5_2_RELATION_SCHEMA_REVIEW.md §1.
--
-- ── why only PRECEDES ──────────────────────────────────────────────────────
--
-- The review spec proposed SUPPORTS / CONTRASTS / PRECEDES / DEPENDS_ON. Three
-- of the four are deferred, not because they are hard, but because they are
-- semantic judgements:
--
--   075's own comment (lines 189-192) already refused this class of value:
--     "There is no value meaning 'these say the same thing' or 'these are in
--      tension', because deciding either is a semantic judgement: it belongs to
--      B仓, and A仓 has no authority to make it."
--
--   CONTRASTS is that same judgement under a new name. SUPPORTS and DEPENDS_ON
--   need the same authority A仓 does not have. All three are therefore absent
--   from the CHECK below, not merely unused: a future writer cannot insert them
--   even by mistake.
--
--   PRECEDES is machine-verifiable. It is a comparison between two locators the
--   book itself supplies, the same grade as 075's SAME_SOURCE_SPAN. That the
--   *direction* is declared rather than inferred is a service gate, recorded as
--   a known limitation, because DB cannot order two units without a CHECK that
--   reads another table — which PostgreSQL rejects.
--
-- ── two deviations from the review spec v0.2 schema list ───────────────────
--
-- 1. extractor_version is present. v0.2 dropped it from both the column list
--    and the hash formula. That column is the only thing in the row that says
--    whether a relation was extracted or declared, and P5.0 and P5.1 both made
--    pilot rows distinguishable at the database level for exactly this reason.
--    Without it, and without it in the hash, a future extractor run over the
--    same two units and the same evidence would collide on relation_hash and be
--    silently swallowed as a replay of the pilot. Restored, per decision.
--
-- 2. status has no DEFAULT-free column and SUPPORTED is terminal. v0.2's arrow
--    diagram (GENERATED -> SUPPORTED -> REJECTED, REJECTED terminal) permits
--    SUPPORTED -> REJECTED, which v1.0 §9 forbade and which 077 and 078 both
--    freeze against: A仓 corrects by appending a new relation under a new hash,
--    never by downgrading one in place. The CHECK below cannot express a state
--    machine — see the note at the foot of this file — so this is enforced in
--    the writer and recorded as a known limitation. Restored to the 077/078
--    rule, per decision.
--
-- ── same-source enforcement: composite foreign key, measured ───────────────
--
-- v0.2 §"SAME SOURCE ENFORCEMENT" asked for this. It is not expressible as a
-- CHECK, and with the single-column foreign keys v1.0 §3.1 specified it was not
-- enforced at all. Measured against PostgreSQL before writing:
--
--   single-column FKs, both unit ids real, source_version_id naming a
--   different book  =>  accepted. A cross-book relation, silently.
--
--   CHECK (SELECT source_version_id FROM knowledge_unit WHERE ...)  =>
--     ERROR: cannot use subquery in check constraint
--
-- A composite key fixes it, and the fix needs a unique index on the referenced
-- column pair:
--
--   CREATE UNIQUE INDEX knowledge_unit_id_source_version_uniq
--       ON stratum.knowledge_unit (id, source_version_id);
--   FOREIGN KEY (left_unit_id, source_version_id)
--       REFERENCES stratum.knowledge_unit (id, source_version_id)
--
-- Measured: same-book pair accepted, cross-book pair refused with
-- "violates foreign key constraint".
--
-- That index is the one change this migration makes to a frozen table, and the
-- review spec authorised it explicitly. Note what it is *not*: (id,
-- source_version_id) is already unique because id is the primary key, so this
-- index asserts no new fact about the data and cannot fail on existing rows.
-- It exists to be a foreign-key target, and it adds write amplification only.
-- No row, column or value in knowledge_unit is touched.
--
-- The alternative was a BEFORE INSERT trigger, also measured working. It was
-- rejected: A仓 has no trigger or function anywhere in 070-078, and this stage
-- does not introduce the first one for one constraint.
--
-- ── the foreign-key target for the two composite keys below ──────────────────
-- Idempotent: id is already unique, so this can only ever succeed.
--
-- This comes BEFORE the table on purpose. Measured on the first apply: with the
-- index declared after the CREATE TABLE, PostgreSQL refuses the composite
-- foreign key with
--
--   ERROR: there is no unique constraint matching given keys for referenced
--   table "knowledge_unit"
--
-- and — because DDL is transactional — the whole migration rolls back and
-- leaves nothing behind. Which is the good case. The bad case is recording 079
-- in the ledger because the psql wrapper exited zero anyway.
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_unit_id_source_version_uniq
    ON stratum.knowledge_unit (id, source_version_id);

-- ── relation_candidate ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.relation_candidate (
    id TEXT PRIMARY KEY,

    -- Exactly one value. The deferred types are absent from the CHECK rather
    -- than left unused, so a later writer cannot smuggle CONTRASTS in here.
    relation_type TEXT NOT NULL
        CHECK (relation_type IN ('PRECEDES')),

    -- The book this relation belongs to. RESTRICT: a relation must not be able
    -- to take its book with it.
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    -- The two units, in declared order. left precedes right.
    left_unit_id TEXT NOT NULL,
    right_unit_id TEXT NOT NULL,

    -- Both sides evidence-linked. Two CHECKs rather than one side with a
    -- nullable column: a CHECK passes on NULL, so a nullable side would let an
    -- evidence-less relation through the guard written to prevent it. Same
    -- class as the array_length finding in 077 and the nullable-status finding
    -- in the P5.2 review.
    left_evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(left_evidence_ids) >= 1),
    right_evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(right_evidence_ids) >= 1),

    -- GENERATED -> SUPPORTED | REJECTED, and no edge leaves either.
    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    -- The replay identity. Covers relation_type, source_version, both unit ids,
    -- both evidence sets and the extractor version, so the same relation found
    -- again is a no-op and a relation with different evidence is a new row.
    relation_hash TEXT NOT NULL,

    -- 'relation_extractor_v1' for a real extraction, 'pilot-declared' for a
    -- declared pilot relation. Never interchangeable.
    extractor_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT now(),

    CONSTRAINT relation_candidate_hash_uniq UNIQUE (relation_hash),

    -- A unit cannot precede itself. Expressible in a CHECK because both sides
    -- are columns of this same row.
    CONSTRAINT relation_no_self CHECK (left_unit_id <> right_unit_id),

    -- Same-source enforcement. Both unit references carry source_version_id,
    -- so a unit from another book cannot satisfy the key.
    CONSTRAINT relation_left_same_source
        FOREIGN KEY (left_unit_id, source_version_id)
        REFERENCES stratum.knowledge_unit (id, source_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT relation_right_same_source
        FOREIGN KEY (right_unit_id, source_version_id)
        REFERENCES stratum.knowledge_unit (id, source_version_id)
        ON DELETE RESTRICT
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_relation_candidate_source_version
    ON stratum.relation_candidate(source_version_id);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_type
    ON stratum.relation_candidate(relation_type);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_status
    ON stratum.relation_candidate(status);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_extractor
    ON stratum.relation_candidate(extractor_version);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_left_unit
    ON stratum.relation_candidate(left_unit_id);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_right_unit
    ON stratum.relation_candidate(right_unit_id);

-- Containment lookups for the evidence arrays, which carry no foreign key.
CREATE INDEX IF NOT EXISTS idx_relation_candidate_left_evidence
    ON stratum.relation_candidate USING GIN (left_evidence_ids);

CREATE INDEX IF NOT EXISTS idx_relation_candidate_right_evidence
    ON stratum.relation_candidate USING GIN (right_evidence_ids);

-- ── what the database does and does not guarantee ───────────────────────────
-- Guaranteed here:
--   foreign key integrity (source_version)
--   same-source enforcement for both units, via composite keys
--   relation_type vocabulary, closed to PRECEDES
--   both evidence arrays non-empty
--   status vocabulary
--   replay hash uniqueness
--   self-relation exclusion
--
-- NOT guaranteed, and not guaranteeable here:
--   the state machine. A CHECK cannot compare a column to its own previous
--   value, so nothing stops a raw UPDATE from moving SUPPORTED back to
--   GENERATED, or REJECTED to SUPPORTED. Enforced in RelationWriter and
--   recorded as a known limitation.
--
--   locator order. left_unit_id < right_unit_id in *reading* order is not the
--   same comparison as the id ordering used by ku_relation, and enforcing it
--   would need a CHECK that reads reading_evidence — which PostgreSQL rejects
--   ("cannot use subquery in check constraint"). Enforced in the writer.
--
--   evidence existence. TEXT[] carries no foreign key. The CHECK proves the
--   array is non-empty, not that its members are real rows of the same book.
--   Enforced in the writer, measured by the traceability gate.
--
-- 079_a_relation_candidate.sql is applied to a staging database only. It was
-- never executed against a production or development data database.