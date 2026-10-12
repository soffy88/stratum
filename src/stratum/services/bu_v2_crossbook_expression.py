"""P14: Cross-Book Expression Generator.

Generates human-readable expressions of cross-book intelligence.
"""

from __future__ import annotations

from typing import Any

from stratum.knowledge.bu_v2_models import (
    CrossBookCollection,
    CrossBookComparison,
    CrossBookConcept,
    CrossBookConceptRelation,
    CrossBookContradiction,
    CrossBookKnowledgeGap,
    CrossBookProblem,
    CrossBookSynthesis,
    CrossBookThesis,
    CrossBookUnderstanding,
)


class BU2CrossBookExpressionGenerator:
    """Generates expressions from cross-book understanding."""

    def __init__(self):
        pass

    def generate(self, understanding: CrossBookUnderstanding) -> "CrossBookExpression":
        """Generate all expression types for the understanding."""
        return CrossBookExpression(
            collection_id=understanding.collection.collection_id,
            collection_name=understanding.collection.name,
            book_count=len(understanding.collection.book_ids),
            concept_summary=self._generate_concept_summary(understanding),
            thesis_summary=self._generate_thesis_summary(understanding),
            argument_summary=self._generate_argument_summary(understanding),
            contradiction_summary=self._generate_contradiction_summary(understanding),
            gap_summary=self._generate_gap_summary(understanding),
            synthesis=self._generate_synthesis(understanding),
            pairwise_comparisons=self._generate_pairwise_comparisons(understanding),
            quality=self._generate_quality_summary(understanding),
        )

    def _generate_concept_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate concept alignment summary."""
        total = len(understanding.concept_system)
        if total == 0:
            return "No cross-book concepts identified."

        same = sum(1 for r in understanding.concept_relations if r.relation.value == "SAME_CONCEPT")
        diff = sum(1 for r in understanding.concept_relations if r.relation.value == "SAME_TERM_DIFFERENT_MEANING")
        related = sum(1 for r in understanding.concept_relations if r.relation.value == "RELATED_CONCEPT")

        return (
            f"Concept alignment across {len(understanding.collection.book_ids)} books: "
            f"{total} unified concepts, {same} identical, {diff} terminological divergences, "
            f"{related} related concepts."
        )

    def _generate_thesis_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate thesis comparison summary."""
        total = len(understanding.thesis_system)
        if total == 0:
            return "No theses available for comparison."

        supports = sum(1 for r in understanding.thesis_relations if r.relation.value == "SUPPORTS")
        contradicts = sum(1 for r in understanding.thesis_relations if r.relation.value == "CONTRADICTS")
        alternative = sum(1 for r in understanding.thesis_relations if r.relation.value == "ALTERNATIVE")

        return (
            f"Thesis comparison: {total} theses across books, "
            f"{supports} supporting, {contradicts} contradicting, {alternative} alternative relations."
        )

    def _generate_argument_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate argument comparison summary."""
        total = len(understanding.argument_system)
        if total == 0:
            return "No arguments available for comparison."

        supports = sum(1 for r in understanding.argument_relations if r.relation.value == "SUPPORTS")
        extends = sum(1 for r in understanding.argument_relations if r.relation.value == "EXTENDS")
        transfers = len(understanding.argument_relations)  # Would need transfer tracking

        return (
            f"Argument comparison: {total} arguments, "
            f"{supports} supporting, {extends} extending relations."
        )

    def _generate_contradiction_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate contradiction summary."""
        total = len(understanding.contradictions)
        if total == 0:
            return "No contradictions detected across books."

        by_type = {}
        for c in understanding.contradictions:
            by_type[c.type.value] = by_type.get(c.type.value, 0) + 1

        type_str = ", ".join(f"{v} {k}" for k, v in by_type.items())
        return f"Contradictions detected: {total} total ({type_str})."

    def _generate_gap_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate knowledge gap summary."""
        total = len(understanding.knowledge_gaps)
        if total == 0:
            return "No knowledge gaps detected."

        by_type = {}
        for g in understanding.knowledge_gaps:
            by_type[g.type.value] = by_type.get(g.type.value, 0) + 1

        type_str = ", ".join(f"{v} {k}" for k, v in by_type.items())
        return f"Knowledge gaps: {total} total ({type_str})."

    def _generate_synthesis(self, understanding: CrossBookUnderstanding) -> str:
        """Generate full synthesis expression."""
        synth = understanding.synthesis
        if not synth:
            return "No synthesis available."

        parts = []

        if synth.common_ground:
            parts.append(f"Common Ground ({len(synth.common_ground)}):\n" +
                        "\n".join(f"  - {c}" for c in synth.common_ground[:5]))

        if synth.major_differences:
            parts.append(f"Major Differences ({len(synth.major_differences)}):\n" +
                        "\n".join(f"  - {d}" for d in synth.major_differences[:5]))

        if synth.supporting_theories:
            parts.append(f"Supporting Theories ({len(synth.supporting_theories)}):\n" +
                        "\n".join(f"  - {t}" for t in synth.supporting_theories[:5]))

        if synth.competing_theories:
            parts.append(f"Competing Theories ({len(synth.competing_theories)}):\n" +
                        "\n".join(f"  - {t}" for t in synth.competing_theories[:5]))

        if synth.evidence_convergence:
            parts.append(f"Evidence Convergence ({len(synth.evidence_convergence)}):\n" +
                        "\n".join(f"  - {e}" for e in synth.evidence_convergence[:5]))

        if synth.evidence_divergence:
            parts.append(f"Evidence Divergence ({len(synth.evidence_divergence)}):\n" +
                        "\n".join(f"  - {e}" for e in synth.evidence_divergence[:5]))

        if synth.unresolved_conflicts:
            parts.append(f"Unresolved Conflicts ({len(synth.unresolved_conflicts)}):\n" +
                        "\n".join(f"  - {c.description[:80]}..." for c in synth.unresolved_conflicts[:5]))

        if synth.knowledge_gaps:
            parts.append(f"Knowledge Gaps ({len(synth.knowledge_gaps)}):\n" +
                        "\n".join(f"  - {g.description[:80]}..." for g in synth.knowledge_gaps[:5]))

        if synth.higher_order_synthesis:
            parts.append(f"Higher-Order Synthesis:\n  {synth.higher_order_synthesis}")

        return "\n\n".join(parts) if parts else "No synthesis content generated."

    def _generate_pairwise_comparisons(self, understanding: CrossBookUnderstanding) -> str:
        """Generate pairwise comparison summaries."""
        if not understanding.comparisons:
            return "No pairwise comparisons available."

        parts = []
        for comp in understanding.comparisons:
            parts.append(
                f"{comp.book_a_id} vs {comp.book_b_id}:\n"
                f"  Concept relations: {len(comp.concept_relations)}\n"
                f"  Thesis relations: {len(comp.thesis_relations)}\n"
                f"  Argument relations: {len(comp.argument_relations)}\n"
                f"  Mechanism relations: {len(comp.mechanism_relations)}\n"
                f"  Evidence relations: {len(comp.evidence_relations)}\n"
                f"  Contradictions: {len(comp.contradictions)}"
            )
        return "\n\n".join(parts)

    def _generate_quality_summary(self, understanding: CrossBookUnderstanding) -> str:
        """Generate quality metrics summary."""
        q = understanding.quality
        if not q:
            return "No quality metrics available."

        lines = ["Quality Metrics (Q19-Q26):"]
        for key in ["Q19_crossbook_alignment", "Q20_concept_identity_accuracy",
                    "Q21_thesis_comparison_integrity", "Q22_crossbook_argument_validity",
                    "Q23_evidence_independence", "Q24_contradiction_integrity",
                    "Q25_knowledge_gap_integrity", "Q26_crossbook_traceability"]:
            if key in q:
                lines.append(f"  {key}: {q[key]:.3f}")

        return "\n".join(lines)


class CrossBookExpression:
    """Complete cross-book expression."""

    def __init__(
        self,
        collection_id: str,
        collection_name: str,
        book_count: int,
        concept_summary: str,
        thesis_summary: str,
        argument_summary: str,
        contradiction_summary: str,
        gap_summary: str,
        synthesis: str,
        pairwise_comparisons: str,
        quality: str,
    ):
        self.collection_id = collection_id
        self.collection_name = collection_name
        self.book_count = book_count
        self.concept_summary = concept_summary
        self.thesis_summary = thesis_summary
        self.argument_summary = argument_summary
        self.contradiction_summary = contradiction_summary
        self.gap_summary = gap_summary
        self.synthesis = synthesis
        self.pairwise_comparisons = pairwise_comparisons
        self.quality = quality

    def render(self) -> str:
        """Render the complete expression."""
        return (
            f"=== CROSS-BOOK UNDERSTANDING ===\n"
            f"Collection: {self.collection_name} ({self.collection_id})\n"
            f"Books: {self.book_count}\n\n"
            f"{self.concept_summary}\n\n"
            f"{self.thesis_summary}\n\n"
            f"{self.argument_summary}\n\n"
            f"{self.contradiction_summary}\n\n"
            f"{self.gap_summary}\n\n"
            f"--- SYNTHESIS ---\n{self.synthesis}\n\n"
            f"--- PAIRWISE COMPARISONS ---\n{self.pairwise_comparisons}\n\n"
            f"--- QUALITY ---\n{self.quality}\n"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "collection_name": self.collection_name,
            "book_count": self.book_count,
            "concept_summary": self.concept_summary,
            "thesis_summary": self.thesis_summary,
            "argument_summary": self.argument_summary,
            "contradiction_summary": self.contradiction_summary,
            "gap_summary": self.gap_summary,
            "synthesis": self.synthesis,
            "pairwise_comparisons": self.pairwise_comparisons,
            "quality": self.quality,
        }