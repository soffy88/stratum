-- 076: A Repository P6 — canonical KU identity
--
-- Rules respected: additive only; never edits migrations 060-075.
--   NO DROP. NO ALTER of any existing A table. No data backfill.
-- Re-runnable: every statement is CREATE TABLE IF NOT EXISTS /
-- CREATE INDEX IF NOT EXISTS.
--
-- A仓 scope: end the two-ids-per-unit problem P4.1 documented and could
--   not fix.
--
--   P4    froze    ku_<sha256(statement | evidence_fingerprint)[:12]>
--   P4.1  persisted ku_<sha256(candidate_id | verification_id | content_hash)[:12]>
--
--   All eleven units carry both, and all eleven pairs differ. Anything
--   that cited a P4 id does not match the durable row it was cited for.
--
-- What this migration does NOT do, deliberately:
--   It does not mint a third id. A third formula would be a third id per
--   unit and would invalidate every persisted row and every revision link
--   already written. Canonicalization here is about *resolution*, not
--   about renumbering.
--
--   It does not rewrite knowledge_unit.id. The durable id already binds to
--   the verification that admitted the unit, which is the stronger
--   provenance of the two, and it is already what P4.1 wrote and what P5's
--   revision chain links. So knowledge_unit.id BECOMES the canonical id,
--   and the P4 freeze id becomes a registered alias that resolves to it.
--
-- Why no `ku_canonical` table: the canonical id is already
-- knowledge_unit.id, which is already PRIMARY KEY. A second table
-- asserting the same fact would be a third source of truth for one id —
-- the exact disease this stage exists to cure.
--
-- ADDITIVE ONLY:
--   one new table, no existing table altered, no data backfilled, no
--   INSERT of any kind. Rows arrive only through the identity service.
--
-- Authority chain (076 adds a lookup, no new link upward):
--   knowledge_unit <──ku_identity── legacy id
--
-- Authority priority unchanged: SourceVersion > Evidence > Frozen KU.

-- ── ku_identity ─────────────────────────────────────────────────────────────
-- One row per legacy id, naming the canonical unit it resolves to.
--
-- UNIQUE(alias_id) is the load-bearing constraint in this migration. It is
-- what makes "an id means at most one unit" a database invariant rather than
-- an application convention, and it is the whole of GATE_1: two units
-- claiming the same alias is not a state this table can hold.
--
-- UNIQUE(canonical_ku_id, alias_id) lets one canonical unit accumulate
-- several aliases over time — which is what will be needed if a future
-- stage mints ids under a formula that has to be retired the same way.
--
-- ON DELETE RESTRICT, matching 073 and 074: a unit must not be able to take
-- its own identity with it. Resolving an id after the unit it named is gone
-- would return a dangling answer, and that is precisely when a citation
-- most needs to be checkable.
CREATE TABLE IF NOT EXISTS stratum.ku_identity (
    -- The row's own address, content-derived from the pair it asserts.
    -- Kept distinct from UNIQUE(alias_id) below: `id` addresses a row,
    -- while the constraint is what makes one id mean one unit.
    id TEXT PRIMARY KEY,

    -- The one id. knowledge_unit.id, which is what everything downstream
    -- already cites and what P5's revision chain already links.
    canonical_ku_id TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    -- A retired id that must still resolve. Same `ku_<12 hex>` shape as a
    -- canonical id, so the shape alone tells a reader nothing; only this
    -- table says what an id means.
    alias_id TEXT NOT NULL,

    -- Which formula produced the alias. Closed vocabulary, so reading this
    -- table always names the method rather than leaving it to inference.
    alias_kind TEXT NOT NULL
        CHECK (alias_kind IN (
            'FREEZE_LEGACY'
        )),

    -- What the alias is made of, verbatim. This is what lets a reader
    -- recompute the retired id from the same inputs P4 used, rather than
    -- trusting that this table was populated correctly.
    id_fingerprint TEXT NOT NULL
        CHECK (length(btrim(id_fingerprint)) > 0),

    -- Deterministic fingerprint of this row, so re-registering the same
    -- alias collides and writes nothing instead of appending a second
    -- row with a new fingerprint. UNIQUE(alias_id) would catch the
    -- duplicate too; this makes the collision visible as a fingerprint
    -- match rather than only as a constraint violation.
    identity_hash TEXT NOT NULL,

    identity_version TEXT NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- An id means at most one unit.
    CONSTRAINT ku_identity_alias_uniq UNIQUE (alias_id),

    -- A replay recomputes the same fingerprint, so the same row cannot be
    -- written twice under two ids.
    CONSTRAINT ku_identity_hash_uniq UNIQUE (identity_hash),

    -- The same alias may not be registered twice for one unit either, so a
    -- replay collides here instead of appending a second identical row.
    CONSTRAINT ku_identity_pair_uniq UNIQUE (canonical_ku_id, alias_id),

    -- A unit is not an alias of itself. If the two formulas ever agree for
    -- one unit, that agreement is recorded as "no alias needed", not as a
    -- row asserting a unit answers to itself.
    CONSTRAINT ku_identity_not_self CHECK (canonical_ku_id <> alias_id)
);

-- ── indexes ─────────────────────────────────────────────────────────────────
-- Reverse lookup: given a canonical unit, what retired ids answer to it.
CREATE INDEX IF NOT EXISTS idx_ku_identity_canonical
    ON stratum.ku_identity(canonical_ku_id);

-- Given a retired formula, which units it produced. Lets the alias set be
-- audited per formula rather than only per unit.
CREATE INDEX IF NOT EXISTS idx_ku_identity_kind
    ON stratum.ku_identity(alias_kind);

CREATE INDEX IF NOT EXISTS idx_ku_identity_created_at
    ON stratum.ku_identity(created_at);

-- ── resolution ──────────────────────────────────────────────────────────────
--   citation ──> any id ever issued for a unit
--                  │
--                  ├─ already knowledge_unit.id ──> canonical
--                  │
--                  └─ retired formula ──> ku_identity lookup ──> canonical
--                                                    │
--                                                    └─ no row
--                                                       └─ UNRESOLVED
--                                                      (and the reader is
--                                                       told so, rather than
--                                                       given a guess)
--
-- An UNRESOLVED id is a reportable outcome, not an error to paper over. The
-- stage that introduced an id and the stage that failed to resolve it are
-- both facts worth having.
--
-- What is deliberately absent: no UPDATE path, no DELETE path, and no
-- column on knowledge_unit recording "this is the canonical id". The
-- canonical id is the row's primary key; there is nothing to mark up and
-- nothing to keep in step.
--
-- 076_a_ku_identity.sql is applied to a staging database only. It was never
-- executed against a production or development data database.
