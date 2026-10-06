-- 068_bu2_p12_reasoning_graph.sql
--
-- P12 §9: a book understanding gains a reasoning graph, a concept evolution
-- record and an argument graph, each referenced by id from
-- book_understandings_v2.
--
-- §2.1 forbids these becoming a knowledge base. They are book-specific: every
-- table carries run_id, and nothing is keyed by a global concept identity. A
-- concept node means "this concept, in this book, at this chapter" and nothing
-- more, which is what keeps B仓 separate from BU2.
--
-- §15 forbids silent drops, so each graph stores its own unresolved records:
-- a proposed relation the evidence did not support is kept, with its reason,
-- its confidence and status='uncertain', rather than discarded.
--
-- ADDITIVE ONLY: creates four tables and three columns. No DROP, no DELETE, no
-- rewrite of existing rows. Existing BUs keep NULL graph ids, which reads as
-- "produced before P12" rather than as missing data.

-- ── reasoning graph ─────────────────────────────────────────────────────────
-- One graph per run. Nodes and edges are rows rather than jsonb so a relation
-- can be counted, queried and gated independently.

CREATE TABLE IF NOT EXISTS stratum.book_reasoning_graph (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL
        REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    book_id           TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    node_count        INTEGER NOT NULL DEFAULT 0,
    edge_count        INTEGER NOT NULL DEFAULT 0,
    unresolved_count  INTEGER NOT NULL DEFAULT 0,
    mean_confidence   DOUBLE PRECISION NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_reasoning_graph_run
    ON stratum.book_reasoning_graph (run_id);

-- §5.2 node vocabulary: CHAPTER, CONCEPT, CLAIM, MECHANISM, QUESTION, EXAMPLE,
-- CONCLUSION. Constrained rather than free text, so a typo becomes a failed
-- insert instead of a seventh node type nobody can query.
CREATE TABLE IF NOT EXISTS stratum.reasoning_node (
    id            TEXT PRIMARY KEY,
    graph_id      TEXT NOT NULL
        REFERENCES stratum.book_reasoning_graph(id) ON DELETE CASCADE,
    node_type     TEXT NOT NULL CHECK (node_type IN (
        'CHAPTER', 'CONCEPT', 'CLAIM', 'MECHANISM', 'QUESTION', 'EXAMPLE', 'CONCLUSION'
    )),
    label         TEXT NOT NULL,
    chapter_id    TEXT,
    source_ref    TEXT,
    confidence    DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_reasoning_node_graph ON stratum.reasoning_node (graph_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_node_type ON stratum.reasoning_node (graph_id, node_type);
CREATE INDEX IF NOT EXISTS idx_reasoning_node_chapter ON stratum.reasoning_node (chapter_id);

-- §5.2 edge vocabulary: DEPENDS_ON, EXTENDS, REFINES, CONTRADICTS, APPLIES_TO,
-- EXPLAINS, SUPPORTS.
--
-- §6 requires every dependency edge to carry a reason and evidence, and §15
-- forbids a model from producing one without them. reason and evidence_refs are
-- therefore NOT NULL here, not merely expected by convention: a dependency edge
-- without a stated reason cannot be written at all.
CREATE TABLE IF NOT EXISTS stratum.reasoning_edge (
    id             TEXT PRIMARY KEY,
    graph_id       TEXT NOT NULL
        REFERENCES stratum.book_reasoning_graph(id) ON DELETE CASCADE,
    source_node_id TEXT NOT NULL
        REFERENCES stratum.reasoning_node(id) ON DELETE CASCADE,
    target_node_id TEXT NOT NULL
        REFERENCES stratum.reasoning_node(id) ON DELETE CASCADE,
    relation_type  TEXT NOT NULL CHECK (relation_type IN (
        'DEPENDS_ON', 'EXTENDS', 'REFINES', 'CONTRADICTS',
        'APPLIES_TO', 'EXPLAINS', 'SUPPORTS'
    )),
    reason         TEXT NOT NULL,
    evidence_refs  TEXT[] NOT NULL DEFAULT '{}',
    -- §11: how strong the evidence is. MODEL_INFERENCE is the weakest and is
    -- recorded explicitly rather than presented as DIRECT.
    evidence_type  TEXT NOT NULL DEFAULT 'MODEL_INFERENCE' CHECK (evidence_type IN (
        'DIRECT', 'DEFINITION', 'EXAMPLE', 'DERIVED', 'MODEL_INFERENCE'
    )),
    confidence     DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status         TEXT NOT NULL DEFAULT 'asserted' CHECK (status IN (
        'asserted', 'uncertain', 'refuted'
    )),
    UNIQUE (graph_id, source_node_id, target_node_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_reasoning_edge_graph ON stratum.reasoning_edge (graph_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_edge_source ON stratum.reasoning_edge (source_node_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_edge_relation ON stratum.reasoning_edge (graph_id, relation_type);

-- §15: a relation the evidence did not support is kept, not dropped. This is
-- the record of what was proposed and why it was not asserted.
CREATE TABLE IF NOT EXISTS stratum.reasoning_unresolved (
    id           TEXT PRIMARY KEY,
    graph_id     TEXT NOT NULL
        REFERENCES stratum.book_reasoning_graph(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    subject      TEXT NOT NULL,
    reason       TEXT NOT NULL,
    source       TEXT NOT NULL,
    confidence   DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    fallback     TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reasoning_unresolved_graph
    ON stratum.reasoning_unresolved (graph_id);

-- ── §9: concept evolution ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stratum.concept_trajectory (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL
        REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    book_id           TEXT NOT NULL,
    -- §2.1: book-scoped, not a canonical concept identity.
    concept_label     TEXT NOT NULL,
    introduced_at     TEXT,
    final_state       TEXT,
    definition_count  INTEGER NOT NULL DEFAULT 0,
    change_count      INTEGER NOT NULL DEFAULT 0,
    application_count INTEGER NOT NULL DEFAULT 0,
    confidence        DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    UNIQUE (run_id, concept_label)
);

CREATE INDEX IF NOT EXISTS idx_concept_trajectory_run
    ON stratum.concept_trajectory (run_id);

-- §7.3: a trajectory records Introduction, Refinement, Expansion, Connection.
CREATE TABLE IF NOT EXISTS stratum.concept_trajectory_event (
    id            TEXT PRIMARY KEY,
    trajectory_id TEXT NOT NULL
        REFERENCES stratum.concept_trajectory(id) ON DELETE CASCADE,
    event_type    TEXT NOT NULL CHECK (event_type IN (
        'INTRODUCTION', 'REFINEMENT', 'EXPANSION', 'CONNECTION'
    )),
    chapter_id    TEXT,
    detail        TEXT NOT NULL,
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    confidence    DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    -- document order within the book, so a trajectory reads in sequence
    sequence      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_trajectory_event_parent
    ON stratum.concept_trajectory_event (trajectory_id, sequence);

-- ── §8: argument graph ──────────────────────────────────────────────────────
-- Author reasoning chains: CLAIM / EVIDENCE / REASONING / CONCLUSION nodes and
-- SUPPORTS / DERIVES / CHALLENGES / SUMMARIZES edges. Kept in its own table
-- rather than folded into the reasoning graph, because a reasoning chain is a
-- different question from a structural relation and §8 asks for it separately.

CREATE TABLE IF NOT EXISTS stratum.argument_graph (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL
        REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    book_id         TEXT NOT NULL,
    chain_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_argument_graph_run ON stratum.argument_graph (run_id);

CREATE TABLE IF NOT EXISTS stratum.argument_node (
    id          TEXT PRIMARY KEY,
    graph_id    TEXT NOT NULL
        REFERENCES stratum.argument_graph(id) ON DELETE CASCADE,
    node_type   TEXT NOT NULL CHECK (node_type IN (
        'CLAIM', 'EVIDENCE', 'REASONING', 'CONCLUSION'
    )),
    label       TEXT NOT NULL,
    chapter_id  TEXT,
    confidence  DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_argument_node_graph ON stratum.argument_node (graph_id);

CREATE TABLE IF NOT EXISTS stratum.argument_edge (
    id             TEXT PRIMARY KEY,
    graph_id       TEXT NOT NULL
        REFERENCES stratum.argument_graph(id) ON DELETE CASCADE,
    source_node_id TEXT NOT NULL
        REFERENCES stratum.argument_node(id) ON DELETE CASCADE,
    target_node_id TEXT NOT NULL
        REFERENCES stratum.argument_node(id) ON DELETE CASCADE,
    relation_type  TEXT NOT NULL CHECK (relation_type IN (
        'SUPPORTS', 'DERIVES', 'CHALLENGES', 'SUMMARIZES'
    )),
    reason         TEXT NOT NULL,
    evidence_refs  TEXT[] NOT NULL DEFAULT '{}',
    confidence     DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    chain_id       TEXT
);

CREATE INDEX IF NOT EXISTS idx_argument_edge_graph ON stratum.argument_edge (graph_id);
CREATE INDEX IF NOT EXISTS idx_argument_edge_chain ON stratum.argument_edge (chain_id);

-- ── §9: the three ids on the BU ─────────────────────────────────────────────
-- Nullable on purpose: a BU produced before P12 has NULL here, which reads as
-- "produced before P12" rather than as corruption.

ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS reasoning_graph_id TEXT;

ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS concept_evolution_id TEXT;

ALTER TABLE stratum.book_understandings_v2
    ADD COLUMN IF NOT EXISTS argument_graph_id TEXT;

-- §11: a claim must bind an evidence strength. Recorded on the understanding so
-- the binding is checkable rather than assumed.
ALTER TABLE stratum.chapter_understandings
    ADD COLUMN IF NOT EXISTS evidence_strengths JSONB NOT NULL DEFAULT '{}'::jsonb;