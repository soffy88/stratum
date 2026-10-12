"""P13: Thesis Model Extraction.

Extracts the book's thesis structure from P12 artefacts with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookThesis,
    BookThesisModel,
    BookUnderstandingV2,
    ChapterUnderstanding,
    ThesisProvenance,
    ThesisType,
)
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class ThesisAnalysis:
    model: BookThesisModel
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class ThesisAnalyzer:
    """Build BookThesisModel from integrated BU and reasoning graph."""

    def analyze(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None = None,
    ) -> ThesisAnalysis:
        model = BookThesisModel()
        traceability: dict[str, list[str]] = {}

        core = self._extract_core_thesis(bu, chapters, graph)
        if core:
            model.core_thesis = core
            traceability[core.id] = core.source_locations

        model.supporting_theses = self._extract_supporting_theses(bu, chapters, graph)
        for t in model.supporting_theses:
            traceability[t.id] = t.source_locations

        model.problem_statements = self._extract_problems(bu, chapters)
        for t in model.problem_statements:
            traceability[t.id] = t.source_locations

        model.central_questions = self._extract_questions(bu, chapters)
        for t in model.central_questions:
            traceability[t.id] = t.source_locations

        model.key_assumptions = self._extract_assumptions(bu, chapters)
        for t in model.key_assumptions:
            traceability[t.id] = t.source_locations

        model.conclusions = self._extract_conclusions(bu, chapters)
        for t in model.conclusions:
            traceability[t.id] = t.source_locations

        model.limitations = self._extract_limitations(bu, chapters)
        for t in model.limitations:
            traceability[t.id] = t.source_locations

        return ThesisAnalysis(model=model, traceability=traceability)

    def _extract_core_thesis(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> BookThesis | None:
        theses = getattr(bu, "central_theses", []) or []
        if not theses:
            return None

        best_thesis = theses[0]
        evidence_refs = self._find_evidence_for_thesis(best_thesis, chapters, graph)
        supporting_args = self._find_supporting_args(best_thesis, graph)
        locations = self._find_source_locations(best_thesis, chapters)

        provenance = self._determine_provenance(best_thesis, chapters, evidence_refs)

        return BookThesis(
            id=_stable_id("thesis", "core", bu.book_id),
            type=ThesisType.CORE,
            statement=best_thesis,
            scope="book",
            evidence_refs=evidence_refs,
            supporting_arguments=supporting_args,
            confidence=0.7 if evidence_refs else 0.4,
            provenance=provenance,
            source_locations=locations,
        )

    def _extract_supporting_theses(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> list[BookThesis]:
        sub_theses = getattr(bu, "sub_theses", []) or []
        out = []
        for i, stmt in enumerate(sub_theses):
            evidence_refs = self._find_evidence_for_thesis(stmt, chapters, graph)
            supporting_args = self._find_supporting_args(stmt, graph)
            locations = self._find_source_locations(stmt, chapters)
            provenance = self._determine_provenance(stmt, chapters, evidence_refs)

            out.append(
                BookThesis(
                    id=_stable_id("thesis", "support", bu.book_id, str(i)),
                    type=ThesisType.SUPPORTING,
                    statement=stmt,
                    scope="book",
                    evidence_refs=evidence_refs,
                    supporting_arguments=supporting_args,
                    confidence=0.6 if evidence_refs else 0.3,
                    provenance=provenance,
                    source_locations=locations,
                )
            )
        return out

    def _extract_problems(
        self, bu: BookUnderstandingV2, chapters: list[ChapterUnderstanding]
    ) -> list[BookThesis]:
        questions = getattr(bu, "governing_questions", []) or []
        out = []
        for i, q in enumerate(questions):
            locations = self._find_source_locations(q, chapters)
            out.append(
                BookThesis(
                    id=_stable_id("thesis", "problem", bu.book_id, str(i)),
                    type=ThesisType.PROBLEM,
                    statement=q,
                    scope="book",
                    evidence_refs=[],
                    supporting_arguments=[],
                    confidence=0.5,
                    provenance=ThesisProvenance.AUTHOR_ASSERTED,
                    source_locations=locations,
                )
            )
        return out

    def _extract_questions(
        self, bu: BookUnderstandingV2, chapters: list[ChapterUnderstanding]
    ) -> list[BookThesis]:
        questions = getattr(bu, "governing_questions", []) or []
        out = []
        for i, q in enumerate(questions):
            locations = self._find_source_locations(q, chapters)
            out.append(
                BookThesis(
                    id=_stable_id("thesis", "question", bu.book_id, str(i)),
                    type=ThesisType.QUESTION,
                    statement=q,
                    scope="book",
                    evidence_refs=[],
                    supporting_arguments=[],
                    confidence=0.5,
                    provenance=ThesisProvenance.AUTHOR_ASSERTED,
                    source_locations=locations,
                )
            )
        return out

    def _extract_assumptions(
        self, bu: BookUnderstandingV2, chapters: list[ChapterUnderstanding]
    ) -> list[BookThesis]:
        all_assumptions = []
        for cu in chapters:
            all_assumptions.extend(cu.assumptions)
        out = []
        for i, a in enumerate(all_assumptions[:10]):
            locations = self._find_source_locations(a, chapters)
            out.append(
                BookThesis(
                    id=_stable_id("thesis", "assumption", bu.book_id, str(i)),
                    type=ThesisType.ASSUMPTION,
                    statement=a,
                    scope="book",
                    evidence_refs=[],
                    supporting_arguments=[],
                    confidence=0.4,
                    provenance=ThesisProvenance.AUTHOR_ASSERTED,
                    source_locations=locations,
                )
            )
        return out

    def _extract_conclusions(
        self, bu: BookUnderstandingV2, chapters: list[ChapterUnderstanding]
    ) -> list[BookThesis]:
        out = []
        for cu in chapters:
            for qual in cu.qualifications:
                locations = self._find_source_locations(qual, chapters)
                out.append(
                    BookThesis(
                        id=_stable_id("thesis", "conclusion", bu.book_id, cu.chapter_id),
                        type=ThesisType.CONCLUSION,
                        statement=qual,
                        scope=cu.chapter_id,
                        evidence_refs=[],
                        supporting_arguments=[],
                        confidence=0.5,
                        provenance=ThesisProvenance.AUTHOR_ASSERTED,
                        source_locations=locations,
                    )
                )
        return out[:10]

    def _extract_limitations(
        self, bu: BookUnderstandingV2, chapters: list[ChapterUnderstanding]
    ) -> list[BookThesis]:
        nk = getattr(bu, "negative_knowledge", None)
        limitations = getattr(nk, "limitations", []) if nk else []
        out = []
        for i, lim in enumerate(limitations):
            locations = self._find_source_locations(lim, chapters)
            out.append(
                BookThesis(
                    id=_stable_id("thesis", "limitation", bu.book_id, str(i)),
                    type=ThesisType.LIMITATION,
                    statement=lim,
                    scope="book",
                    evidence_refs=[],
                    supporting_arguments=[],
                    confidence=0.6,
                    provenance=ThesisProvenance.AUTHOR_ASSERTED,
                    source_locations=locations,
                )
            )
        return out

    def _find_evidence_for_thesis(
        self, thesis: str, chapters: list[ChapterUnderstanding], graph: BookReasoningGraph | None
    ) -> list[str]:
        evidence = []
        thesis_lower = thesis.lower()[:100]
        for cu in chapters:
            for ep in cu.evidence_program:
                if ep.is_supported and thesis_lower in ep.claim_ref.lower():
                    evidence.extend(ep.evidence_refs)
        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CLAIM" and thesis_lower in node.label.lower():
                    evidence.extend([e for e in node.metadata.get("evidence_refs", [])])
        return list(dict.fromkeys(evidence))[:20]

    def _find_supporting_args(self, thesis: str, graph: BookReasoningGraph | None) -> list[str]:
        if not graph:
            return []
        supporting = []
        thesis_lower = thesis.lower()[:100]
        for edge in graph.edges:
            if edge.relation_type == "SUPPORTS":
                target = graph.nodes.get(edge.target_node_id)
                if target and thesis_lower in target.label.lower():
                    supporting.append(edge.edge_id)
        return supporting[:10]

    def _find_source_locations(self, text: str, chapters: list[ChapterUnderstanding]) -> list[str]:
        locations = []
        text_lower = text.lower()[:100]
        for cu in chapters:
            if text_lower in cu.chapter_thesis.lower() or text_lower in cu.chapter_question.lower():
                locations.append(f"chapter:{cu.chapter_id}")
            for ep in cu.evidence_program:
                if text_lower in ep.claim_ref.lower():
                    locations.append(f"evidence:{cu.chapter_id}")
        return locations[:10]

    def _determine_provenance(
        self, thesis: str, chapters: list[ChapterUnderstanding], evidence_refs: list[str]
    ) -> ThesisProvenance:
        text_lower = thesis.lower()[:100]
        for cu in chapters:
            if text_lower in cu.chapter_thesis.lower() or text_lower in cu.chapter_question.lower():
                if evidence_refs:
                    return ThesisProvenance.AUTHOR_ASSERTED
                return ThesisProvenance.STRUCTURALLY_DERIVED
        return ThesisProvenance.MODEL_INFERRED
