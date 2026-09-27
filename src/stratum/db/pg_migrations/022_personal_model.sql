-- 022: minimum multi-user Personal Model in the authenticated Stratum store.
--
-- cx.learning_* remains in the separate aii_context database and is not
-- silently rewritten here.  These tables are the new cross-object write path
-- for Stratum users; object_id is an application-level reference because some
-- targets live in other namespaces.

CREATE TABLE IF NOT EXISTS stratum.personal_states (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    object_type     TEXT NOT NULL CHECK (
        object_type IN ('claim', 'evidence', 'concept', 'substrate', 'note', 'highlight')
    ),
    object_id       TEXT NOT NULL,
    mastery         DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (mastery >= 0.0 AND mastery <= 1.0),
    interest        DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (interest >= 0.0 AND interest <= 1.0),
    certainty       DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (certainty >= 0.0 AND certainty <= 1.0),
    relevance       DOUBLE PRECISION NOT NULL DEFAULT 0.0
        CHECK (relevance >= 0.0 AND relevance <= 1.0),
    source          TEXT NOT NULL DEFAULT 'explicit' CHECK (
        source IN ('explicit', 'inferred', 'imported')
    ),
    source_event_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (user_id, object_type, object_id)
);

CREATE INDEX IF NOT EXISTS idx_personal_states_user_updated
    ON stratum.personal_states (user_id, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_personal_states_object
    ON stratum.personal_states (object_type, object_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS stratum.beliefs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    claim_id        TEXT NOT NULL REFERENCES stratum.knowledge_claims(id) ON DELETE CASCADE,
    stance          TEXT NOT NULL CHECK (
        stance IN ('agree', 'disagree', 'uncertain', 'conditional')
    ),
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source          TEXT NOT NULL DEFAULT 'user' CHECK (
        source IN ('user', 'inferred', 'imported')
    ),
    source_event_id TEXT,
    rationale       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (user_id, claim_id)
);

CREATE INDEX IF NOT EXISTS idx_beliefs_user_updated
    ON stratum.beliefs (user_id, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_beliefs_claim
    ON stratum.beliefs (claim_id)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS stratum.context_links (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    object_type     TEXT NOT NULL CHECK (
        object_type IN ('claim', 'evidence', 'concept', 'substrate', 'note', 'highlight')
    ),
    object_id       TEXT NOT NULL,
    context_type    TEXT NOT NULL CHECK (context_type IN ('project', 'goal', 'tag', 'area')),
    context_id      TEXT NOT NULL,
    weight          DOUBLE PRECISION NOT NULL DEFAULT 1.0
        CHECK (weight >= 0.0 AND weight <= 1.0),
    source          TEXT NOT NULL DEFAULT 'explicit' CHECK (
        source IN ('explicit', 'inferred', 'imported')
    ),
    source_event_id TEXT,
    rationale       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (user_id, object_type, object_id, context_type, context_id)
);

CREATE INDEX IF NOT EXISTS idx_context_links_user_context
    ON stratum.context_links (user_id, context_type, context_id)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_context_links_object
    ON stratum.context_links (object_type, object_id)
    WHERE deleted_at IS NULL;
