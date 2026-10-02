-- 081: A Repository P5.4 — constraint annotation
--
-- Rules respected: additive only; never edits migrations 060-080.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: persist a *constraint annotation* — a limiting rule the source
-- states about itself — with the exact span that states it.
--
--   constraint_candidate ──> knowledge_unit ──> reading_evidence
--                       └─> source_version
--
-- Nothing else. No BU2, no B仓, no C仓. A constraint annotation records that a
-- source says something is bounded. It never says the bound is right, high, or
-- ought to be followed.
--
-- ── QUOTE AUTHORITY (frozen decision, see the schema review) ────────────────
--
-- DECISION=SPAN_ONLY. Every one of subject, predicate, object and boundary must
-- be a literal substring of the reading_evidence span. Anything else is refused.
--
-- The reason is not tidiness. Measured on the frozen corpus, the knowledge_unit
-- statement and the raw span use different words:
--
--   KU   : 巴比伦法定利率上限：银子贷款20%/年（按重量计）
--   SPAN : 银子贷款按重量计算每年20%
--
-- The silver-loan span states a rate and contains **no** 上限, no 不得超过, no
-- 禁止. The "cap" framing exists only in the KU statement, which P3/P4 wrote.
-- Allowing fields to be quoted from the KU statement would let an extractor
-- change the semantics first and then have the constraint appear evidenced:
--
--   raw span   "谷物贷款每年33.333%"
--   extractor  "谷物贷款每年33.333%，存在20%上限"
--   => predicate 不得超过, object 20%, typed HARD. A source declaration would
--      have become an extractor assertion.
--
-- So the Babylon rate cap is REJECTED, deliberately: a rate fact is not a
-- constraint. Recorded as LIMITATION-6 — some historically known constraints
-- cannot enter A仓 when the span records a fact but not the limiting rule, and
-- that is the point. A仓 preserves declaration authority, not inferred
-- interpretation.
--
-- The KU statement remains available for human context, display and navigation.
-- It is forbidden as a constraint evidence source, and the writer refuses any
-- field that is not in the raw span.
--
-- ── relationship to the frozen P5.0 layer ──────────────────────────────────
--
-- 077_a_condition_boundary.sql built ku_boundary_candidate and left it empty,
-- holding back:
--
--   NOT_YET_EXTRACTABLE_BOUNDARY_TYPES = ("SCOPE_LIMIT", "EXCEPTION")
--
-- A "利息被限制为不得超过每年8.333%" cap is exactly a SCOPE_LIMIT — the type
-- P5.0 withheld for want of an extractor. 081 is that extractor's landing place,
-- not a parallel table.
--
-- After 081 A仓 holds two limit vocabularies on **different axes**, and they are
-- not interposable:
--
--   077  TIME_LIMIT / ACTOR_LIMIT   which *kind* of scope
--   081  HARD / SOFT / SELF_DEFINED how *strongly* it binds
--
-- SOFT and SELF_DEFINED are declared here and not exercised. Measured: the
-- vocabulary that would define a SOFT constraint (通常 / 一般情况 / 大多数 /
-- 多半) occurs **zero** times in this corpus, and no span makes an author's
-- self-defined range judgeable. They are closed in the CHECK so raw SQL cannot
-- write an undeclared type, and a coverage gate reports per type whether the
-- pilot exercised it — an unexercised type, reported, rather than a vocabulary
-- quietly narrowed to what happened to be testable today.
--
-- ── no new index on a frozen table ─────────────────────────────────────────
--
-- §8 of the review spec lists UNIQUE (id, source_version_id) on knowledge_unit
-- as a required index. It already exists, created by 079 for its own cross-book
-- composite key:
--
--   knowledge_unit_id_source_version_uniq ON knowledge_unit (id, source_version_id)
--
-- So 081 adds **no index to any frozen table**. The composite key below reuses
-- it. This is stated explicitly because a composite foreign key that appears to
-- have no target looks like a bug, and the fix — creating the index here — would
-- duplicate one that 079 already put there.
--
-- ── constraint_candidate ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.constraint_candidate (
    id TEXT PRIMARY KEY,

    -- The version this annotation belongs to. RESTRICT: an annotation must not
    -- be able to take its source with it.
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    -- The frozen unit the constraint was read from. RESTRICT: a unit that has
    -- been read into a constraint must not be deletable out from under it.
    knowledge_unit_id TEXT NOT NULL,

    -- How strongly the source binds itself.
    --
    --   HARD          the source prohibits or limits outright
    --   SOFT          the source states a tendency or a usual case
    --   SELF_DEFINED  the source sets its own range
    --
    -- None of this is a judgement that a constraint is reasonable. "利息不得
    -- 超过8.333%" is HARD because the source says 不得超过, not because a cap is
    -- strict.
    constraint_type TEXT NOT NULL
        CHECK (constraint_type IN ('HARD', 'SOFT', 'SELF_DEFINED')),

    -- The rule as the span states it. All four are literal substrings of the
    -- reading_evidence span; the writer refuses any that is not, and
    -- quote_authority_gate() reads that refusal rather than trusting it.
    --
    -- btrim guards against a whitespace-only value. A CHECK cannot compare
    -- these to the span — that reads another table, which PostgreSQL rejects —
    -- so the span comparison is the writer's and is the real gate. These NOT
    -- NULL and non-empty constraints only stop the degenerate row.
    subject TEXT NOT NULL
        CHECK (length(btrim(subject)) > 0),
    predicate TEXT NOT NULL
        CHECK (length(btrim(predicate)) > 0),
    object TEXT NOT NULL
        CHECK (length(btrim(object)) > 0),
    -- Nullable: a rule may state a limit with no number in it.
    boundary TEXT,

    -- The spans that state it. cardinality, not array_length: measured in 077,
    -- array_length of an empty array is NULL and a CHECK passes on NULL, so an
    -- array_length guard accepts the array it exists to reject.
    --
    -- Ordered before hashing, because traversal order is not a claim. See the
    -- hash note below.
    evidence_ids TEXT[] NOT NULL
        CHECK (cardinality(evidence_ids) >= 1),

    -- The replay identity. Covers the source, the unit, the type, all four
    -- quoted fields and the extractor version, plus the evidence set — so the
    -- same rule read from a different span is a different annotation, which is
    -- what "quoted from the span" means operationally.
    constraint_hash TEXT NOT NULL,

    -- 'constraint_extractor_v1' for a real extraction, 'pilot-declared' for the
    -- pilot. Never interchangeable: a pilot row is not evidence that an
    -- extractor works.
    extractor_version TEXT NOT NULL,

    -- GENERATED -> SUPPORTED | REJECTED, and no edge leaves either. No VERIFIED,
    -- no CONFIRMED, no APPROVED: VERIFIED is the success value of
    -- ku_verification.verification_status, and APPROVED would be a second word
    -- for the same judgement.
    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    created_at TIMESTAMP NOT NULL DEFAULT now(),

    CONSTRAINT constraint_candidate_hash_uniq UNIQUE (constraint_hash),

    -- Same-source enforcement, reusing the index 079 already created. A CHECK
    -- cannot express this — it would need to read knowledge_unit, and
    -- PostgreSQL refuses a CHECK that reads another table — so the tie is a
    -- composite key, and the writer additionally checks it to report a readable
    -- reason instead of a constraint name.
    --
    -- Measured in 079: with single-column keys, a candidate naming one book's
    -- version and another book's unit was accepted.
    CONSTRAINT constraint_unit_same_source
        FOREIGN KEY (knowledge_unit_id, source_version_id)
        REFERENCES stratum.knowledge_unit (id, source_version_id)
        ON DELETE RESTRICT
);

-- ── indexes ─────────────────────────────────────────────────────────────────
-- On this stage's own table only. No frozen table is indexed here; the composite
-- key's target already exists from 079.
CREATE INDEX IF NOT EXISTS idx_constraint_candidate_source_version
    ON stratum.constraint_candidate(source_version_id);

CREATE INDEX IF NOT EXISTS idx_constraint_candidate_unit
    ON stratum.constraint_candidate(knowledge_unit_id);

CREATE INDEX IF NOT EXISTS idx_constraint_candidate_type
    ON stratum.constraint_candidate(constraint_type);

CREATE INDEX IF NOT EXISTS idx_constraint_candidate_status
    ON stratum.constraint_candidate(status);

CREATE INDEX IF NOT EXISTS idx_constraint_candidate_extractor
    ON stratum.constraint_candidate(extractor_version);

-- Containment lookups for evidence_ids, which carry no foreign key.
CREATE INDEX IF NOT EXISTS idx_constraint_candidate_evidence
    ON stratum.constraint_candidate USING GIN (evidence_ids);

-- ── what the database does and does not guarantee ───────────────────────────
-- Guaranteed here:
--   foreign key integrity (source_version, knowledge_unit)
--   the unit is of the annotation's own source version, via composite keys
--   constraint_type vocabulary, closed to three values
--   status vocabulary, closed, with no VERIFIED / CONFIRMED / APPROVED
--   subject, predicate, object non-empty
--   evidence_ids non-empty
--   replay hash uniqueness
--
-- NOT guaranteed, and not guaranteeable here:
--   that the four quoted fields appear in the evidence span. That is the whole
--   point of this stage and a CHECK cannot state it: it reads another table,
--   which PostgreSQL rejects ("cannot use subquery in check constraint"). The
--   writer refuses any field that is not a literal substring of the span, and
--   quote_authority_gate() is the check that reads that refusal.
--
--   that evidence_ids members are real rows of the same book. TEXT[] carries no
--   foreign key. Enforced in the writer, measured by the traceability gate.
--
--   the state machine. A CHECK cannot compare a column to its own previous
--   value, so a raw UPDATE can still move SUPPORTED back to GENERATED, or
--   REJECTED to SUPPORTED. Enforced in ConstraintWriter.
--
--   constraint_type. The words HARD, SOFT and SELF_DEFINED name how strongly a
--   source binds itself, and a CHECK cannot tell whether the span binds
--   strongly. The writer decides, from the span, and coverage is reported per
--   type so an unexercised type stays visible.
--
-- 081_a_constraint_candidate.sql is applied to a staging database only. It was
-- never executed against a production or development data database.