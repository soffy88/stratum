"""P13: Synthesis Expression Generator.

Generates human-readable expressions from BookSynthesis (read-only, non-authoritative).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    BookThesis,
    ConceptRole,
    ContradictionType,
)


@dataclass
class BookExpression:
    """Generated expression artifact."""
    executive_summary: str
    full_explanation: str
    concept_map: str
    argument_map: str
    chapter_by_chapter: str
    author_position: str
    limitations: str
    unresolved_questions: str


class SynthesisExpressionGenerator:
    """Generate expressions from BookSynthesis."""

    def generate(self, synthesis: BookSynthesis) -> BookExpression:
        return BookExpression(
            executive_summary=self._executive_summary(synthesis),
            full_explanation=self._full_explanation(synthesis),
            concept_map=self._concept_map(synthesis),
            argument_map=self._argument_map(synthesis),
            chapter_by_chapter=self._chapter_by_chapter(synthesis),
            author_position=self._author_position(synthesis),
            limitations=self._limitations(synthesis),
            unresolved_questions=self._unresolved_questions(synthesis),
        )

    def _executive_summary(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "BOOK SYNTHESIS — EXECUTIVE SUMMARY",
            f"Book: {s.book_id}  Run: {s.run_id}",
            "=" * 80,
            "",
            "PROBLEM & THESIS",
            s.problem_definition or "Not extracted",
            "",
        ]
        if s.thesis.core_thesis:
            lines += [
                f"Core Thesis: {s.thesis.core_thesis.statement}",
                f"  Confidence: {s.thesis.core_thesis.confidence:.2f}  Provenance: {s.thesis.core_thesis.provenance.value}",
                "",
            ]
        if s.thesis.supporting_theses:
            lines.append(f"Supporting Theses ({len(s.thesis.supporting_theses)}):")
            for t in s.thesis.supporting_theses[:3]:
                lines.append(f"  - {t.statement[:120]}")
            lines.append("")
        lines += [
            f"Concept System: {len(s.concept_system.foundational)} foundational, {len(s.concept_system.core)} core, {len(s.concept_system.derived)} derived, {len(s.concept_system.application)} application",
            f"Arguments: {len(s.argument_system.thesis_arguments)} thesis-level, {len(s.argument_system.major_arguments)} major, {len(s.argument_system.sub_arguments)} sub",
            f"Mechanisms: {len(s.mechanism_system.mechanisms)} identified",
            f"Evidence Coverage: {s.evidence_map.evidence_coverage:.0%} ({s.evidence_map.unsupported_claim_count} unsupported claims)",
            f"Contradictions: {len(s.contradictions.contradictions)} detected",
            f"Unresolved Questions: {len(s.unresolved_questions)}",
            "",
        ]
        return "\n".join(lines)

    def _full_explanation(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "FULL BOOK EXPLANATION",
            "=" * 80,
            "",
            "1. WHAT PROBLEM DOES THE BOOK SOLVE?",
            s.problem_definition or "Not extracted",
            "",
            "2. WHAT IS THE CENTRAL THESIS?",
        ]
        if s.thesis.core_thesis:
            lines.append(f"   {s.thesis.core_thesis.statement}")
            lines.append(f"   (Confidence: {s.thesis.core_thesis.confidence:.2f}, Provenance: {s.thesis.core_thesis.provenance.value})")
        else:
            lines.append("   No core thesis extracted")
        lines.append("")

        lines += [
            "3. HOW IS THE THESIS CONSTRUCTED?",
            f"   {len(s.thesis.supporting_theses)} supporting theses, {len(s.argument_system.thesis_arguments)} thesis-level argument chains",
            "",
            "4. FOUNDATIONAL CONCEPTS:",
        ]
        for c in s.concept_system.foundational[:5]:
            lines.append(f"   - {c.label}: {c.definition[:100]}")
        lines.append("")

        lines += [
            "5. MAJOR ARGUMENTS:",
        ]
        for a in s.argument_system.major_arguments[:5]:
            lines.append(f"   - {a.what[:80]}")
            lines.append(f"     Evidence: {len(a.evidence_refs)} items | Status: {a.status.value}")
        lines.append("")

        lines += [
            "6. KEY MECHANISMS:",
        ]
        for m in s.mechanism_system.mechanisms[:5]:
            lines.append(f"   - {m.operation[:100]}")
            lines.append(f"     Trigger: {m.trigger[:80]} | Outcome: {m.outcome[:80]}")
        lines.append("")

        lines += [
            "7. EVIDENCE SUPPORT:",
            f"   Coverage: {s.evidence_map.evidence_coverage:.0%}",
            f"   Unsupported claims: {s.evidence_map.unsupported_claim_count}",
            f"   Model inference ratio: {s.evidence_map.model_inference_ratio:.0%}",
            "",
            "8. LIMITATIONS & CONTRADICTIONS:",
        ]
        for lim in s.limitations[:5]:
            lines.append(f"   - {lim}")
        for c in s.contradictions.contradictions[:3]:
            lines.append(f"   - [{c.type.value}] {c.description}")
        lines.append("")

        return "\n".join(lines)

    def _concept_map(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "CONCEPT MAP",
            "=" * 80,
            "",
        ]
        for role in [ConceptRole.FOUNDATIONAL, ConceptRole.CORE, ConceptRole.DERIVED, ConceptRole.BRIDGING, ConceptRole.APPLICATION, ConceptRole.TERMINAL]:
            concepts = getattr(s.concept_system, role.value.lower(), [])
            if concepts:
                lines.append(f"{role.value} ({len(concepts)}):")
                for c in concepts[:10]:
                    prereq = f" ← {', '.join(c.prerequisites[:3])}" if c.prerequisites else ""
                    lines.append(f"  - {c.label}{prereq}")
                    if c.applied_in:
                        lines.append(f"    Applied in: {', '.join(c.applied_in[:3])}")
                lines.append("")
        return "\n".join(lines)

    def _argument_map(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "ARGUMENT MAP",
            "=" * 80,
            "",
            "THESIS-LEVEL:",
        ]
        for a in s.argument_system.thesis_arguments:
            lines.append(f"  {a.what[:100]}")
            lines.append(f"    Evidence: {len(a.evidence_refs)} | Status: {a.status.value} | Confidence: {a.confidence:.2f}")
        lines.append("")
        lines.append("MAJOR ARGUMENTS:")
        for a in s.argument_system.major_arguments:
            lines.append(f"  {a.what[:100]}")
            lines.append(f"    Why: {a.why[:100]}")
            lines.append(f"    How: {a.how[:100]}")
            lines.append(f"    Conclusion: {a.conclusion[:100]}")
            lines.append(f"    Depends on: {', '.join(a.depends_on) if a.depends_on else '—'}")
            lines.append(f"    Status: {a.status.value} | Confidence: {a.confidence:.2f}")
            lines.append("")
        return "\n".join(lines)

    def _chapter_by_chapter(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "CHAPTER-BY-CHAPTER REASONING",
            "=" * 80,
            "",
        ]
        for assignment in s.chapter_roles.assignments:
            roles_str = ", ".join(r.value for r in assignment.roles)
            lines.append(f"{assignment.chapter_id} — {roles_str} (confidence: {assignment.confidence:.2f})")
            lines.append(f"  {assignment.evidence}")
            lines.append("")
        return "\n".join(lines)

    def _author_position(self, s: BookSynthesis) -> str:
        am = s.author_model
        lines = [
            "=" * 80,
            "AUTHOR POSITION MODEL",
            "=" * 80,
            "",
        ]
        if am.worldview:
            lines.append("Worldview:")
            for w in am.worldview:
                lines.append(f"  - {w}")
            lines.append("")
        if am.assumptions:
            lines.append("Key Assumptions:")
            for a in am.assumptions:
                lines.append(f"  - {a}")
            lines.append("")
        if am.explanatory_strategy:
            lines.append("Explanatory Strategy:")
            for e in am.explanatory_strategy:
                lines.append(f"  - {e}")
            lines.append("")
        if am.argument_style:
            lines.append("Argument Style:")
            for a in am.argument_style:
                lines.append(f"  - {a}")
            lines.append("")
        if am.evidence_preference:
            lines.append("Evidence Preference:")
            for e in am.evidence_preference:
                lines.append(f"  - {e}")
            lines.append("")
        return "\n".join(lines)

    def _limitations(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "LIMITATIONS",
            "=" * 80,
            "",
        ]
        if s.limitations:
            for lim in s.limitations:
                lines.append(f"  - {lim}")
        else:
            lines.append("  (none recorded)")
        lines.append("")
        if s.contradictions.contradictions:
            lines.append("Contradictions:")
            for c in s.contradictions.contradictions:
                lines.append(f"  [{c.type.value}] {c.description} (confidence: {c.confidence:.2f})")
        return "\n".join(lines)

    def _unresolved_questions(self, s: BookSynthesis) -> str:
        lines = [
            "=" * 80,
            "UNRESOLVED QUESTIONS",
            "=" * 80,
            "",
        ]
        if s.unresolved_questions:
            for q in s.unresolved_questions:
                lines.append(f"  - {q}")
        else:
            lines.append("  (none recorded)")
        return "\n".join(lines)