-- 053: Book Understanding 2.0 - P1/P2 Completion (Evidence Trajectory, Multimodal, KU 2.0 Extensions)

-- 1. P1: Multimodal Inventory (VisualSemanticUnit)
CREATE TABLE IF NOT EXISTS stratum.visual_semantic_unit (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    substrate_id TEXT NOT NULL REFERENCES stratum.substrates(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('figure', 'table', 'chart', 'diagram', 'equation')),
    variables_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    entities_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    trends_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    comparisons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    textual_claims_supported JSONB NOT NULL DEFAULT '[]'::jsonb,
    ku_refs TEXT[] NOT NULL DEFAULT '{}',
    argument_refs TEXT[] NOT NULL DEFAULT '{}',
    page_number INTEGER,
    bbox_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_visual_semantic_unit_substrate ON stratum.visual_semantic_unit(substrate_id);

-- 2. P1: Evidence Trajectory
CREATE TABLE IF NOT EXISTS stratum.evidence_trajectory (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES stratum.knowledge_claims(id) ON DELETE CASCADE,
    source_pages JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_regions JSONB NOT NULL DEFAULT '[]'::jsonb,
    extracted_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    ku_refs TEXT[] NOT NULL DEFAULT '{}',
    reasoning_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    final_interpretation TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending' 
        CHECK (verification_status IN ('pending', 'verified', 'failed', 'partially_verified')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_trajectory_claim ON stratum.evidence_trajectory(claim_id);

-- 3. P2: KU 2.0 Ontology Extensions on knowledge_claims
ALTER TABLE stratum.knowledge_claims
    ADD COLUMN IF NOT EXISTS discourse_role TEXT CHECK (discourse_role IN (
        'DEFINITION', 'CLAIM', 'OBSERVATION', 'EVIDENCE', 'EXAMPLE', 'COUNTEREXAMPLE',
        'ASSUMPTION', 'HYPOTHESIS', 'QUALIFICATION', 'EXCEPTION', 'OBJECTION', 
        'REBUTTAL', 'APPLICATION', 'CONCLUSION', 'QUESTION'
    )),
    ADD COLUMN IF NOT EXISTS argument_role TEXT,
    ADD COLUMN IF NOT EXISTS epistemic_role TEXT CHECK (epistemic_role IN (
        'AUTHOR_ASSERTED', 'AUTHOR_HYPOTHESIZED', 'QUOTED_POSITION', 
        'HISTORICAL_POSITION', 'OPPONENT_POSITION', 'AUTHOR_REJECTED'
    )),
    ADD COLUMN IF NOT EXISTS speaker TEXT,
    ADD COLUMN IF NOT EXISTS modality TEXT,
    ADD COLUMN IF NOT EXISTS quantifier TEXT,
    ADD COLUMN IF NOT EXISTS scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS qualifiers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS exceptions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS mechanism_ref TEXT,
    ADD COLUMN IF NOT EXISTS grounding_status TEXT NOT NULL DEFAULT 'unverified',
    ADD COLUMN IF NOT EXISTS context_status TEXT NOT NULL DEFAULT 'unverified',
    ADD COLUMN IF NOT EXISTS extraction_run_id TEXT;
