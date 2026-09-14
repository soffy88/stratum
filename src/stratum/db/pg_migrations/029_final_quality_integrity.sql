-- 029: close two data-integrity gaps exposed by the final product-quality gate.
-- Active concepts are owner/name/type identities; invalid evidence cannot point
-- at a non-existent substrate.  The cleanup is deliberately narrow and
-- idempotent, while the partial unique index protects future concurrent writes.

CREATE TABLE IF NOT EXISTS stratum.evidence (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_highlight_id TEXT,
    substrate_id TEXT NOT NULL,
    quote TEXT NOT NULL,
    quote_hash TEXT NOT NULL,
    locator_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stratum.knowledge_claims (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'hypothesis',
    confidence DOUBLE PRECISION,
    concept_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stratum.claim_evidence (
    claim_id TEXT NOT NULL REFERENCES stratum.knowledge_claims(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES stratum.evidence(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'supports',
    PRIMARY KEY (claim_id, evidence_id)
);

WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY user_id, lower(trim(name)), type
               ORDER BY created_at, id
           ) AS rn
    FROM stratum.concepts
    WHERE deleted_at IS NULL
)
UPDATE stratum.concepts c
SET deleted_at = NOW()
FROM ranked r
WHERE c.id = r.id AND r.rn > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_concepts_owner_name_type_active
    ON stratum.concepts (user_id, lower(trim(name)), type)
    WHERE deleted_at IS NULL;

DELETE FROM stratum.evidence e
WHERE NOT EXISTS (
    SELECT 1 FROM stratum.substrates s WHERE s.id = e.substrate_id
)
AND NOT EXISTS (
    SELECT 1 FROM stratum.claim_evidence ce WHERE ce.evidence_id = e.id
);
