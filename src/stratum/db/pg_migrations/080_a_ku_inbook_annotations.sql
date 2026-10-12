-- 080: A Repository P8 — in-book annotations over frozen knowledge units
--
-- Rules respected: additive only; never edits migrations 060-079.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: record the *shape* the book gives a knowledge unit at a given
-- place, without ever merging two units.
--
--   ku_occurrence    one place in one book where a unit occurs, with its role
--   ku_relation_hint a dedup hint for B仓 about two occurrences of one unit
--
-- What this migration is FOR, stated plainly, because the previous A仓
-- layers all refused exactly this shape of value:
--
--   A仓 has one row per knowledge unit. It has no record of the same unit
--   being stated as a definition on page 12 and restated as a theorem on
--   page 310, and no record that the book itself signals the two are the
--   same thing. That record is what a reader following the book needs and
--   what B仓 needs before it can decide anything about duplication.
--
-- What this migration is NOT, deliberately:
--
--   It is NOT a merge, a dedup, or a canonicalisation. 076 ruled that an id
--   means one unit; this adds a second *occurrence* of that unit and merges
--   nothing. `ku_occurrence.id` is a fresh composite key, never a pointer
--   that collapses two rows into one.
--
--   It is NOT a semantic judgement recorded as fact. 075 declined to add
--   SAME_MEANING or TENSION, and 079 closed relation_candidate to PRECEDES
--   alone, both with the same reasoning: deciding that two units say the
--   same thing belongs to B仓. So the three kinds in ku_relation_hint are
--   stored as *hints* carrying a confidence, and are exposed to B仓 as
--   dedup candidates. B仓 decides what they mean; A仓 only reports them.
--
-- ── why a separate `ku_occurrence` table and not a column on 073 ────────────
--
-- knowledge_unit is frozen and additive-only forbids an ALTER on it, so the
-- question is where the per-place rows live. A column would be the wrong
-- shape even if it were allowed: one unit restated three times has three
-- occurrences, and a single column cannot hold three. The occurrence is the
-- thing with its own identity, so it gets its own table.
--
-- ── the occurrence key ───────────────────────────────────────────────────────
--
--   occurrence key = kao_<sha256(source_version | unit | locator |
--                                quote_hash | role)[:12]>
--
-- Five parts, and two of them are here because leaving either out was
-- measured against this corpus rather than guessed:
--
--   unit_id. 利率史第一章 has a unit and its own revision both anchored to
--     the same evidence row at the same page, quoting the same span. A key
--     without the unit gives those two the same key, so the second silently
--     overwrites the first and one occurrence disappears -- a merge,
--     performed by a hash collision rather than by a decision. Two frozen
--     units are two units, so the key has to say so.
--
--   role. The same passage re-read and re-labelled is a NEW reading, not an
--     edit of the old one. Without the role in the key the second reading
--     collides with the first, is returned unchanged, and the first reading
--     is what survives -- an observation quietly lost, which is the one thing
--     an append-only stage must never do.
--
-- So the key is NOT the bare `source_version | locator | quote_hash` one might
-- write: the three-part formula folds a unit into its own revision and folds a
-- re-reading back into the reading it replaced. Both are merges, and neither
-- was a decision.
--
-- The source version is in the key for the adjacent reason. The same words at
-- the same position in a later version of the book is a later state of the
-- world, not the same occurrence; a key without it would silently fold two
-- versions together. quote_hash is in the key too, so an occurrence that
-- quotes different words is a different occurrence even at the same place.
--
-- UNIQUE(occurrence_hash) is what makes a rerun a no-op: re-annotating the
-- same passage at the same place with the same role recomputes the same
-- fingerprint and writes nothing.
--
-- ── quote_span is verbatim or it is flagged ─────────────────────────────────
--
-- `quote_status` is LOCATED or UNLOCATED, and `review_required` is the
-- derived queue. An unlocatable span is KEPT, never dropped: dropping an
-- occurrence would be a place in the book that no longer accounts for
-- itself, and the fact that a span could not be verified is exactly what a
-- reviewer needs to see. Rejected alternatives, measured:
--
--   dropping on failure   loses a real occurrence, silently
--   coercing a near match  a span that had to be fuzzed to match is a span
--                          a reader cannot find in the book
--
-- ── same-source enforcement: composite foreign keys, measured ──────────────
--
-- A hint may not cross books. A single-column foreign key does not provide
-- that, and a CHECK cannot read another table, so the two composite-key
-- form 079 already proved is reused:
--
--   CREATE UNIQUE INDEX IF NOT EXISTS knowledge_unit_id_source_version_uniq
--       ON stratum.knowledge_unit (id, source_version_id);
--   FOREIGN KEY (from_unit_id, source_version_id)
--       REFERENCES stratum.knowledge_unit (id, source_version_id)
--
-- That index already exists, applied by 079. Declared again here with
-- IF NOT EXISTS so this migration stands alone; because id is the primary
-- key the pair is already unique, so the index asserts nothing new and
-- cannot fail on existing rows.
--
-- ── the confidence range ────────────────────────────────────────────────────
--
-- A CHECK rather than a nullable column, and both bounds rather than a
-- DEFAULT: a NULL passes every CHECK, and a hint with no confidence is not a
-- weak hint but an unrecorded one. Same finding as the nullable-status and
-- array_length findings in 077 and the P5.2 review.
--
-- ADDITIVE ONLY:
--   two new tables, no existing table altered, no data backfilled, no INSERT
--   of any kind. Rows arrive only through the annotation service.
--
-- Authority chain (080 adds a lookup beside the unit, no new link upward):
--   knowledge_unit <──ku_occurrence── a place in the book
--   knowledge_unit <──ku_relation_hint── another unit of the same book
--
-- Authority priority unchanged: SourceVersion > Evidence > Frozen KU.

-- ── the foreign-key target for the composite keys below ────────────────────
-- Idempotent, and already applied by 079: id is the primary key, so
-- (id, source_version_id) is already unique and this index asserts nothing
-- new about the data. It exists to be a foreign-key target.
--
-- Declared again here so this migration stands alone, and it must come BEFORE
-- the table that references it. Measured on 079's first apply: declared after
-- the CREATE TABLE, PostgreSQL refuses the composite foreign key with
--
--   ERROR: there is no unique constraint matching given keys for referenced
--   table "knowledge_unit"
--
-- and -- because DDL is transactional -- the whole migration rolls back and
-- leaves nothing behind. Which is the good case. The bad case is recording 080
-- in the ledger because the psql wrapper exited zero anyway.
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_unit_id_source_version_uniq
    ON stratum.knowledge_unit (id, source_version_id);

-- ── ku_occurrence ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.ku_occurrence (
    -- The occurrence's own address, content-derived from the pair it
    -- asserts. Distinct from any unit id: a second occurrence of the same
    -- unit is a new row, never a second name for the same one.
    id TEXT PRIMARY KEY,

    -- The book this occurrence belongs to. RESTRICT: an occurrence must not
    -- be able to take its book with it.
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    -- The unit being annotated. RESTRICT, and the unit is never mutated by
    -- this table: an occurrence is a fact about a place, not an edit to the
    -- unit it names.
    unit_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    -- Where in the book. A string rather than an integer, because a locator
    -- may be a page, a section, a clause or a page-and-offset, and the book
    -- supplies whichever one it supplies. Part of the identity, verbatim.
    locator TEXT NOT NULL
        CHECK (length(btrim(locator)) > 0),

    -- The verbatim span this occurrence quotes. Part of the identity, and
    -- never normalised: a normalised span could not be found in the book.
    quote_span TEXT NOT NULL
        CHECK (length(btrim(quote_span)) > 0),

    -- What kind of passage the book is using here. Closed vocabulary. A
    -- role the vocabulary does not name is refused by the writer rather than
    -- coerced to OTHER, so a mislabelled passage stays visible instead of
    -- quietly joining the catch-all.
    role TEXT NOT NULL
        CHECK (role IN (
            'DEFINITION',
            'THEOREM',
            'EXAMPLE',
            'EXERCISE',
            'SUMMARY',
            'ASIDE',
            'OTHER'
        )),

    -- LOCATED or UNLOCATED. Whether the span was found verbatim in the
    -- source text. Never absent: a row with no status would read as
    -- verified, which is the one reading an unverified span must not have.
    quote_status TEXT NOT NULL DEFAULT 'LOCATED'
        CHECK (quote_status IN ('LOCATED', 'UNLOCATED')),

    -- The review queue. True exactly when the span could not be located, and
    -- the reason the occurrence is kept rather than dropped.
    review_required BOOLEAN NOT NULL DEFAULT FALSE,

    -- The replay fingerprint. Covers source, unit, locator, quote and role,
    -- so re-annotating the same passage collides instead of appending, and
    -- the same passage re-labelled is a different row.
    occurrence_hash TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- A rerun over the same occurrence writes nothing.
    CONSTRAINT ku_occurrence_hash_uniq UNIQUE (occurrence_hash),

    -- The same place may not carry two rows for one unit.
    -- The same place, unit and book, read the same way, once. The role is
    -- part of it because a re-reading is a new row, not an edit: the same
    -- passage re-read and re-labelled must be able to coexist with the
    -- reading it replaced, or the append-only rule has no way to record it.
    CONSTRAINT ku_occurrence_place_uniq
        UNIQUE (source_version_id, unit_id, locator, role),

    -- NOT NULL and no transition table: this migration adds an annotation
    -- table, not a lifecycle. quote_status and review_required carry
    -- everything a reader needs about the span's state.
    CONSTRAINT ku_occurrence_review_consistent
        CHECK ((quote_status = 'UNLOCATED') = review_required)
);

-- ── ku_relation_hint ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.ku_relation_hint (
    id TEXT PRIMARY KEY,

    -- The book this hint belongs to. RESTRICT, and it is the book BOTH units
    -- must belong to, enforced by the two composite keys below.
    source_version_id TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    -- The three hint kinds. Closed, and the deferred values are absent from
    -- the CHECK rather than left unused, so a later writer cannot smuggle
    -- DUPLICATE in here through raw SQL and make a hint read as a decision.
    kind TEXT NOT NULL
        CHECK (kind IN (
            'RESTATES',
            'SUMMARIZES',
            'APPLIES'
        )),

    -- The two occurrences, in no particular order. A hint is a symmetric
    -- observation, so the id is derived from the sorted pair and
    -- A-hints-B and B-hints-A are one hint.
    from_unit_id TEXT NOT NULL,
    to_unit_id TEXT NOT NULL,

    -- A reading, not a measurement of fact. Bounded at both ends: a NULL
    -- passes every CHECK, and a hint with no confidence is not a weak hint
    -- but an unrecorded one.
    confidence DOUBLE PRECISION NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- The evidence the hint was read against. An observation with nothing
    -- to point at is an opinion.
    evidence_id TEXT NOT NULL
        REFERENCES stratum.reading_evidence(id) ON DELETE RESTRICT,

    hint_hash TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- A rerun over the same hint writes nothing.
    CONSTRAINT ku_relation_hint_hash_uniq UNIQUE (hint_hash),

    -- One hint per kind per pair: two RESTATES about the same two units is
    -- one observation, not two.
    CONSTRAINT ku_relation_hint_pair_uniq
        UNIQUE (kind, from_unit_id, to_unit_id),

    -- A unit does not hint at itself.
    CONSTRAINT ku_relation_hint_no_self CHECK (from_unit_id <> to_unit_id),

    -- Same-source enforcement, the form 079 proved. Both unit references
    -- carry source_version_id, so a unit from another book cannot satisfy
    -- the key and a cross-book hint is refused by the database rather than
    -- only by the writer.
    CONSTRAINT ku_relation_hint_from_same_source
        FOREIGN KEY (from_unit_id, source_version_id)
        REFERENCES stratum.knowledge_unit (id, source_version_id)
        ON DELETE RESTRICT,
    CONSTRAINT ku_relation_hint_to_same_source
        FOREIGN KEY (to_unit_id, source_version_id)
        REFERENCES stratum.knowledge_unit (id, source_version_id)
        ON DELETE RESTRICT
);

-- ── indexes ─────────────────────────────────────────────────────────────────
-- Every occurrence of one unit, which is what a reader following the unit
-- wants and what a rerun uses to find itself.
CREATE INDEX IF NOT EXISTS idx_ku_occurrence_unit
    ON stratum.ku_occurrence(unit_id);

-- Every occurrence of one book, in the order the book presents them.
CREATE INDEX IF NOT EXISTS idx_ku_occurrence_source
    ON stratum.ku_occurrence(source_version_id);

-- The review queue: every occurrence whose span could not be verified.
CREATE INDEX IF NOT EXISTS idx_ku_occurrence_review
    ON stratum.ku_occurrence(review_required)
    WHERE review_required;

-- How many occurrences carry each role, without scanning the table.
CREATE INDEX IF NOT EXISTS idx_ku_occurrence_role
    ON stratum.ku_occurrence(role);

-- The dedup payload B仓 reads: every hint touching one unit.
CREATE INDEX IF NOT EXISTS idx_ku_relation_hint_from_unit
    ON stratum.ku_relation_hint(from_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_hint_to_unit
    ON stratum.ku_relation_hint(to_unit_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_hint_source
    ON stratum.ku_relation_hint(source_version_id);

CREATE INDEX IF NOT EXISTS idx_ku_relation_hint_kind
    ON stratum.ku_relation_hint(kind);

-- ── what the database does and does not guarantee ───────────────────────────
-- Guaranteed here:
--   foreign key integrity (source_version, knowledge_unit, reading_evidence)
--   same-source enforcement for both units, via composite keys
--   role vocabulary, closed to the seven declared values
--   hint kind vocabulary, closed to the three declared values
--   confidence in [0, 1], both bounds
--   a locator and a quote that are not blank
--   quote_status not absent, and consistent with review_required
--   self-hint exclusion
--   replay identity: one row per occurrence and per hint
--
-- NOT guaranteed, and not guaranteeable here:
--   the role itself. Whether a passage really is a definition is a reading
--   of the book, and no CHECK can make it. Recorded per occurrence, and a
--   mislabelled passage is visible as a row rather than merged away.
--
--   that UNLOCATED is ever resolved. A flagged occurrence stays flagged as
--   long as it is unverified; nothing here moves it to LOCATED except a new
--   annotation row, which is the append-only rule working.
--
--   that B仓 acts on a hint. The hint is a candidate for B仓, which is free
--   to reject every one of them. That freedom is what makes this a hint
--   channel rather than a merge order, and it is enforced by this table
--   having no write path into B仓 at all.
--
-- 080_a_ku_inbook_annotations.sql is applied to a staging database only. It
-- was never executed against a production or development data database.
