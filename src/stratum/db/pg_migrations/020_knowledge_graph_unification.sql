-- 020: unify concepts, relations, claims, and portable Evidence ownership.
-- Existing concepts/highlights/graph_* tables remain readable; these tables are
-- the canonical cross-object links used by the Knowledge API.

CREATE TABLE IF NOT EXISTS stratum.evidence (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL,
    source_highlight_id TEXT,
    substrate_id        TEXT NOT NULL,
    quote               TEXT NOT NULL,
    quote_hash          TEXT NOT NULL,
    locator_json        JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 1.0
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_source_highlight
    ON stratum.evidence (source_highlight_id)
    WHERE source_highlight_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evidence_user_substrate
    ON stratum.evidence (user_id, substrate_id);

CREATE TABLE IF NOT EXISTS stratum.knowledge_claims (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    statement   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'unverified'
        CHECK (status IN ('unverified', 'verified', 'contradicted', 'refuted')),
    confidence  DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    concept_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_claims_user_status
    ON stratum.knowledge_claims (user_id, status);

CREATE TABLE IF NOT EXISTS stratum.claim_evidence (
    claim_id    TEXT NOT NULL REFERENCES stratum.knowledge_claims(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES stratum.evidence(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL DEFAULT 'supports'
        CHECK (relation IN ('supports', 'contradicts', 'qualifies')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS stratum.concept_relations (
    id                TEXT PRIMARY KEY,
    user_id           TEXT NOT NULL,
    source_concept_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    relation_type     TEXT NOT NULL,
    confidence        DOUBLE PRECISION NOT NULL DEFAULT 0.5
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    rationale         TEXT,
    evidence_ids      TEXT[] NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, source_concept_id, target_concept_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_concept_relations_source
    ON stratum.concept_relations (user_id, source_concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_relations_target
    ON stratum.concept_relations (user_id, target_concept_id);

-- Backfill first-class Evidence from upgraded highlight records.
INSERT INTO stratum.evidence (
    id, user_id, source_highlight_id, substrate_id, quote, quote_hash,
    locator_json, confidence, created_at, updated_at
)
SELECT h.id, h.user_id, h.id, h.substrate_id, h.text,
       -- md5 is only a migration fallback for legacy rows; all new API writes
       -- use the canonical SHA-256 quote hash.
       COALESCE(h.quote_hash, md5(COALESCE(h.text, ''))),
       COALESCE(h.locator_json, h.location_json, '{}'::jsonb),
       COALESCE(h.confidence, 1.0), COALESCE(h.created_at, NOW()),
       COALESCE(h.updated_at, h.created_at, NOW())
FROM stratum.highlights h
WHERE h.text IS NOT NULL
ON CONFLICT (id) DO NOTHING;
