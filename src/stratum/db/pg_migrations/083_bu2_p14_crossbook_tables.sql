-- 083: BU2 P14 - Cross-Book Intelligence Tables
-- Creates all tables required for P14 cross-book analysis persistence

-- 1. Cross-Book Collections
-- A named collection of independently understood books for cross-book analysis
CREATE TABLE IF NOT EXISTS stratum.crossbook_collections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    book_ids TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_crossbook_collections_user
    ON stratum.crossbook_collections(user_id);

-- 2. Cross-Book Understandings
-- The top-level cross-book understanding object for a collection
CREATE TABLE IF NOT EXISTS stratum.crossbook_understandings (
    collection_id TEXT PRIMARY KEY REFERENCES stratum.crossbook_collections(id) ON DELETE CASCADE,
    understanding_id TEXT NOT NULL,
    shared_problems_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    concept_system_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    concept_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    thesis_system_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    thesis_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    argument_system_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    argument_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mechanism_system_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mechanism_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_system_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    contradictions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    comparisons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    knowledge_gaps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    synthesis_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    traceability_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Cross-Book Concepts (normalized for querying)
CREATE TABLE IF NOT EXISTS stratum.crossbook_concepts (
    concept_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    definition TEXT,
    source_books_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    alignment_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_concepts_collection
    ON stratum.crossbook_concepts(collection_id);

-- 4. Cross-Book Concept Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_concept_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_concept_id TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_collection
    ON stratum.crossbook_concept_relations(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_source
    ON stratum.crossbook_concept_relations(source_book_id, source_concept_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_concept_relations_target
    ON stratum.crossbook_concept_relations(target_book_id, target_concept_id);

-- 5. Cross-Book Theses
CREATE TABLE IF NOT EXISTS stratum.crossbook_theses (
    thesis_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    thesis_ref TEXT NOT NULL,
    statement TEXT NOT NULL,
    type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_theses_collection
    ON stratum.crossbook_theses(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_theses_book
    ON stratum.crossbook_theses(book_id);

-- 6. Cross-Book Thesis Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_thesis_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_thesis_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_thesis_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_thesis_relations_collection
    ON stratum.crossbook_thesis_relations(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_thesis_relations_source
    ON stratum.crossbook_thesis_relations(source_book_id, source_thesis_ref);
CREATE INDEX IF NOT EXISTS idx_crossbook_thesis_relations_target
    ON stratum.crossbook_thesis_relations(target_book_id, target_thesis_ref);

-- 7. Cross-Book Arguments
CREATE TABLE IF NOT EXISTS stratum.crossbook_arguments (
    argument_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    argument_ref TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 0,
    what TEXT NOT NULL,
    why TEXT,
    how TEXT,
    conclusion TEXT,
    evidence_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_arguments_collection
    ON stratum.crossbook_arguments(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_arguments_book
    ON stratum.crossbook_arguments(book_id);

-- 8. Cross-Book Argument Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_argument_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_argument_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_argument_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_argument_relations_collection
    ON stratum.crossbook_argument_relations(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_argument_relations_source
    ON stratum.crossbook_argument_relations(source_book_id, source_argument_ref);
CREATE INDEX IF NOT EXISTS idx_crossbook_argument_relations_target
    ON stratum.crossbook_argument_relations(target_book_id, target_argument_ref);

-- 9. Cross-Book Argument Transfers
CREATE TABLE IF NOT EXISTS stratum.crossbook_argument_transfers (
    transfer_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_argument_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_argument_ref TEXT NOT NULL,
    transfer_type TEXT NOT NULL,
    reason TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_argument_transfers_collection
    ON stratum.crossbook_argument_transfers(collection_id);

-- 10. Cross-Book Mechanisms
CREATE TABLE IF NOT EXISTS stratum.crossbook_mechanisms (
    mechanism_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    mechanism_ref TEXT NOT NULL,
    trigger TEXT,
    precondition TEXT,
    operation TEXT,
    outcome TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_mechanisms_collection
    ON stratum.crossbook_mechanisms(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_mechanisms_book
    ON stratum.crossbook_mechanisms(book_id);

-- 11. Cross-Book Mechanism Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_mechanism_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_mechanism_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_mechanism_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_mechanism_relations_collection
    ON stratum.crossbook_mechanism_relations(collection_id);

-- 12. Cross-Book Evidence
CREATE TABLE IF NOT EXISTS stratum.crossbook_evidence (
    evidence_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    locator TEXT,
    strength TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_evidence_collection
    ON stratum.crossbook_evidence(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_evidence_book
    ON stratum.crossbook_evidence(book_id);

-- 13. Cross-Book Evidence Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_evidence_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_evidence_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_evidence_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_evidence_relations_collection
    ON stratum.crossbook_evidence_relations(collection_id);

-- 14. Cross-Book Contradictions
CREATE TABLE IF NOT EXISTS stratum.crossbook_contradictions (
    contradiction_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    book_a_id TEXT NOT NULL,
    element_a TEXT NOT NULL,
    book_b_id TEXT NOT NULL,
    element_b TEXT NOT NULL,
    element_type TEXT NOT NULL,
    description TEXT,
    classification TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_contradictions_collection
    ON stratum.crossbook_contradictions(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_contradictions_books
    ON stratum.crossbook_contradictions(book_a_id, book_b_id);

-- 15. Cross-Book Problems
CREATE TABLE IF NOT EXISTS stratum.crossbook_problems (
    problem_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    problem_ref TEXT NOT NULL,
    statement TEXT NOT NULL,
    scope TEXT,
    domain TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_problems_collection
    ON stratum.crossbook_problems(collection_id);

-- 16. Cross-Book Problem Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_problem_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_problem_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_problem_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_problem_relations_collection
    ON stratum.crossbook_problem_relations(collection_id);

-- 17. Cross-Book Author Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_author_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_a_id TEXT NOT NULL,
    book_b_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    dimension TEXT,
    reason TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_author_relations_collection
    ON stratum.crossbook_author_relations(collection_id);

-- 18. Cross-Book Knowledge Gaps
CREATE TABLE IF NOT EXISTS stratum.crossbook_knowledge_gaps (
    gap_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_books_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_elements_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    reason TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_knowledge_gaps_collection
    ON stratum.crossbook_knowledge_gaps(collection_id);

-- 19. Cross-Book Comparisons
CREATE TABLE IF NOT EXISTS stratum.crossbook_comparisons (
    comparison_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_a_id TEXT NOT NULL,
    book_b_id TEXT NOT NULL,
    concept_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    thesis_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    argument_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    mechanism_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    contradictions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    problem_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    author_relations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_comparisons_collection
    ON stratum.crossbook_comparisons(collection_id);
CREATE INDEX IF NOT EXISTS idx_crossbook_comparisons_books
    ON stratum.crossbook_comparisons(book_a_id, book_b_id);

-- 20. Cross-Book Syntheses
CREATE TABLE IF NOT EXISTS stratum.crossbook_syntheses (
    synthesis_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    common_ground_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    major_differences_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    concept_evolution_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_theories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    competing_theories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_convergence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_divergence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_conflicts_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    knowledge_gaps_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    higher_order_synthesis TEXT NOT NULL DEFAULT '',
    traceability_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_syntheses_collection
    ON stratum.crossbook_syntheses(collection_id);

-- 21. Cross-Book Claims (for evidence map cross-book alignment)
CREATE TABLE IF NOT EXISTS stratum.crossbook_claims (
    claim_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    claim_ref TEXT NOT NULL,
    statement TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    is_supported BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_claims_collection
    ON stratum.crossbook_claims(collection_id);

-- 24. Cross-Book Claim Relations
CREATE TABLE IF NOT EXISTS stratum.crossbook_claim_relations (
    relation_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    source_book_id TEXT NOT NULL,
    source_claim_ref TEXT NOT NULL,
    target_book_id TEXT NOT NULL,
    target_claim_ref TEXT NOT NULL,
    relation TEXT NOT NULL,
    reason TEXT,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_claim_relations_collection
    ON stratum.crossbook_claim_relations(collection_id);

-- 25. Cross-Book Concept Evolutions
CREATE TABLE IF NOT EXISTS stratum.crossbook_concept_evolutions (
    chain_id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL REFERENCES stratum.crossbook_understandings(collection_id) ON DELETE CASCADE,
    sequence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    evolution_types_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance TEXT NOT NULL DEFAULT 'MODEL_INFERRED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_crossbook_concept_evolutions_collection
    ON stratum.crossbook_concept_evolutions(collection_id);