-- 085_bu2_reasoning_node_theorem.sql
-- Task C: the reasoning graph must carry THEOREM-level nodes for a mathematics
-- book, not only CHAPTER nodes. Migration 068 constrained node_type to a closed
-- vocabulary that had CONCEPT and CLAIM but no THEOREM, so a frozen Theorem KU
-- could only be attached to a CONCEPT node, losing the distinction between a
-- definition and a proved result.
--
-- Additive and idempotent: widen the CHECK to include THEOREM. No row is
-- rewritten; every existing node keeps its type.

ALTER TABLE stratum.reasoning_node
    DROP CONSTRAINT IF EXISTS reasoning_node_node_type_check;

ALTER TABLE stratum.reasoning_node
    ADD CONSTRAINT reasoning_node_node_type_check CHECK (node_type IN (
        'CHAPTER', 'CONCEPT', 'CLAIM', 'THEOREM', 'MECHANISM',
        'QUESTION', 'EXAMPLE', 'CONCLUSION'
    ));

-- Task C: the real definition text per concept, so the book-level concept
-- evolution can carry a definition rather than the placeholder
-- "introduced or redefined in chX". Additive with a default; no row rewritten.
ALTER TABLE stratum.chapter_understandings
    ADD COLUMN IF NOT EXISTS concept_definitions JSONB NOT NULL DEFAULT '{}'::jsonb;
