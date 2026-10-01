-- 054: Book Understanding 2.0 - P3 Explanation Structure (Argument, Mechanism, SituationModel, UnderstandingFrontier)

-- 1. Argument
CREATE TABLE IF NOT EXISTS stratum.arguments (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    premises_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warrants_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    inference_steps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    objections_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    rebuttals_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    qualifiers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    conclusion JSONB NOT NULL DEFAULT '[]'::jsonb,
    ku_refs TEXT[] NOT NULL DEFAULT '{}',
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arguments_run ON stratum.arguments(run_id);

-- 2. AuthorMechanism
CREATE TABLE IF NOT EXISTS stratum.author_mechanisms (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    trigger_event TEXT NOT NULL,
    actors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    variables_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    inputs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mediators_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    state_changes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    outputs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    exceptions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    failure_conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ku_refs TEXT[] NOT NULL DEFAULT '{}',
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    explicitness TEXT NOT NULL CHECK (explicitness IN ('EXPLICIT', 'IMPLICIT', 'DERIVED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_author_mechanisms_run ON stratum.author_mechanisms(run_id);

-- 3. SituationModel
CREATE TABLE IF NOT EXISTS stratum.situation_models (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    entities_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    states_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    variables_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    causal_links_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    temporal_links_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mechanism_refs TEXT[] NOT NULL DEFAULT '{}',
    constraints_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    boundary_conditions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_situation_models_run ON stratum.situation_models(run_id);

-- 4. UnderstandingFrontier
CREATE TABLE IF NOT EXISTS stratum.understanding_frontiers (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN (
        'CLAIM_AWAITING_EVIDENCE', 'QUESTION_AWAITING_ANSWER', 
        'CONCEPT_AWAITING_DEFINITION', 'MECHANISM_AWAITING_COMPLETION', 
        'OBJECTION_AWAITING_REBUTTAL', 'REFERENCE_AWAITING_EXPLANATION', 
        'PROMISE_AWAITING_FULFILLMENT'
    )),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN (
        'OPEN', 'RESOLVED', 'SUPPORTED', 'QUALIFIED', 'REVISED', 'CONTRADICTED', 'REJECTED'
    )),
    resolution_refs TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_understanding_frontiers_run ON stratum.understanding_frontiers(run_id);
