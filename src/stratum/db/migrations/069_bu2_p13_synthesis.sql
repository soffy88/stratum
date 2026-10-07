-- P13: Book-Level Synthesis Tables
-- Migration 069
-- Adds structured synthesis components to BookUnderstandingV2
-- Authority: stratum.book_understandings_v2 (BU2 persistence authority)
-- These tables are components of BU2, NOT a second authority

-- Thesis model
CREATE TABLE IF NOT EXISTS book_theses (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    thesis_type TEXT NOT NULL CHECK (thesis_type IN ('CORE','SUPPORTING','PROBLEM','QUESTION','ASSUMPTION','CONCLUSION','LIMITATION')),
    statement TEXT NOT NULL,
    scope TEXT DEFAULT '',
    evidence_refs TEXT[] DEFAULT '{}',
    supporting_arguments TEXT[] DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED' CHECK (provenance IN ('AUTHOR_ASSERTED','MODEL_INFERRED','STRUCTURALLY_DERIVED')),
    source_locations TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_theses_run ON book_theses(run_id);
CREATE INDEX IF NOT EXISTS idx_book_theses_book ON book_theses(book_id);
CREATE INDEX IF NOT EXISTS idx_book_theses_type ON book_theses(thesis_type);

-- Concept system
CREATE TABLE IF NOT EXISTS book_concept_systems (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    concept_id TEXT NOT NULL,
    label TEXT NOT NULL,
    definition TEXT DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('FOUNDATIONAL','CORE','DERIVED','BRIDGING','APPLICATION','TERMINAL')),
    prerequisites TEXT[] DEFAULT '{}',
    related_concepts TEXT[] DEFAULT '{}',
    refined_by TEXT[] DEFAULT '{}',
    applied_in TEXT[] DEFAULT '{}',
    supports TEXT[] DEFAULT '{}',
    chapter_refs TEXT[] DEFAULT '{}',
    final_role TEXT DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_concept_systems_run ON book_concept_systems(run_id);
CREATE INDEX IF NOT EXISTS idx_book_concept_systems_book ON book_concept_systems(book_id);
CREATE INDEX IF NOT EXISTS idx_book_concept_systems_role ON book_concept_systems(role);

-- Argument system
CREATE TABLE IF NOT EXISTS book_arguments (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    level INTEGER NOT NULL DEFAULT 0,
    what TEXT NOT NULL,
    why TEXT DEFAULT '',
    how TEXT DEFAULT '',
    evidence_refs TEXT[] DEFAULT '{}',
    depends_on TEXT[] DEFAULT '{}',
    conclusion TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'MODEL_INFERRED' CHECK (status IN ('SUPPORTED','PARTIALLY_SUPPORTED','MODEL_INFERRED','UNRESOLVED','CONTRADICTED')),
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source_chapters TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_arguments_run ON book_arguments(run_id);
CREATE INDEX IF NOT EXISTS idx_book_arguments_book ON book_arguments(book_id);
CREATE INDEX IF NOT EXISTS idx_book_arguments_level ON book_arguments(level);

-- Mechanism system
CREATE TABLE IF NOT EXISTS book_mechanisms (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    trigger TEXT DEFAULT '',
    precondition TEXT DEFAULT '',
    operation TEXT NOT NULL,
    intermediate_state TEXT DEFAULT '',
    outcome TEXT DEFAULT '',
    evidence_refs TEXT[] DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED' CHECK (provenance IN ('AUTHOR_ASSERTED','MODEL_INFERRED','STRUCTURALLY_DERIVED')),
    source_chapters TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_mechanisms_run ON book_mechanisms(run_id);
CREATE INDEX IF NOT EXISTS idx_book_mechanisms_book ON book_mechanisms(book_id);

-- Evidence map
CREATE TABLE IF NOT EXISTS book_evidence_map (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL,
    claim_statement TEXT NOT NULL,
    evidence_ids TEXT[] DEFAULT '{}',
    evidence_strengths JSONB DEFAULT '{}',
    argument_ids TEXT[] DEFAULT '{}',
    chapter_ids TEXT[] DEFAULT '{}',
    is_supported BOOLEAN NOT NULL DEFAULT FALSE,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED' CHECK (provenance IN ('AUTHOR_ASSERTED','MODEL_INFERRED','STRUCTURALLY_DERIVED')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_evidence_map_run ON book_evidence_map(run_id);
CREATE INDEX IF NOT EXISTS idx_book_evidence_map_book ON book_evidence_map(book_id);
CREATE INDEX IF NOT EXISTS idx_book_evidence_map_claim ON book_evidence_map(claim_id);

-- Evidence map aggregates (one per run)
CREATE TABLE IF NOT EXISTS book_evidence_map_summary (
    run_id TEXT PRIMARY KEY REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    evidence_coverage REAL NOT NULL DEFAULT 0.0 CHECK (evidence_coverage >= 0.0 AND evidence_coverage <= 1.0),
    unsupported_claim_count INTEGER NOT NULL DEFAULT 0,
    model_inference_ratio REAL NOT NULL DEFAULT 0.0 CHECK (model_inference_ratio >= 0.0 AND model_inference_ratio <= 1.0),
    contradiction_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Author model
CREATE TABLE IF NOT EXISTS book_author_models (
    run_id TEXT PRIMARY KEY REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    worldview TEXT[] DEFAULT '{}',
    assumptions TEXT[] DEFAULT '{}',
    explanatory_strategy TEXT[] DEFAULT '{}',
    argument_style TEXT[] DEFAULT '{}',
    recurring_patterns TEXT[] DEFAULT '{}',
    evidence_preference TEXT[] DEFAULT '{}',
    limitations TEXT[] DEFAULT '{}',
    unresolved_positions TEXT[] DEFAULT '{}',
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED' CHECK (provenance IN ('AUTHOR_ASSERTED','MODEL_INFERRED','STRUCTURALLY_DERIVED')),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Chapter roles
CREATE TABLE IF NOT EXISTS book_chapter_roles (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    chapter_id TEXT NOT NULL,
    roles TEXT[] NOT NULL DEFAULT '{}',
    evidence TEXT DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_chapter_roles_run ON book_chapter_roles(run_id);
CREATE INDEX IF NOT EXISTS idx_book_chapter_roles_book ON book_chapter_roles(book_id);
CREATE INDEX IF NOT EXISTS idx_book_chapter_roles_chapter ON book_chapter_roles(chapter_id);

-- Contradictions
CREATE TABLE IF NOT EXISTS book_contradictions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    contradiction_type TEXT NOT NULL CHECK (contradiction_type IN ('DIRECT_CONTRADICTION','CONTEXTUAL_DIFFERENCE','APPARENT_CONTRADICTION','UNRESOLVED')),
    element_a TEXT NOT NULL,
    element_b TEXT NOT NULL,
    element_type TEXT NOT NULL CHECK (element_type IN ('claim','concept','argument')),
    description TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('DIRECT_CONTRADICTION','CONTEXTUAL_DIFFERENCE','APPARENT_CONTRADICTION','UNRESOLVED')),
    source_chapters TEXT[] DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_contradictions_run ON book_contradictions(run_id);
CREATE INDEX IF NOT EXISTS idx_book_contradictions_book ON book_contradictions(book_id);
CREATE INDEX IF NOT EXISTS idx_book_contradictions_type ON book_contradictions(contradiction_type);

-- Book synthesis (one per run)
CREATE TABLE IF NOT EXISTS book_syntheses (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    thesis JSONB NOT NULL DEFAULT '{}',
    problem_definition TEXT DEFAULT '',
    concept_system JSONB NOT NULL DEFAULT '{}',
    argument_system JSONB NOT NULL DEFAULT '{}',
    mechanism_system JSONB NOT NULL DEFAULT '{}',
    evidence_map JSONB NOT NULL DEFAULT '{}',
    author_model JSONB NOT NULL DEFAULT '{}',
    chapter_roles JSONB NOT NULL DEFAULT '{}',
    unresolved_questions TEXT[] DEFAULT '{}',
    contradictions JSONB NOT NULL DEFAULT '{}',
    limitations TEXT[] DEFAULT '{}',
    synthesis_evidence JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_syntheses_run ON book_syntheses(run_id);
CREATE INDEX IF NOT EXISTS idx_book_syntheses_book ON book_syntheses(book_id);

-- Synthesis expressions (read-only, non-authoritative)
CREATE TABLE IF NOT EXISTS book_synthesis_expressions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    synthesis_id TEXT NOT NULL REFERENCES book_syntheses(id) ON DELETE CASCADE,
    executive_summary TEXT DEFAULT '',
    full_explanation TEXT DEFAULT '',
    concept_map TEXT DEFAULT '',
    argument_map TEXT DEFAULT '',
    chapter_by_chapter TEXT DEFAULT '',
    author_position TEXT DEFAULT '',
    limitations TEXT DEFAULT '',
    unresolved_questions TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_book_synthesis_expressions_run ON book_synthesis_expressions(run_id);

-- Quality gates audit log
CREATE TABLE IF NOT EXISTS bu2_p13_quality_gates (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES book_reading_run(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES substrates(id) ON DELETE CASCADE,
    gate_number INTEGER NOT NULL CHECK (gate_number BETWEEN 1 AND 8),
    gate_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','BOOK_LIMIT')),
    score REAL,
    detail TEXT,
    evidence JSONB DEFAULT '{}',
    checked_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bu2_p13_quality_gates_run ON bu2_p13_quality_gates(run_id);