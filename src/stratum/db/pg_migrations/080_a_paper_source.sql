-- 080: A Repository P5.3 — paper / source metadata annotation
--
-- Rules respected: additive only; never edits migrations 060-079.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: persist a *source annotation candidate* — what a source record
-- declares about itself — plus the record that made each declaration.
--
--   paper_source_candidate ──> source_version ──> book_source
--   paper_evidence        ──> paper_source_candidate
--                        └──> book_source   (the declaring record)
--
-- Nothing else. No BU2, no B仓, no C仓. A source annotation records what a
-- record says about a source. It never says whether that source is good.
--
-- ── what this is not, and why it is smaller than the review spec ────────────
--
-- The review spec proposed a paper table keyed on the book's own metadata and
-- evidence attached as TEXT[] spans of reading_evidence. Measured against the
-- frozen corpus, that could not have been built honestly:
--
--   reading_evidence          17 rows, 671 characters total
--   occurrences of 霍默 / 理查德 (the authors)      0
--   occurrences of 中信 (the publisher)              0
--   occurrences of 9787 (the ISBN)                  0
--   occurrences of any 4-digit year                 0
--   occurrences of 作者 / 出版 / 译者 / 版权           0
--
-- The bibliographic data exists in exactly one place: the book_source catalog
-- row. Ingestion covered chapter-1 body text — no title page, no copyright
-- page. So all five statement_type values (AUTHOR, TITLE, PUBLICATION, YEAR,
-- IDENTIFIER) had no span that declared them, and attaching a span anyway
-- would have made traceability=100% a fabrication rather than a measurement.
--
-- So the evidence here is the catalog record itself, referenced by foreign key,
-- and every declared_value is checked against the field it claims to come from.
-- A declaration that does not match its record cannot be written. "The source
-- declares author X" becomes a fact about a row, not a hope about a span.
--
-- LIMITATION, frozen: *declaration by text span is untested*, because no span
-- in this corpus declares source metadata. The vocabulary below leaves room for
-- TITLE_PAGE and COPYRIGHT_PAGE so that ingesting front matter later has
-- somewhere to record provenance, but neither is exercised now.
--
-- ── relationship to the frozen 075 relation layer ───────────────────────────
--
-- stratum.ku_relation (075) stores undirected machine-comparable facts between
-- two units and is left untouched. Nothing in 080 touches it: a source
-- annotation is about a source, not about a pair of rows.
--
-- ── deviations from the review spec v1.0, all decided in the schema review ──
--
-- 1. evidence_hash UNIQUE on paper_evidence, and cardinality >= 1.
--    The spec declared no uniqueness at all on paper_evidence. Without a
--    replay key, (paper_id, statement_type) can grow without bound and a
--    re-run cannot tell an already-stored declaration from a new one. 077-079
--    each carry a UNIQUE fingerprint for the same reason.
--
-- 2. paper_evidence declares catalog_source_id (FK) and declared_in, instead of
--    a TEXT[] span array. This is the F1 decision: the evidence is the catalog
--    row. See above for the measurement.
--
-- 3. publisher is inside paper_hash. The spec's §5 formula listed doi and isbn
--    but not publisher, so changing the publisher would not change the hash —
--    the opposite of every A table from 077 on, where the fingerprint covers
--    the row's identity fields.
--
-- 4. evidence is deliberately NOT inside paper_hash. It is an append-only layer
--    under the candidate, keyed by evidence_hash. The spec's §5 omitted
--    evidence while its §9 listed evidence as part of the replay key; this
--    resolves that contradiction in favour of §5, and says so out loud: new
--    evidence for the same source is new *evidence*, not a new *source*.
--
-- 5. book_source_id is a foreign key. The spec listed no FK to book_source,
--    while duplicating its title / publisher / isbn verbatim. Without the FK,
--    editing book_source would silently leave this candidate stale, with
--    nothing able to detect it.
--
-- 6. authors is NOT sorted before hashing. Author order carries meaning — first
--    author, corresponding author — so normalising it away would destroy a
--    fact. evidence ids under 080 are declared_in the catalog row, and the
--    evidence_hash below sorts only its own catalog reference.
--
-- ── the composite key: this candidate's catalog row must be its own ─────────
--
-- A candidate names both a source_version and a book_source_id. Nothing in the
-- spec tied them together, and the same lie was measured against 079: both
-- references individually valid, together describing two different books.
--
-- source_version carries book_source_id, so the tie is expressible:
--
--   CREATE UNIQUE INDEX source_version_id_book_source_uniq
--       ON stratum.source_version (id, book_source_id);
--   FOREIGN KEY (source_version_id, book_source_id)
--       REFERENCES stratum.source_version (id, book_source_id)
--
-- (id, book_source_id) is already unique because id is the primary key, so the
-- index asserts nothing new and cannot fail on existing rows. It exists to be a
-- foreign-key target and costs write amplification only. No row, column or
-- value in source_version is touched.
--
-- The alternative — a BEFORE INSERT trigger — was rejected: A仓 has no trigger
-- or function anywhere in 070-079.

-- ── foreign-key targets, declared before the tables that need them ──────────
-- Measured on the first apply of 079: with the index declared after the CREATE
-- TABLE, PostgreSQL refuses the composite key with "there is no unique
-- constraint matching given keys". DDL is transactional so the migration rolls
-- back cleanly, but the psql wrapper still exits zero — which is how a false
-- ledger entry gets written. The order here is load-bearing.
CREATE UNIQUE INDEX IF NOT EXISTS source_version_id_book_source_uniq
    ON stratum.source_version (id, book_source_id);

-- ── paper_source_candidate ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stratum.paper_source_candidate (
    id TEXT PRIMARY KEY,

    -- The version this annotation is about. RESTRICT: an annotation must not be
    -- able to take its source with it.
    source_version_id TEXT NOT NULL,
    book_source_id TEXT NOT NULL,

    -- What kind of source this is. UNKNOWN is absent by design: an unreadable
    -- source is a read state, not a fact about the world, and writing it here
    -- would let "we could not tell" masquerade as "it is a book".
    source_type TEXT NOT NULL
        CHECK (source_type IN (
            'BOOK', 'PAPER', 'ARTICLE', 'REPORT', 'ARCHIVE'
        )),

    -- What the record declares about itself. Not what is true of it.
    title TEXT NOT NULL,

    -- The author field as the record states it. cardinality, not array_length:
    -- measured in 077, array_length of an empty array is NULL and a CHECK passes
    -- on NULL, so an array_length guard accepts the empty array it exists to
    -- reject.
    --
    -- One element for this corpus. Splitting "[美]悉尼·霍默 理查德·西勒" into
    -- two names is author identity resolution, which LIMITATION-2 puts out of
    -- scope, so it is not done here.
    authors TEXT[] NOT NULL
        CHECK (cardinality(authors) >= 1),

    -- Nullable, and NULL in this corpus: measured, A仓 holds no publication
    -- year and no DOI anywhere. Not invented to fill a column.
    publication_year INTEGER,
    publisher TEXT,
    doi TEXT,
    isbn TEXT,

    -- The replay identity. Covers source version, catalog row, source type and
    -- every declared field including publisher, plus the extractor version.
    -- Evidence is deliberately not included — see deviation 4.
    paper_hash TEXT NOT NULL,

    -- 'paper_extractor_v1' for a real extraction, 'pilot-declared' for the
    -- pilot. Never interchangeable: a pilot row is not evidence that an
    -- extractor works.
    extractor_version TEXT NOT NULL,

    -- GENERATED -> SUPPORTED | REJECTED, and no edge leaves either. No VERIFIED
    -- and no APPROVED: VERIFIED is the success value of
    -- ku_verification.verification_status, and APPROVED would be a second word
    -- for the same judgement.
    status TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (status IN ('GENERATED', 'SUPPORTED', 'REJECTED')),

    created_at TIMESTAMP NOT NULL DEFAULT now(),

    CONSTRAINT paper_candidate_hash_uniq UNIQUE (paper_hash),

    -- The catalog row this annotation is about must be the catalog row its own
    -- source version was ingested from. Without this, a candidate could name a
    -- version of one book and the catalog record of another.
    CONSTRAINT paper_candidate_same_source
        FOREIGN KEY (source_version_id, book_source_id)
        REFERENCES stratum.source_version (id, book_source_id)
        ON DELETE RESTRICT,

    -- Declared separately from the inline reference above so both are visible:
    -- the book itself must exist, independently of the version tie.
    CONSTRAINT paper_candidate_book_fkey
        FOREIGN KEY (book_source_id)
        REFERENCES stratum.book_source (id) ON DELETE RESTRICT
);

-- ── paper_evidence ──────────────────────────────────────────────────────────
-- One declaration made by a record.
--
-- Not a span of reading_evidence, because no span in this corpus declares
-- source metadata — measured, zero occurrences of the author, the publisher,
-- the ISBN or any year across all 671 characters. declared_value is instead
-- checked against the field it claims to come from, by the writer, so a
-- declaration that does not match its record cannot be stored.
CREATE TABLE IF NOT EXISTS stratum.paper_evidence (
    id TEXT PRIMARY KEY,

    paper_id TEXT NOT NULL
        REFERENCES stratum.paper_source_candidate(id) ON DELETE RESTRICT,

    -- What kind of declaration this is. YEAR is in the vocabulary and is not
    -- exercised: the catalog row has no year field, so there is nothing to
    -- declare and nothing to check a declaration against.
    statement_type TEXT NOT NULL
        CHECK (statement_type IN (
            'AUTHOR', 'TITLE', 'PUBLICATION', 'YEAR', 'IDENTIFIER'
        )),

    -- The value exactly as the declaring record states it. Not normalised, not
    -- translated, not split.
    declared_value TEXT NOT NULL,

    -- Which kind of record made the declaration. BOOK_SOURCE_CATALOG is the
    -- only one this corpus can supply; the other three name where a title page,
    -- copyright page or CIP record would be recorded if front matter were ever
    -- ingested, and none of them is exercised now.
    declared_in TEXT NOT NULL
        CHECK (declared_in IN (
            'BOOK_SOURCE_CATALOG', 'TITLE_PAGE', 'COPYRIGHT_PAGE', 'CIP_RECORD'
        )),

    -- The declaring record itself. This is the evidence reference, and it is a
    -- foreign key rather than an opaque string, so "the evidence exists" is
    -- enforced by the database instead of asserted by the writer.
    catalog_source_id TEXT NOT NULL
        REFERENCES stratum.book_source (id) ON DELETE RESTRICT,

    -- Replay identity for the declaration. Sorts its own catalog reference, so
    -- a re-run writes nothing.
    evidence_hash TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT now(),

    CONSTRAINT paper_evidence_hash_uniq UNIQUE (evidence_hash)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_paper_candidate_source_version
    ON stratum.paper_source_candidate(source_version_id);

CREATE INDEX IF NOT EXISTS idx_paper_candidate_book_source
    ON stratum.paper_source_candidate(book_source_id);

CREATE INDEX IF NOT EXISTS idx_paper_candidate_source_type
    ON stratum.paper_source_candidate(source_type);

CREATE INDEX IF NOT EXISTS idx_paper_candidate_status
    ON stratum.paper_source_candidate(status);

CREATE INDEX IF NOT EXISTS idx_paper_candidate_extractor
    ON stratum.paper_source_candidate(extractor_version);

CREATE INDEX IF NOT EXISTS idx_paper_candidate_authors
    ON stratum.paper_source_candidate USING GIN (authors);

CREATE INDEX IF NOT EXISTS idx_paper_evidence_paper
    ON stratum.paper_evidence(paper_id);

CREATE INDEX IF NOT EXISTS idx_paper_evidence_statement_type
    ON stratum.paper_evidence(statement_type);

-- ── what the database does and does not guarantee ───────────────────────────
-- Guaranteed here:
--   foreign key integrity (source_version, book_source, candidate)
--   the candidate's catalog row is the one its version was ingested from
--   source_type vocabulary, closed, with no UNKNOWN
--   status vocabulary, closed, with no VERIFIED and no APPROVED
--   authors non-empty
--   declared_value non-empty by NOT NULL
--   statement_type and declared_in vocabularies, closed
--   replay uniqueness for both the candidate and the declaration
--
-- NOT guaranteed, and not guaranteeable here:
--   the state machine. A CHECK cannot compare a column to its own previous
--   value, so a raw UPDATE can still move SUPPORTED back to GENERATED, or
--   REJECTED to SUPPORTED. Enforced in PaperWriter.
--
--   that declared_value is what the catalog record actually says. The foreign
--   key proves the record exists; it cannot prove the sentence about it is
--   true. That comparison is the writer's, and it is the traceability gate.
--
--   publication_year sanity. The column is an unbounded INTEGER because A仓
--   holds no year to check it against, and inventing a bound would be
--   inventing a fact. Frozen as a known limitation.
--
-- 080_a_paper_source.sql is applied to a staging database only. It was never
-- executed against a production or development data database.