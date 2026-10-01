-- 055: Book Understanding 2.0 - P4 & P5 Chapter Model and BU

-- P4: ChapterUnderstanding
CREATE TABLE IF NOT EXISTS stratum.chapter_understandings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL,
    chapter_question TEXT,
    chapter_goal TEXT,
    chapter_thesis TEXT,
    primary_role TEXT,
    secondary_roles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    concepts_introduced_refs TEXT[] NOT NULL DEFAULT '{}',
    concepts_redefined_refs TEXT[] NOT NULL DEFAULT '{}',
    major_ku_refs TEXT[] NOT NULL DEFAULT '{}',
    supporting_ku_refs TEXT[] NOT NULL DEFAULT '{}',
    arguments_refs TEXT[] NOT NULL DEFAULT '{}',
    mechanisms_refs TEXT[] NOT NULL DEFAULT '{}',
    evidence_program_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    qualifications_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    dependencies_on_prior JSONB NOT NULL DEFAULT '[]'::jsonb,
    promises_to_future JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- P4: ChapterDelta
CREATE TABLE IF NOT EXISTS stratum.chapter_deltas (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL,
    new_concepts_refs TEXT[] NOT NULL DEFAULT '{}',
    revised_concepts_refs TEXT[] NOT NULL DEFAULT '{}',
    new_claims_refs TEXT[] NOT NULL DEFAULT '{}',
    new_arguments_refs TEXT[] NOT NULL DEFAULT '{}',
    supports_prior_refs TEXT[] NOT NULL DEFAULT '{}',
    qualifies_prior_refs TEXT[] NOT NULL DEFAULT '{}',
    contradicts_prior_refs TEXT[] NOT NULL DEFAULT '{}',
    revises_prior_refs TEXT[] NOT NULL DEFAULT '{}',
    resolves_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    opens_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- P5: BookUnderstanding v2 (Canonical BU Authority)
CREATE TABLE IF NOT EXISTS stratum.book_understandings_v2 (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES stratum.book_reading_run(id) ON DELETE CASCADE,
    substrate_id TEXT NOT NULL REFERENCES stratum.substrates(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'VERIFICATION_PENDING', 'VERIFIED', 'FAILED')),
    genre TEXT,
    governing_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    central_theses_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sub_theses_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    concept_system_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    situation_model_ref TEXT,
    argument_architecture_json JSONB NOT NULL DEFAULT '{"root_arguments":[], "supporting_arguments":[]}'::jsonb,
    chapter_dependency_graph JSONB NOT NULL DEFAULT '{"dependencies":[]}'::jsonb,
    discourse_arc JSONB NOT NULL DEFAULT '{"steps":[]}'::jsonb,
    negative_knowledge_json JSONB NOT NULL DEFAULT '{"rejected_claims":[], "limitations":[], "open_problems":[], "unresolved_conflicts":[]}'::jsonb,
    concept_evolution_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    claim_evolution_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolved_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    coverage_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    verification_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(substrate_id, version)
);
