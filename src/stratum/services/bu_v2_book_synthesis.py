"""P13: Book-Level Synthesis.

Orchestrates all P13 components to produce the final BookSynthesis.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookAuthorModel,
    BookContradictions,
    BookSynthesis,
    BookThesisModel,
    ChapterUnderstanding,
    ThesisProvenance,
)
from stratum.services.bu_v2_argument_system import ArgumentSystemBuilder
from stratum.services.bu_v2_chapter_roles import ChapterRoleAnalyzer
from stratum.services.bu_v2_concept_system import ConceptSystemBuilder
from stratum.services.bu_v2_contradiction_detector import ContradictionDetector
from stratum.services.bu_v2_evidence_map import EvidenceMapBuilder
from stratum.services.bu_v2_mechanism_analyzer import MechanismAnalyzer
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph
from stratum.services.bu_v2_thesis_analyzer import ThesisAnalyzer


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _flatten_traceability(traceability: dict[str, list[str]]) -> list[str]:
    """Flatten traceability dict into a single list of all references."""
    out = []
    for refs in traceability.values():
        if isinstance(refs, list):
            out.extend(refs)
        elif isinstance(refs, dict):
            for v in refs.values():
                if isinstance(v, list):
                    out.extend(v)
    return out


class BookSynthesisBuilder:
    """Build the complete BookSynthesis from all P12/P13 components."""

    def __init__(self):
        self.thesis_analyzer = ThesisAnalyzer()
        self.concept_builder = ConceptSystemBuilder()
        self.argument_builder = ArgumentSystemBuilder()
        self.mechanism_analyzer = MechanismAnalyzer()
        self.evidence_builder = EvidenceMapBuilder()
        self.chapter_roles = ChapterRoleAnalyzer()
        self.contradiction_detector = ContradictionDetector()

    def build(
        self,
        bu: Any,
        chapters: list[ChapterUnderstanding],
        evolution: Any = None,
        argument_analysis: Any = None,
        graph: BookReasoningGraph | None = None,
        structure: dict[str, Any] | None = None,
    ) -> BookSynthesis:
        thesis_analysis = self.thesis_analyzer.analyze(bu, chapters, graph)
        thesis_model = thesis_analysis.model

        concept_analysis = self.concept_builder.build(bu, chapters, evolution, graph)
        concept_system = concept_analysis.system

        argument_analysis_result = self.argument_builder.build(bu, chapters, thesis_model, argument_analysis, graph)
        argument_system = argument_analysis_result.system

        mechanism_analysis = self.mechanism_analyzer.analyze(bu, chapters, graph)
        mechanism_system = mechanism_analysis.system

        evidence_analysis = self.evidence_builder.build(bu, chapters, argument_analysis, graph)
        evidence_map = evidence_analysis.evidence_map

        chapter_roles_analysis = self.chapter_roles.analyze(bu, chapters, structure)
        chapter_roles = chapter_roles_analysis.roles

        contradiction_analysis = self.contradiction_detector.detect(
            bu, chapters, thesis_model, concept_system, argument_system, graph
        )
        contradictions = contradiction_analysis.contradictions

        author_model = self._build_author_model(bu, chapters, thesis_model, concept_system, argument_system, contradictions)

        unresolved_questions = list(getattr(bu, "unresolved_questions", []) or [])
        nk = getattr(bu, "negative_knowledge", None)
        if nk:
            unresolved_questions.extend(getattr(nk, "open_problems", []) or [])

        limitations = list(getattr(nk, "limitations", []) if nk else [])
        for lim in getattr(thesis_model, "limitations", []):
            limitations.append(lim.statement)

        synthesis_evidence = {
            "thesis": _flatten_traceability(thesis_analysis.traceability),
            "concepts": _flatten_traceability(concept_analysis.traceability),
            "arguments": _flatten_traceability(argument_analysis_result.traceability),
            "mechanisms": _flatten_traceability(mechanism_analysis.traceability),
            "evidence": _flatten_traceability(evidence_analysis.traceability),
            "chapter_roles": _flatten_traceability(chapter_roles_analysis.traceability),
            "contradictions": _flatten_traceability(contradiction_analysis.traceability),
        }

        return BookSynthesis(
            id=_stable_id("synthesis", bu.book_id, bu.run_id),
            run_id=bu.run_id,
            book_id=bu.book_id,
            thesis=thesis_model,
            problem_definition=self._formulate_problem(thesis_model),
            concept_system=concept_system,
            argument_system=argument_system,
            mechanism_system=mechanism_system,
            evidence_map=evidence_map,
            author_model=author_model,
            chapter_roles=chapter_roles,
            unresolved_questions=unresolved_questions,
            contradictions=contradictions,
            limitations=limitations,
            synthesis_evidence=synthesis_evidence,
            created_at=datetime.utcnow().isoformat(),
        )

    def _formulate_problem(self, thesis_model: BookThesisModel) -> str:
        problems = [p.statement for p in thesis_model.problem_statements]
        questions = [q.statement for q in thesis_model.central_questions]
        parts = []
        if problems:
            parts.append("Problems: " + "; ".join(problems[:3]))
        if questions:
            parts.append("Questions: " + "; ".join(questions[:3]))
        if thesis_model.core_thesis:
            parts.append("Central thesis: " + thesis_model.core_thesis.statement)
        return " | ".join(parts) if parts else "Problem definition not extracted"

    def _build_author_model(
        self,
        bu: Any,
        chapters: list[ChapterUnderstanding],
        thesis_model: BookThesisModel,
        concept_system: Any,
        argument_system: Any,
        contradictions: BookContradictions,
    ) -> BookAuthorModel:
        worldview = []
        assumptions = []
        explanatory_strategy = []
        argument_style = []
        recurring_patterns = []
        evidence_preference = []
        limitations = []
        unresolved_positions = []

        if thesis_model.core_thesis:
            worldview.append(f"Centers the book on: {thesis_model.core_thesis.statement[:200]}")

        for p in thesis_model.key_assumptions:
            assumptions.append(p.statement)

        arg_count = len(argument_system.all_arguments()) if argument_system else 0
        if arg_count > 5:
            argument_style.append("Builds extensive hierarchical argument structure")
        elif arg_count > 0:
            argument_style.append("Uses focused argument chains")

        concept_count = len(concept_system.all_concepts()) if concept_system else 0
        if concept_count > 10:
            explanatory_strategy.append("Develops a large concept system with systematic evolution")
        elif concept_count > 0:
            explanatory_strategy.append("Introduces and refines core concepts progressively")

        evidence_map = getattr(bu, "concept_system", {}).get("evidence_map", {})
        if evidence_map:
            coverage = evidence_map.get("evidence_coverage", 0)
            if coverage > 0.7:
                evidence_preference.append("Strong preference for direct evidence and worked examples")
            elif coverage > 0.4:
                evidence_preference.append("Moderate evidence traceability with some gaps")
            else:
                evidence_preference.append("Limited explicit evidence linkage")

        for contra in contradictions.contradictions:
            if contra.type.value == "DIRECT_CONTRADICTION":
                limitations.append(f"Contains direct contradiction: {contra.description}")
            elif contra.type.value == "CONTEXTUAL_DIFFERENCE":
                unresolved_positions.append(f"Contextual difference in {contra.element_type}: {contra.description}")

        return BookAuthorModel(
            worldview=worldview,
            assumptions=assumptions,
            explanatory_strategy=explanatory_strategy,
            argument_style=argument_style,
            recurring_patterns=recurring_patterns,
            evidence_preference=evidence_preference,
            limitations=limitations,
            unresolved_positions=unresolved_positions,
            provenance=ThesisProvenance.MODEL_INFERRED,
        )