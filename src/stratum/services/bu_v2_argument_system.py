"""P13: Argument System Extraction.

Builds the book's argument hierarchy from P12 argument analysis with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    ArgumentStatus,
    BookArgument,
    BookArgumentSystem,
    BookThesisModel,
    BookUnderstandingV2,
    ChapterUnderstanding,
    ThesisProvenance,
)
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class ArgumentSystemAnalysis:
    system: BookArgumentSystem
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class ArgumentSystemBuilder:
    """Build BookArgumentSystem from P12 argument analysis and reasoning graph."""

    def build(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        thesis_model: BookThesisModel,
        argument_analysis: ArgumentAnalysis | None = None,
        graph: BookReasoningGraph | None = None,
    ) -> ArgumentSystemAnalysis:
        system = BookArgumentSystem()
        traceability: dict[str, list[str]] = {}

        if thesis_model.core_thesis:
            thesis_args = self._build_thesis_arguments(
                thesis_model.core_thesis, chapters, argument_analysis, graph
            )
            system.thesis_arguments = thesis_args
            for a in thesis_args:
                traceability[a.id] = a.source_chapters

        major_args = self._build_major_arguments(bu, chapters, argument_analysis, graph)
        system.major_arguments = major_args
        for a in major_args:
            traceability[a.id] = a.source_chapters

        sub_args = self._build_sub_arguments(bu, chapters, argument_analysis, graph)
        system.sub_arguments = sub_args
        for a in sub_args:
            traceability[a.id] = a.source_chapters

        return ArgumentSystemAnalysis(system=system, traceability=traceability)

    def _build_thesis_arguments(
        self,
        core_thesis: Any,
        chapters: list[ChapterUnderstanding],
        argument_analysis: ArgumentAnalysis | None,
        graph: BookReasoningGraph | None,
    ) -> list[BookArgument]:
        out = []
        if not argument_analysis or not argument_analysis.chains:
            return out

        for i, chain in enumerate(argument_analysis.chains[:3]):
            if not chain.complete:
                continue
            evidence_refs = []
            for ev in chain.evidence:
                evidence_refs.extend(ev.evidence_refs)
            source_chapters = [chain.chapter_id] if chain.chapter_id else []
            status = self._determine_status(chain, evidence_refs)

            out.append(BookArgument(
                id=_stable_id("arg", "thesis", chain.chain_id),
                level=0,
                what=chain.claim.label,
                why=self._build_why(chain),
                how=self._build_how(chain),
                evidence_refs=evidence_refs,
                depends_on=[],
                conclusion=chain.conclusion.label if chain.conclusion else "",
                status=status,
                confidence=chain.claim.confidence,
                source_chapters=source_chapters,
            ))
        return out

    def _build_major_arguments(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        argument_analysis: ArgumentAnalysis | None,
        graph: BookReasoningGraph | None,
    ) -> list[BookArgument]:
        out = []
        if not argument_analysis or not argument_analysis.chains:
            return out

        for i, chain in enumerate(argument_analysis.chains[3:8]):
            if not chain.claim:
                continue
            evidence_refs = []
            for ev in chain.evidence:
                evidence_refs.extend(ev.evidence_refs)
            source_chapters = [chain.chapter_id] if chain.chapter_id else []
            depends_on = [a.id for a in out[-2:]] if out else []
            status = self._determine_status(chain, evidence_refs)

            out.append(BookArgument(
                id=_stable_id("arg", "major", bu.book_id, str(i)),
                level=1,
                what=chain.claim.label,
                why=self._build_why(chain),
                how=self._build_how(chain),
                evidence_refs=evidence_refs,
                depends_on=depends_on,
                conclusion=chain.conclusion.label if chain.conclusion else "",
                status=status,
                confidence=chain.claim.confidence * 0.9,
                source_chapters=source_chapters,
            ))
        return out

    def _build_sub_arguments(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        argument_analysis: ArgumentAnalysis | None,
        graph: BookReasoningGraph | None,
    ) -> list[BookArgument]:
        out = []
        if not argument_analysis or not argument_analysis.chains:
            return out

        for i, chain in enumerate(argument_analysis.chains[8:15]):
            if not chain.claim:
                continue
            evidence_refs = []
            for ev in chain.evidence:
                evidence_refs.extend(ev.evidence_refs)
            source_chapters = [chain.chapter_id] if chain.chapter_id else []
            depends_on = []
            if out:
                depends_on = [out[-1].id]
            status = self._determine_status(chain, evidence_refs)

            out.append(BookArgument(
                id=_stable_id("arg", "sub", bu.book_id, str(i)),
                level=2,
                what=chain.claim.label,
                why=self._build_why(chain),
                how=self._build_how(chain),
                evidence_refs=evidence_refs,
                depends_on=depends_on,
                conclusion=chain.conclusion.label if chain.conclusion else "",
                status=status,
                confidence=chain.claim.confidence * 0.8,
                source_chapters=source_chapters,
            ))
        return out

    def _build_why(self, chain: Any) -> str:
        reasons = []
        for ev in chain.evidence:
            reasons.append(f"Evidence: {ev.label}")
        for rs in chain.reasoning:
            reasons.append(f"Reasoning: {rs.label}")
        return "; ".join(reasons) if reasons else "No explicit justification recorded"

    def _build_how(self, chain: Any) -> str:
        steps = []
        for rs in chain.reasoning:
            steps.append(rs.label)
        if chain.conclusion:
            steps.append(f"Concludes: {chain.conclusion.label}")
        return " -> ".join(steps) if steps else "No explicit derivation recorded"

    def _determine_status(self, chain: Any, evidence_refs: list[str]) -> ArgumentStatus:
        if not chain.complete:
            return ArgumentStatus.UNRESOLVED
        if not evidence_refs:
            return ArgumentStatus.MODEL_INFERRED
        if chain.evidence_strength == "DIRECT":
            return ArgumentStatus.SUPPORTED
        if chain.evidence_strength in ("DEFINITION", "EXAMPLE", "DERIVED"):
            return ArgumentStatus.PARTIALLY_SUPPORTED
        return ArgumentStatus.MODEL_INFERRED