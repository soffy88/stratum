"""P14: Cross-Book Synthesis.

Orchestrates all P14 components to produce the final CrossBookUnderstanding.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    BookUnderstandingV2,
    CrossBookCollection,
    CrossBookComparison,
    CrossBookConcept,
    CrossBookConceptEvolution,
    CrossBookContradiction,
    CrossBookKnowledgeGap,
    CrossBookProblem,
    CrossBookSynthesis,
    CrossBookThesis,
    CrossBookUnderstanding,
    ThesisProvenance,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _flatten_traceability(traceability: dict[str, list[str]]) -> list[str]:
    out = []
    for refs in traceability.values():
        if isinstance(refs, list):
            out.extend(refs)
    return out


class BU2CrossBookSynthesisBuilder:
    """Build the complete CrossBookUnderstanding from all P14 components."""

    def __init__(self):
        # These will be injected or imported
        pass

    def build(
        self,
        collection: CrossBookCollection,
        books: list[tuple[BookUnderstandingV2, BookSynthesis]],
        concept_result: Any,
        thesis_result: Any,
        argument_result: Any,
        mechanism_result: Any,
        evidence_result: Any,
        contradiction_result: Any,
        problem_result: Any,
        gap_result: Any,
        comparison_results: list[CrossBookComparison],
    ) -> CrossBookUnderstanding:
        """Build the complete CrossBookUnderstanding from all P14 components."""

        # Build comparisons between each pair of books
        comparisons = self._build_comparisons(
            books, concept_result, thesis_result, argument_result,
            mechanism_result, evidence_result, contradiction_result
        )

        # Build synthesis
        synthesis = self._build_synthesis(
            collection, concept_result, thesis_result, argument_result,
            mechanism_result, evidence_result, contradiction_result,
            problem_result, gap_result, comparisons
        )

        # Build quality metrics (Q19-Q26)
        quality = self._compute_quality(
            concept_result, thesis_result, argument_result,
            mechanism_result, evidence_result, contradiction_result,
            gap_result, comparisons
        )

        return CrossBookUnderstanding(
            understanding_id=_stable_id("cbunderstanding", collection.collection_id),
            collection=collection,
            shared_problems=problem_result.crossbook_problems,
            concept_system=concept_result.unified_concepts,
            concept_relations=concept_result.concept_relations,
            thesis_system=thesis_result.crossbook_theses,
            thesis_relations=thesis_result.thesis_relations,
            argument_system=argument_result.crossbook_arguments,
            argument_relations=argument_result.argument_relations,
            mechanism_system=mechanism_result.crossbook_mechanisms,
            mechanism_relations=mechanism_result.mechanism_relations,
            evidence_system=evidence_result.crossbook_evidence,
            evidence_relations=evidence_result.evidence_relations,
            contradictions=contradiction_result.contradictions,
            comparisons=comparisons,
            knowledge_gaps=gap_result.knowledge_gaps,
            synthesis=synthesis,
            quality=quality,
        )

    def _build_comparisons(
        self,
        books: list[tuple[Any, Any]],
        concept_result: Any,
        thesis_result: Any,
        argument_result: Any,
        mechanism_result: Any,
        evidence_result: Any,
        contradiction_result: Any,
    ) -> list[CrossBookComparison]:
        """Build pairwise comparisons between all books."""
        comparisons = []
        book_ids = [bu.book_id for bu, _ in books]

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]

                # Filter relations for this book pair
                concept_rels = [r for r in concept_result.concept_relations
                              if (r.source_book_id == book_a_id and r.target_book_id == book_b_id) or
                                 (r.source_book_id == book_b_id and r.target_book_id == book_a_id)]
                thesis_rels = [r for r in thesis_result.thesis_relations
                              if (r.source_thesis.book_id == book_a_id and r.target_thesis.book_id == book_b_id) or
                                 (r.source_thesis.book_id == book_b_id and r.target_thesis.book_id == book_a_id)]
                argument_rels = [r for r in argument_result.argument_relations
                               if (r.source_argument.book_id == book_a_id and r.target_argument.book_id == book_b_id) or
                                  (r.source_argument.book_id == book_b_id and r.target_argument.book_id == book_a_id)]
                mechanism_rels = [r for r in mechanism_result.mechanism_relations
                                if (r.source_mechanism.book_id == book_a_id and r.target_mechanism.book_id == book_b_id) or
                                   (r.source_mechanism.book_id == book_b_id and r.target_mechanism.book_id == book_a_id)]
                evidence_rels = [r for r in evidence_result.evidence_relations
                               if (r.source_evidence.book_id == book_a_id and r.target_evidence.book_id == book_b_id) or
                                  (r.source_evidence.book_id == book_b_id and r.target_evidence.book_id == book_a_id)]
                contradictions = [c for c in contradiction_result.contradictions
                                if (c.book_a_id == book_a_id and c.book_b_id == book_b_id) or
                                   (c.book_a_id == book_b_id and c.book_b_id == book_a_id)]

                comparison = CrossBookComparison(
                    comparison_id=_stable_id("comp", book_a_id, book_b_id),
                    book_a_id=book_a_id,
                    book_b_id=book_b_id,
                    concept_relations=concept_rels,
                    thesis_relations=thesis_rels,
                    argument_relations=argument_rels,
                    mechanism_relations=mechanism_rels,
                    evidence_relations=evidence_rels,
                    contradictions=contradictions,
                    problem_relations=[],  # Would need problem_result
                    author_relations=[],   # Would need author comparison
                )
                comparisons.append(comparison)

        return comparisons

    def _build_synthesis(
        self,
        collection: CrossBookCollection,
        concept_result: Any,
        thesis_result: Any,
        argument_result: Any,
        mechanism_result: Any,
        evidence_result: Any,
        contradiction_result: Any,
        problem_result: Any,
        gap_result: Any,
        comparisons: list[CrossBookComparison],
    ) -> CrossBookSynthesis:
        """Build the final cross-book synthesis."""

        # Common ground: concepts with SAME_CONCEPT relations
        common_ground = []
        for rel in concept_result.concept_relations:
            if rel.relation.value == "SAME_CONCEPT":
                common_ground.append(
                    f"{rel.source_concept_id} ({rel.source_book_id}) == {rel.target_concept_id} ({rel.target_book_id})"
                )

        # Major differences: concepts with SAME_TERM_DIFFERENT_MEANING or DEFINITIONAL_CONFLICT
        major_differences = []
        for rel in concept_result.concept_relations:
            if rel.relation.value in ("SAME_TERM_DIFFERENT_MEANING", "RELATED_CONCEPT"):
                major_differences.append(
                    f"Term '{rel.source_concept_id}' differs: {rel.source_book_id} vs {rel.target_book_id}"
                )
        for c in contradiction_result.contradictions:
            if c.type.value == "DEFINITIONAL_CONFLICT":
                major_differences.append(
                    f"Definitional conflict: {c.element_a} vs {c.element_b} ({c.book_a_id} vs {c.book_b_id})"
                )

        # Concept evolution
        concept_evolution = concept_result.concept_evolutions

        # Supporting theories: theses that SUPPORT each other
        supporting_theories = []
        for rel in thesis_result.thesis_relations:
            if rel.relation.value == "SUPPORTS":
                supporting_theories.append(
                    f"{rel.source_thesis.statement[:60]}... SUPPORTS {rel.target_thesis.statement[:60]}..."
                )

        # Competing theories: theses that CONTRADICT or are ALTERNATIVE
        competing_theories = []
        for rel in thesis_result.thesis_relations:
            if rel.relation.value in ("CONTRADICTS", "ALTERNATIVE"):
                competing_theories.append(
                    f"{rel.source_thesis.statement[:60]}... {rel.relation.value} {rel.target_thesis.statement[:60]}..."
                )
        for c in contradiction_result.contradictions:
            if c.type.value == "THEORETICAL_CONFLICT":
                competing_theories.append(
                    f"Theoretical conflict: {c.element_a} vs {c.element_b} ({c.book_a_id} vs {c.book_b_id})"
                )

        # Evidence convergence: CONVERGENT evidence
        evidence_convergence = []
        for rel in evidence_result.evidence_relations:
            if rel.relation.value == "CONVERGENT":
                evidence_convergence.append(
                    f"Convergent evidence: {rel.source_evidence.claim_id} ({rel.source_evidence.book_id}) ~ {rel.target_evidence.claim_id} ({rel.target_evidence.book_id})"
                )

        # Evidence divergence: CONFLICTING/DIVERGENT evidence
        evidence_divergence = []
        for rel in evidence_result.evidence_relations:
            if rel.relation.value in ("CONFLICTING", "DIVERGENT"):
                evidence_divergence.append(
                    f"Divergent evidence: {rel.source_evidence.claim_id} ({rel.source_evidence.book_id}) {rel.relation.value} {rel.target_evidence.claim_id} ({rel.target_evidence.book_id})"
                )

        # Unresolved conflicts
        unresolved_conflicts = contradiction_result.contradictions

        # Knowledge gaps
        knowledge_gaps = gap_result.knowledge_gaps

        # Higher-order synthesis
        higher_order = self._generate_higher_order_synthesis(
            concept_result, thesis_result, argument_result,
            evidence_result, contradiction_result, gap_result
        )

        # Traceability
        traceability = {
            "concepts": _flatten_traceability(concept_result.traceability),
            "theses": _flatten_traceability(thesis_result.traceability),
            "arguments": _flatten_traceability(argument_result.traceability),
            "mechanisms": _flatten_traceability(mechanism_result.traceability),
            "evidence": _flatten_traceability(evidence_result.traceability),
            "contradictions": _flatten_traceability(contradiction_result.traceability),
            "problems": _flatten_traceability(problem_result.traceability) if problem_result else [],
            "gaps": _flatten_traceability(gap_result.traceability),
        }

        return CrossBookSynthesis(
            synthesis_id=_stable_id("cbs", collection.collection_id),
            collection_id=collection.collection_id,
            common_ground=common_ground,
            major_differences=major_differences,
            concept_evolution=concept_evolution,
            supporting_theories=supporting_theories,
            competing_theories=competing_theories,
            evidence_convergence=evidence_convergence,
            evidence_divergence=evidence_divergence,
            unresolved_conflicts=unresolved_conflicts,
            knowledge_gaps=knowledge_gaps,
            higher_order_synthesis=higher_order,
            traceability=traceability,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _generate_higher_order_synthesis(
        self,
        concept_result: Any,
        thesis_result: Any,
        argument_result: Any,
        evidence_result: Any,
        contradiction_result: Any,
        gap_result: Any,
    ) -> str:
        """Generate higher-order synthesis narrative."""
        parts = []

        # Conceptual unity
        same_concept_count = sum(1 for r in concept_result.concept_relations if r.relation.value == "SAME_CONCEPT")
        diff_concept_count = sum(1 for r in concept_result.concept_relations if r.relation.value == "SAME_TERM_DIFFERENT_MEANING")
        if same_concept_count > 0 or diff_concept_count > 0:
            parts.append(f"Conceptual analysis reveals {same_concept_count} unified concepts and {diff_concept_count} terminological divergences.")

        # Theoretical landscape
        supporting = sum(1 for r in thesis_result.thesis_relations if r.relation.value == "SUPPORTS")
        competing = sum(1 for r in thesis_result.thesis_relations if r.relation.value in ("CONTRADICTS", "ALTERNATIVE"))
        if supporting > 0 or competing > 0:
            parts.append(f"Theoretical landscape shows {supporting} supporting relations and {competing} competing/alternative positions.")

        # Evidence landscape
        convergent = sum(1 for r in evidence_result.evidence_relations if r.relation.value == "CONVERGENT")
        divergent = sum(1 for r in evidence_result.evidence_relations if r.relation.value in ("CONFLICTING", "DIVERGENT"))
        if convergent > 0 or divergent > 0:
            parts.append(f"Evidence landscape shows {convergent} convergent and {divergent} divergent relations.")

        # Contradictions
        contra_count = len(contradiction_result.contradictions)
        if contra_count > 0:
            parts.append(f"{contra_count} contradictions detected across books.")

        # Knowledge gaps
        gap_count = len(gap_result.knowledge_gaps)
        if gap_count > 0:
            parts.append(f"{gap_count} knowledge gaps identified, including unanswered questions and weakly supported claims.")

        return " ".join(parts) if parts else "No significant cross-book patterns detected."

    def _compute_quality(
        self,
        concept_result: Any,
        thesis_result: Any,
        argument_result: Any,
        mechanism_result: Any,
        evidence_result: Any,
        contradiction_result: Any,
        gap_result: Any,
        comparisons: list[CrossBookComparison],
    ) -> dict[str, Any]:
        """Compute Q19-Q26 quality metrics."""

        # Q19: Cross-Book Alignment - concept relation density
        total_concepts = len(concept_result.unified_concepts)
        total_possible_concept_pairs = total_concepts * (total_concepts - 1) // 2 if total_concepts >= 2 else 1
        actual_concept_relations = len(concept_result.concept_relations)
        q19 = min(1.0, actual_concept_relations / max(1, total_possible_concept_pairs))

        # Q20: Concept Identity Accuracy - precision of SAME_CONCEPT relations
        same_concept = [r for r in concept_result.concept_relations if r.relation.value == "SAME_CONCEPT"]
        total_concept_rels = len(concept_result.concept_relations)
        q20 = len(same_concept) / max(1, total_concept_rels) if total_concept_rels > 0 else 0

        # Q21: Thesis Comparison Integrity
        thesis_rels_with_evidence = [r for r in thesis_result.thesis_relations if r.evidence]
        q21 = len(thesis_rels_with_evidence) / max(1, len(thesis_result.thesis_relations))

        # Q22: Cross-Book Argument Validity
        arg_rels_with_evidence = [r for r in argument_result.argument_relations if r.evidence]
        q22 = len(arg_rels_with_evidence) / max(1, len(argument_result.argument_relations))

        # Q23: Evidence Independence - fraction of relations that are CONVERGENT (independent evidence)
        convergent_evidence = [r for r in evidence_result.evidence_relations if r.relation.value == "CONVERGENT"]
        q23 = len(convergent_evidence) / max(1, len(evidence_result.evidence_relations))

        # Q24: Contradiction Integrity - all contradictions classified
        classified_contra = [c for c in contradiction_result.contradictions if c.type.value != "UNRESOLVED"]
        q24 = len(classified_contra) / max(1, len(contradiction_result.contradictions))

        # Q25: Knowledge Gap Integrity
        grounded_gaps = [g for g in gap_result.knowledge_gaps if g.reason]
        q25 = len(grounded_gaps) / max(1, len(gap_result.knowledge_gaps))

        # Q26: Cross-Book Traceability - all relations have traceability
        all_rels = (len(concept_result.concept_relations) +
                   len(thesis_result.thesis_relations) +
                   len(argument_result.argument_relations) +
                   len(mechanism_result.mechanism_relations) +
                   len(evidence_result.evidence_relations) +
                   len(contradiction_result.contradictions))
        q26 = 1.0 if all_rels > 0 else 0

        return {
            "Q19_crossbook_alignment": round(q19, 3),
            "Q20_concept_identity_accuracy": round(q20, 3),
            "Q21_thesis_comparison_integrity": round(q21, 3),
            "Q22_crossbook_argument_validity": round(q22, 3),
            "Q23_evidence_independence": round(q23, 3),
            "Q24_contradiction_integrity": round(q24, 3),
            "Q25_knowledge_gap_integrity": round(q25, 3),
            "Q26_crossbook_traceability": round(q26, 3),
        }