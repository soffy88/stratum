"""AII Canonical Knowledge Object Contract.

This is the constitutional definition for every knowledge object in AII.
All 8 canonical objects share the same six-item contract:

    owner / authority / lifecycle / version / provenance / projection

If code disagrees with this file, fix code first, then update this file
and mention it in the PR — this file is the single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectContract:
    """Six-item contract for a canonical knowledge object."""

    owner: str  # who can write (user / system / ai)
    authority: str  # canonical table that owns truth
    lifecycle: str  # create → update → supersede → archive
    version: str  # how versions are tracked
    provenance: str  # required provenance links
    projection: str  # allowed projections, rebuildable


# ── Canonical objects (closed set) ────────────────────────────────────────────
# No new object type without explicit evidence and ADR.

CANONICAL_OBJECTS: list[str] = [
    "Source",
    "Fragment",
    "Evidence",
    "Claim",
    "Concept",
    "Relation",
    "Note",
    "Annotation",
    "LearningObject",
    "Skill",
]

# ── Authority map: object → canonical table ───────────────────────────────────

AUTHORITY_MAP: dict[str, str] = {
    "Source": "stratum.substrates",
    "Fragment": "stratum.substrate_chunk",
    "Evidence": "stratum.evidence",
    "Claim": "stratum.knowledge_claims",
    "Concept": "stratum.concepts",
    "Relation": "stratum.concept_relations",
    "Note": "stratum.notes_sl",
    "Annotation": "stratum.highlights",
    "LearningObject": "stratum.substrate_layers",  # L1/L2 are LO projections
    "Skill": "aii.bu_onto (sub_type=skill)",
}

# ── Writer map: object → allowed writer(s) ───────────────────────────────────

WRITER_MAP: dict[str, str] = {
    "Source": "acquire pipeline (ingest_substrate) + user upload",
    "Fragment": "parser/pg_reembed (substrate_chunk writer)",
    "Evidence": "user highlight + API POST /api/v1/knowledge/evidence",
    "Claim": "AI pipeline (BU/ku_pipeline) + API POST /api/v1/knowledge/claims, must reference Evidence",
    "Concept": "stratum.concepts API + legacy merge ledger (human-approved)",
    "Relation": "stratum.concept_relations API, requires rationale or evidence_ids",
    "Note": "user-authored only (ai/system must not masquerade)",
    "Annotation": "user highlight + system locator enrichment",
    "LearningObject": "BU pipeline (learning_paths/deep_cards) projecting Claim/Evidence",
    "Skill": "skill export projecting Concept/Claim/Evidence/LearningObject",
}

# ── Six-item contracts ────────────────────────────────────────────────────────

OBJECT_CONTRACTS: dict[str, ObjectContract] = {
    "Source": ObjectContract(
        owner="user",
        authority="stratum.substrates",
        lifecycle="acquire → version (new row) → soft-delete (never overwrite text/content_hash)",
        version="immutable text/content_hash; correction = new substrate_id",
        provenance="self-authority; license + source_path anchor",
        projection="derivative, substrate_chunk, tantivy index (rebuildable)",
    ),
    "Fragment": ObjectContract(
        owner="system",
        authority="stratum.substrate_chunk",
        lifecycle="parse → chunk → embed → supersede on re-parse",
        version="substrate_id#chunk_idx + parser_version + anchor_json",
        provenance="Fragment -> Source (substrate_id FK, stable anchor, content_hash)",
        projection="vector index (pgvector vector(1024)), tantivy BM25 (rebuildable from PG)",
    ),
    "Evidence": ObjectContract(
        owner="user",
        authority="stratum.evidence",
        lifecycle="highlight → evidence → link to Claim → supersede",
        version="ulid + quote_hash; updated_at on locator change",
        provenance="Evidence -> Fragment -> Source (substrate_id + locator_json + quote_hash)",
        projection="claim_evidence join, search snippet",
    ),
    "Claim": ObjectContract(
        owner="ai (grounded) / user (curated)",
        authority="stratum.knowledge_claims",
        lifecycle="unverified → verified | contradicted | refuted; superseded_by on correction",
        version="ulid + status + confidence + updated_at; correction preserves history",
        provenance="Claim -> Evidence[] -> Fragment -> Source (claim_evidence relation, no orphan claim)",
        projection="BU learning_paths, skill claim_refs, search citation",
    ),
    "Concept": ObjectContract(
        owner="system (merge ledger human-approved)",
        authority="stratum.concepts",
        lifecycle="extract → dedup (ledger) → merge (human approval) → soft-delete",
        version="ulid; aliases[] + substrate_refs[]",
        provenance="Concept -> Evidence/Claim (substrate_refs), Relation rationale",
        projection="graph_entities (legacy, read-only), KG retrieval",
    ),
    "Relation": ObjectContract(
        owner="ai (explainable)",
        authority="stratum.concept_relations",
        lifecycle="create (requires rationale|evidence) → update → supersede",
        version="ulid + (user_id, source, target, type) unique; updated_at",
        provenance="Relation -> Claim/Evidence (evidence_ids) + rationale text",
        projection="graph_relations (legacy), neighborhood API",
    ),
    "Note": ObjectContract(
        owner="user",
        authority="stratum.notes_sl",
        lifecycle="create (user-authored) → update (user only) → soft-delete; AI must not overwrite",
        version="ulid + updated_at; author=user enforced at API boundary",
        provenance="Note -> optional substrate_refs/concept_refs (user-curated links)",
        projection="timeline, personal search namespace",
    ),
    "Annotation": ObjectContract(
        owner="user",
        authority="stratum.highlights",
        lifecycle="create highlight → enrich to Evidence → supersede",
        version="ulid + location_json/locator_json; quote_hash stable",
        provenance="Annotation -> Fragment (substrate_id + locator)",
        projection="evidence.source_highlight_id",
    ),
    "LearningObject": ObjectContract(
        owner="ai (projection)",
        authority="NOT authority — projection of Claim/Evidence via substrate_layers L1/L2",
        lifecycle="generate transient JSON → persist with canonical refs → stale on claim correction",
        version="substrate_id + layer (L1/L2); no independent semantic id",
        provenance="LearningObject -> Claim -> Evidence -> Fragment -> Source",
        projection="substrate_layers L1/L2, BU deep_cards/learning_paths (must resolve to canonical ids)",
    ),
    "Skill": ObjectContract(
        owner="ai (packaging)",
        authority="NOT authority — packaged projection, never fact source",
        lifecycle="export (with refs) → version → stale detection → regenerate",
        version="skill_id ulid + version + generator_version + generated_at",
        provenance="Skill -> Concept/Claim/Evidence/LearningObject (explicit ref lists)",
        projection="exported JSON/package; rebuildable from canonical store",
    ),
}

# ── Provenance graph (edges: derived → source) ───────────────────────────────

PROVENANCE_GRAPH: dict[str, list[str]] = {
    "Fragment": ["Source"],
    "Evidence": ["Fragment", "Source"],
    "Claim": ["Evidence"],
    "Relation": ["Claim", "Evidence"],
    "LearningObject": ["Claim", "Evidence"],
    "Skill": ["Claim", "Concept", "Evidence", "LearningObject"],
    "Annotation": ["Fragment"],
    "Note": [],  # user-authored, optional links but not required
    "Source": [],
    "Concept": ["Evidence", "Claim"],
}

# ── Retrieval scopes (KnowledgeView must support) ─────────────────────────────

RETRIEVAL_SCOPES: list[str] = [
    "lexical",
    "dense",
    "graph",
    "temporal",
    "user-authored",
    "learning",
]
