-- 091_bu2_learning_guide_cache.sql
-- Traceability: the dependency-ordered learning guide is derived from the
-- reasoning graph, which is expensive to rebuild (nodes + edges + a topological
-- sort) and stable for the life of a run. Computing it on every request meant a
-- book with 1000 concept nodes re-derived the whole ordering per page load.
--
-- Keyed by (run_id, graph_version) on purpose: a graph rebuild produces new node
-- ids and edges, so a cache keyed on run_id alone would serve a guide built from
-- a graph the run no longer has. graph_version is part of the identity, and a
-- rebuild is a cache miss rather than a stale hit. The row is a cache, never an
-- authority: the guide is recomputed from the database if the row is absent or
-- the version differs, so deleting every row is safe.
--
-- Additive and idempotent. No existing row or table is touched.

CREATE TABLE IF NOT EXISTS stratum.bu2_learning_guide (
    run_id         TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    -- The reasoning graph the guide was built from. A rebuild changes the version,
    -- which is what invalidates this row.
    graph_version  TEXT NOT NULL,
    book_id        TEXT,
    -- The rendered guide: steps, by_chapter and cycles, exactly the shape the
    -- API returns.
    payload        JSONB NOT NULL,
    step_count     INTEGER NOT NULL DEFAULT 0,
    -- book_understandings_v2.reasoning_graph_id as of this build. Not a foreign key:
    -- graph ids are reset on rebuild and the cache is keyed by version, so a stale
    -- id here must not fail the insert.
    graph_id       TEXT,
    engine_version TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, graph_version)
);

CREATE INDEX IF NOT EXISTS idx_bu2_learning_guide_run
    ON stratum.bu2_learning_guide (run_id, created_at DESC);

-- A rebuild replaces the newest version, so run+version lookups are the hot path
-- and need no second index beyond the primary key; this one exists for the
-- "latest version for this run" query that does not know the version yet.
CREATE INDEX IF NOT EXISTS idx_bu2_learning_guide_latest
    ON stratum.bu2_learning_guide (run_id, graph_version DESC);
