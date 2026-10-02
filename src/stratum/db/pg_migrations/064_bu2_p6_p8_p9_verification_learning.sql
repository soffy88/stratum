-- 056: Book Understanding 2.0 - P6 Verification and P8/P9 Learning

-- P6: UnderstandingGap
CREATE TABLE IF NOT EXISTS stratum.understanding_gaps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN (
        'MISSING_KU', 'BAD_BOUNDARY', 'MISSING_CONTEXT', 'STANCE_ERROR', 'SCOPE_ERROR', 
        'MISSING_EVIDENCE', 'ARGUMENT_GAP', 'MECHANISM_GAP', 'CONCEPT_GAP', 
        'CROSS_CHAPTER_GAP', 'VISUAL_GAP', 'BU_SYNTHESIS_GAP', 'CONTRADICTION', 'UNRESOLVED'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    affected_component TEXT,
    question TEXT NOT NULL,
    evidence_targets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_action TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'TARGETED_REREAD_DISPATCHED', 'RECONCILED', 'WONTFIX')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- P8: LearningObject
CREATE TABLE IF NOT EXISTS stratum.learning_objects (
    id TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL REFERENCES stratum.book_understandings_v2(id) ON DELETE CASCADE,
    learning_goal TEXT NOT NULL,
    target_refs TEXT[] NOT NULL DEFAULT '{}',
    prerequisites_refs TEXT[] NOT NULL DEFAULT '{}',
    knowledge_type TEXT NOT NULL,
    importance TEXT NOT NULL CHECK (importance IN ('CORE', 'SUPPORTING', 'PERIPHERAL')),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('EASY', 'MEDIUM', 'HARD')),
    mastery_requirements_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    assessment_modes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_refs TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- P8: LearningGraph
CREATE TABLE IF NOT EXISTS stratum.learning_graphs (
    id TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL REFERENCES stratum.book_understandings_v2(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    nodes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    edges_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(bu_id, version)
);

-- P9: RetrievalItem
CREATE TABLE IF NOT EXISTS stratum.retrieval_items (
    id TEXT PRIMARY KEY,
    learning_object_id TEXT NOT NULL REFERENCES stratum.learning_objects(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL CHECK (interaction_type IN (
        'FREE_RECALL', 'DEFINITION', 'EXPLAIN_WHY', 'MINIMAL_PAIR', 
        'EXAMPLE', 'NON_EXAMPLE', 'RELATION_RECONSTRUCTION', 
        'ARGUMENT_RECONSTRUCTION', 'PREDICT', 'COUNTERFACTUAL', 
        'SOLVE', 'APPLY', 'TEACH_BACK', 'TRANSFER'
    )),
    payload_json JSONB NOT NULL DEFAULT '{"question": "", "options": [], "expected_answer": ""}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
