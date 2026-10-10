-- P14: Cross-Book Intelligence Migration
-- Creates tables for cross-book understanding storage

-- 1. Cross-Book Collections
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_collections (
    collection_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    book_ids TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

-- 2. Cross-Book Collection Members (many-to-many: collection <-> book)
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_members (
    collection_id TEXT NOT NULL REFERENCES stratum.bu2_crossbook_collections(collection_id),
    book_id TEXT NOT NULL,  -- substrate_id
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (collection_id, book_id)
);

-- 3. Cross-Book Concepts (unified concepts across books)
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_concepts (
    concept_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    definition TEXT,
    source_books JSONB NOT NULL,  -- [{"book_id": "...", "concept_ref": "...", "role": "..."}]
    alignment_confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Cross-Book Concept Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_concept_relations (
    relation_id TEXT PRIMARY KEY,
    source_book_id TEXT NOT NULL,
    source_concept_id TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- SAME_CONCEPT, RELATED_CONCEPT, SUBSUMES, etc.
    reason TEXT,
    evidence JSONB,  -- array of evidence strings
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Cross-Book Concept Evolutions
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_concept_evolutions (
    chain_id TEXT PRIMARY KEY,
    sequence JSONB NOT NULL,  -- [{"book_id": "...", "concept_id": "...", "evolution_type": "..."}]
    evolution_types TEXT[] NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Cross-Book Theses
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_theses (
    thesis_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    thesis_ref TEXT NOT NULL,  -- ref to BookThesis.id in that book's synthesis
    statement TEXT NOT NULL,
    type TEXT NOT NULL,  -- CORE, SUPPORTING, PROBLEM, QUESTION, etc.
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Cross-Book Thesis Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_thesis_relations (
    relation_id TEXT PRIMARY KEY,
    source_thesis_id TEXT NOT NULL,
    target_thesis_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- SUPPORTS, EXTENDS, QUALIFIES, CONTRADICTS, etc.
    reason TEXT,
    evidence JSONB,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Cross-Book Arguments
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_arguments (
    argument_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    argument_ref TEXT NOT NULL,  -- ref to BookArgument.id
    level INTEGER NOT NULL,
    what TEXT NOT NULL,
    why TEXT,
    how TEXT,
    conclusion TEXT,
    evidence_refs TEXT[],
    status TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Cross-Book Argument Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_argument_relations (
    relation_id TEXT PRIMARY KEY,
    source_argument_id TEXT NOT NULL,
    target_argument_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- SUPPORTS, CHALLENGES, EXTENDS, etc.
    reason TEXT,
    evidence JSONB,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 10. Cross-Book Argument Transfers
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_argument_transfers (
    transfer_id TEXT PRIMARY KEY,
    source_book_id TEXT NOT NULL,
    source_argument_id TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_argument_id TEXT NOT NULL,
    transfer_type TEXT NOT NULL,  -- THEORY_TO_APPLICATION, FOUNDATION_TO_EXTENSION, etc.
    reason TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. Cross-Book Mechanisms
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_mechanisms (
    mechanism_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    mechanism_ref TEXT NOT NULL,  -- ref to BookMechanism.id
    trigger TEXT,
    precondition TEXT,
    operation TEXT,
    outcome TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. Cross-Book Mechanism Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_mechanism_relations (
    relation_id TEXT PRIMARY KEY,
    source_mechanism_id TEXT NOT NULL,
    target_mechanism_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- SAME, VARIANT, COMPLEMENTARY, COMPETING, INCOMPATIBLE, UNKNOWN
    reason TEXT,
    evidence JSONB,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 13. Cross-Book Evidence
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_evidence (
    evidence_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    locator TEXT,
    strength TEXT NOT NULL,  -- DIRECT, DEFINITION, EXAMPLE, DERIVED, MODEL_INFERENCE
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 14. Cross-Book Evidence Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_evidence_relations (
    relation_id TEXT PRIMARY KEY,
    source_evidence_id TEXT NOT NULL,
    target_evidence_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- CONVERGENT, DIVERGENT, INDEPENDENT, CONFLICTING, INSUFFICIENT, UNKNOWN
    reason TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 15. Cross-Book Contradictions
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_contradictions (
    contradiction_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- DIRECT_CONTRADICTION, DEFINITIONAL_CONFLICT, SCOPE_CONFLICT, etc.
    book_a_id TEXT NOT NULL,
    element_a TEXT NOT NULL,
    book_b_id TEXT NOT NULL,
    element_b TEXT NOT NULL,
    element_type TEXT NOT NULL,  -- claim, concept, argument, thesis
    description TEXT,
    classification TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 16. Cross-Book Problems
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_problems (
    problem_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    problem_ref TEXT NOT NULL,
    statement TEXT NOT NULL,
    scope TEXT,
    domain TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 17. Cross-Book Problem Relations
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_problem_relations (
    relation_id TEXT PRIMARY KEY,
    source_problem_id TEXT NOT NULL,
    target_problem_id TEXT NOT NULL,
    relation TEXT NOT NULL,  -- SAME_PROBLEM, SUBPROBLEM, SUPERPROBLEM, RELATED_PROBLEM, ORTHOGONAL, UNKNOWN
    reason TEXT,
    evidence JSONB,
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 18. Cross-Book Knowledge Gaps
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_gaps (
    gap_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- UNANSWERED, WEAKLY_SUPPORTED, CONFLICTING, MISSING_BRIDGE, MISSING_EVIDENCE, SCOPE_GAP, BOOK_SET_LIMIT
    description TEXT NOT NULL,
    affected_books TEXT[] NOT NULL,
    missing_elements TEXT[],
    reason TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 19. Cross-Book Comparisons (pairwise book comparisons)
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_comparisons (
    comparison_id TEXT PRIMARY KEY,
    book_a_id TEXT NOT NULL,
    book_b_id TEXT NOT NULL,
    concept_relations JSONB,
    thesis_relations JSONB,
    argument_relations JSONB,
    mechanism_relations JSONB,
    evidence_relations JSONB,
    contradictions JSONB,
    problem_relations JSONB,
    author_relations JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 20. Cross-Book Syntheses
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_syntheses (
    synthesis_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.bu2_crossbook_collections(collection_id),
    common_ground TEXT[],
    major_differences TEXT[],
    concept_evolution JSONB,
    supporting_theories TEXT[],
    competing_theories TEXT[],
    evidence_convergence TEXT[],
    evidence_divergence TEXT[],
    unresolved_conflicts JSONB,
    knowledge_gaps JSONB,
    higher_order_synthesis TEXT,
    traceability JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 21. Cross-Book Understanding (top-level object)
CREATE TABLE IF NOT EXISTS stratum.bu2_crossbook_understanding (
    understanding_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.bu2_crossbook_collections(collection_id),
    shared_problems JSONB,
    concept_system JSONB,
    concept_relations JSONB,
    thesis_system JSONB,
    thesis_relations JSONB,
    argument_system JSONB,
    argument_relations JSONB,
    mechanism_system JSONB,
    mechanism_relations JSONB,
    evidence_system JSONB,
    evidence_relations JSONB,
    contradictions JSONB,
    comparisons JSONB,
    knowledge_gaps JSONB,
    synthesis JSONB,
    quality JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_crossbook_concepts_label ON stratum.bu2_crossbook_concepts(label);
CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_source ON stratum.bu2_crossbook_concept_relations(source_book_id, source_concept_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_target ON stratum.bu2_crossbook_concept_relations(target_book_id, target_concept_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_type ON stratum.bu2_crossbook_concept_relations(relation);
CREATE INDEX IF NOT EXISTS idx_crossbook_theses_book ON stratum.bu2_crossbook_theses(book_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_thesis_relations_source ON stratum.bu2_crossbook_thesis_relations(source_thesis_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_thesis_relations_target ON stratum.bu2_crossbook_thesis_relations(target_thesis_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_argument_relations_source ON stratum.bu2_crossbook_argument_relations(source_argument_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_argument_relations_target ON stratum.bu2_crossbook_argument_relations(target_argument_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_mechanism_relations_source ON stratum.bu2_crossbook_mechanism_relations(source_mechanism_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_mechanism_relations_target ON stratum.bu2_crossbook_mechanism_relations(target_mechanism_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_evidence_relations_source ON stratum.bu2_crossbook_evidence_relations(source_evidence_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_evidence_relations_target ON stratum.bu2_crossbook_evidence_relations(target_evidence_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_contradictions_type ON stratum.bu2_crossbook_contradictions(type);
CREATE INDEX IF NOT EXISTS idx_crossbook_contradictions_books ON stratum.bu2_crossbook_contradictions(book_a_id, book_b_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_problems_book ON stratum.bu2_crossbook_problems(book_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_gaps_type ON stratum.bu2_crossbook_gaps(type);
CREATE INDEX IF NOT EXISTS idx_crossbook_comparisons_books ON stratum.bu2_crossbook_comparisons(book_a_id, book_b_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_syntheses_collection ON stratum.bu2_crossbook_syntheses(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_understanding_collection ON stratum.bu2_crossbook_understanding(collection_id);