"""P14: Cross-Book Concept Alignment.

Aligns concepts across independently understood books with full traceability.
Does not assume same-name = same-concept.
"""

from __future__ import annotations

import hashlib
from typing import Any
from dataclasses import dataclass

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    BookUnderstandingV2,
    ConceptSystemEntry,
    CrossBookConcept,
    CrossBookConceptEvolution,
    CrossBookConceptRelation,
    CrossBookConceptRelationType,
    ThesisProvenance,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two texts."""
    set_a = set(_normalize_text(a).split())
    set_b = set(_normalize_text(b).split())
    if not set_a and not set_b:
        # Two empty fields share nothing; scoring them 1.0 manufactured
        # matches between unrelated items whose optional fields were blank.
        return 0.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


@dataclass
class ConceptAlignmentResult:
    """Result of concept alignment across books."""

    unified_concepts: list[CrossBookConcept]
    concept_relations: list[CrossBookConceptRelation]
    concept_evolutions: list[CrossBookConceptEvolution]
    traceability: dict[str, list[str]]


class BU2CrossBookConceptAligner:
    """Aligns concepts across independently understood books.

    Core principle: same name != same concept. Alignment requires
    definition, scope, properties, role, applications comparison.
    """

    def __init__(self, provider=None):
        self.provider = provider
        self._concept_cache: dict[str, list[ConceptSystemEntry]] = {}

    def _extract_all_concepts(
        self, books: list[tuple[BookUnderstandingV2, BookSynthesis]]
    ) -> dict[str, list[ConceptSystemEntry]]:
        """Extract all concepts from all books with their source context."""
        all_concepts: dict[str, list[ConceptSystemEntry]] = {}

        for bu, synth in books:
            if not synth or not synth.concept_system:
                continue

            book_concepts: list[ConceptSystemEntry] = []
            for role_attr in [
                "foundational",
                "core",
                "derived",
                "bridging",
                "application",
                "terminal",
            ]:
                concepts = getattr(synth.concept_system, role_attr, [])
                for concept in concepts:
                    concept_copy = concept.model_copy()
                    concept_copy.final_role = role_attr.upper()
                    book_concepts.append(concept_copy)

            if book_concepts:
                all_concepts[bu.book_id] = book_concepts

        return all_concepts

    def _compute_concept_similarity(
        self,
        c1: ConceptSystemEntry,
        c2: ConceptSystemEntry,
    ) -> dict[str, float]:
        """Compute similarity metrics between two concepts."""
        return {
            "label": _jaccard_similarity(c1.label, c2.label),
            "definition": _jaccard_similarity(c1.definition, c2.definition),
            "prerequisites": _jaccard_similarity(
                " ".join(c1.prerequisites), " ".join(c2.prerequisites)
            ),
            "related": _jaccard_similarity(
                " ".join(c1.related_concepts), " ".join(c2.related_concepts)
            ),
            "applied_in": _jaccard_similarity(" ".join(c1.applied_in), " ".join(c2.applied_in)),
        }

    def _determine_relation(
        self,
        c1: ConceptSystemEntry,
        c2: ConceptSystemEntry,
        similarity: dict[str, float],
    ) -> CrossBookConceptRelationType:
        """Determine the relation type between two concepts from different books."""

        # Same label, high definition similarity -> likely same concept
        if similarity["label"] > 0.8 and similarity["definition"] > 0.7:
            return CrossBookConceptRelationType.SAME_CONCEPT

        # Same label, low definition similarity -> same term, different meaning
        if similarity["label"] > 0.8 and similarity["definition"] < 0.4:
            return CrossBookConceptRelationType.SAME_TERM_DIFFERENT_MEANING

        # High overall similarity -> related concept
        avg_sim = sum(similarity.values()) / len(similarity)
        if avg_sim > 0.6:
            return CrossBookConceptRelationType.RELATED_CONCEPT

        # Check for subsumption/specialization
        if similarity["definition"] > 0.5 and (
            len(c1.prerequisites) < len(c2.prerequisites) or len(c1.applied_in) < len(c2.applied_in)
        ):
            return CrossBookConceptRelationType.SUBSUMES

        if avg_sim > 0.4:
            return CrossBookConceptRelationType.ANALOGOUS

        return CrossBookConceptRelationType.UNKNOWN

    def _align_concept_pair(
        self,
        book_a_id: str,
        book_b_id: str,
        concepts_a: list[ConceptSystemEntry],
        concepts_b: list[ConceptSystemEntry],
    ) -> list[CrossBookConceptRelation]:
        """Align all pairs of concepts between two books."""
        relations = []

        for c1 in concepts_a:
            for c2 in concepts_b:
                similarity = self._compute_concept_similarity(c1, c2)
                relation_type = self._determine_relation(c1, c2, similarity)

                if relation_type == CrossBookConceptRelationType.UNKNOWN:
                    continue

                # Build evidence list
                evidence = []
                evidence.append(f"label_similarity={similarity['label']:.2f}")
                evidence.append(f"definition_similarity={similarity['definition']:.2f}")
                evidence.append(f"role_a={c1.final_role}, role_b={c2.final_role}")
                if c1.chapter_refs:
                    evidence.append(f"chapters_a={','.join(c1.chapter_refs[:3])}")
                if c2.chapter_refs:
                    evidence.append(f"chapters_b={','.join(c2.chapter_refs[:3])}")

                # Compute confidence
                avg_sim = sum(similarity.values()) / len(similarity)
                confidence = round(avg_sim, 3)

                relation = CrossBookConceptRelation(
                    relation_id=_stable_id(
                        "cbr", book_a_id, c1.concept_id, book_b_id, c2.concept_id
                    ),
                    source_book_id=book_a_id,
                    source_concept_id=c1.concept_id,
                    target_book_id=book_b_id,
                    target_concept_id=c2.concept_id,
                    relation=relation_type,
                    reason=f"{c1.label} ({c1.final_role}) ~ {c2.label} ({c2.final_role}) via {relation_type.value}",
                    evidence=evidence,
                    confidence=confidence,
                    provenance=ThesisProvenance.MODEL_INFERRED,
                )
                relations.append(relation)

        return relations

    def _build_unified_concepts(
        self,
        all_concepts: dict[str, list[ConceptSystemEntry]],
        relations: list[CrossBookConceptRelation],
    ) -> list[CrossBookConcept]:
        """Build unified cross-book concepts from aligned concepts."""
        unified: dict[str, dict[str, Any]] = {}
        concept_to_unified = {}

        # Group by SAME_CONCEPT relations
        for rel in relations:
            if rel.relation == CrossBookConceptRelationType.SAME_CONCEPT:
                # Find or create unified concept
                key = f"{rel.source_book_id}|{rel.source_concept_id}|{rel.target_book_id}|{rel.target_concept_id}"
                if key not in unified:
                    unified[key] = {
                        "books": [],
                        "definitions": [],
                        "roles": [],
                        "confidence_sum": 0.0,
                    }
                unified[key]["books"].extend([rel.source_book_id, rel.target_book_id])
                unified[key]["definitions"].extend(
                    [
                        next(
                            (
                                c.definition
                                for c in all_concepts.get(rel.source_book_id, [])
                                if c.concept_id == rel.source_concept_id
                            ),
                            "",
                        ),
                        next(
                            (
                                c.definition
                                for c in all_concepts.get(rel.target_book_id, [])
                                if c.concept_id == rel.target_concept_id
                            ),
                            "",
                        ),
                    ]
                )
                unified[key]["confidence_sum"] += rel.confidence
                concept_to_unified[rel.source_concept_id] = key
                concept_to_unified[rel.target_concept_id] = key

        # Add unaligned concepts as standalone
        for book_id, concepts in all_concepts.items():
            for c in concepts:
                if c.concept_id not in concept_to_unified:
                    key = f"{book_id}|{c.concept_id}"
                    unified[key] = {
                        "books": [book_id],
                        "definitions": [c.definition],
                        "roles": [c.final_role],
                        "confidence_sum": c.confidence,
                    }

        # Build CrossBookConcept objects
        unified_concepts = []
        for key, data in unified.items():
            if not data["books"]:
                continue
            label = key.split("|")[1] if "|" in key else key
            cb = CrossBookConcept(
                concept_id=_stable_id("cb", key),
                label=label,
                definition=" | ".join(set(d for d in data["definitions"] if d)),
                source_books=[
                    {"book_id": b, "concept_ref": "", "role": r}
                    for b, r in zip(data["books"], data["roles"])
                ],
                alignment_confidence=round(data["confidence_sum"] / max(1, len(data["books"])), 3),
                provenance=ThesisProvenance.MODEL_INFERRED,
            )
            unified_concepts.append(cb)

        return unified_concepts

    def _detect_evolutions(
        self,
        unified_concepts: list[CrossBookConcept],
        all_concepts: dict[str, list[ConceptSystemEntry]],
        relations: list[CrossBookConceptRelation],
    ) -> list[CrossBookConceptEvolution]:
        """Detect concept evolution chains across books."""
        evolutions = []

        for uc in unified_concepts:
            if len(uc.source_books) < 2:
                continue

            # Build sequence by prerequisite/applied_in relations
            sequence = []
            for src in uc.source_books:
                book_id = src.get("book_id", "")
                concept_id = src.get("concept_ref", "")
                if book_id and concept_id:
                    sequence.append(
                        {
                            "book_id": book_id,
                            "concept_id": concept_id,
                            "evolution_type": "INTRODUCES",  # Would need ordering logic
                        }
                    )

            if len(sequence) >= 2:
                evolutions.append(
                    CrossBookConceptEvolution(
                        chain_id=_stable_id("evo", uc.concept_id),
                        sequence=sequence,
                        evolution_types=["INTRODUCES", "REFINES"],  # Simplified
                        provenance=ThesisProvenance.MODEL_INFERRED,
                    )
                )

        return evolutions

    def align(
        self,
        books: list[tuple[BookUnderstandingV2, BookSynthesis]],
    ) -> ConceptAlignmentResult:
        """Align concepts across all books in the collection.

        Args:
            books: List of (BookUnderstandingV2, BookSynthesis) tuples

        Returns:
            ConceptAlignmentResult with unified concepts, relations, evolutions
        """
        if len(books) < 2:
            return ConceptAlignmentResult(
                unified_concepts=[],
                concept_relations=[],
                concept_evolutions=[],
                traceability={},
            )

        # Extract all concepts from all books
        all_concepts = self._extract_all_concepts(books)

        # Align all pairs of books
        book_ids = [bu.book_id for bu, _ in books]
        relations = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                concepts_a = all_concepts.get(book_a_id, [])
                concepts_b = all_concepts.get(book_b_id, [])

                if concepts_a and concepts_b:
                    pair_relations = self._align_concept_pair(
                        book_a_id, book_b_id, concepts_a, concepts_b
                    )
                    relations.extend(pair_relations)

        # Build unified concepts
        unified_concepts = self._build_unified_concepts(all_concepts, relations)

        # Detect evolutions
        evolutions = self._detect_evolutions(unified_concepts, all_concepts, relations)

        # Build traceability
        traceability = {}
        for uc in unified_concepts:
            traceability[uc.concept_id] = [b["book_id"] for b in uc.source_books]
        for rel in relations:
            traceability[rel.relation_id] = [rel.source_book_id, rel.target_book_id]
        for evo in evolutions:
            traceability[evo.chain_id] = [s.get("book_id", "") for s in evo.sequence]

        return ConceptAlignmentResult(
            unified_concepts=unified_concepts,
            concept_relations=relations,
            concept_evolutions=evolutions,
            traceability=traceability,
        )
