"""P13: Mechanism Analysis.

Extracts causal/explanatory mechanisms from the book with full traceability.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookMechanism,
    BookMechanismSystem,
    BookUnderstandingV2,
    ChapterUnderstanding,
    ThesisProvenance,
)
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class MechanismAnalysis:
    system: BookMechanismSystem
    traceability: dict[str, list[str]]


_MECH_CUES = re.compile(
    r"(because|therefore|thus|hence|consequently|leads to|causes|results in|"
    r"produces|generates|brings about|gives rise to|derives from|follows from|"
    r"mechanism|process|procedure|method|operation|step by step|works by|"
    r"the way|how it works|the process|the mechanism|through|via|by means of)",
    re.I,
)

_STEP_CUES = re.compile(
    r"(first|then|next|finally|step \d|stage \d|phase \d|initially|subsequently|"
    r"afterwards|followed by|preceded by|in turn|which in turn)",
    re.I,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class MechanismAnalyzer:
    """Extract mechanisms from chapter understandings and reasoning graph."""

    def analyze(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None = None,
    ) -> MechanismAnalysis:
        system = BookMechanismSystem()
        traceability: dict[str, list[str]] = {}

        for cu in chapters:
            for mech_ref in cu.mechanisms_refs:
                mechanism = self._extract_mechanism_from_text(
                    mech_ref, cu, chapters, graph
                )
                if mechanism:
                    system.mechanisms.append(mechanism)
                    traceability[mechanism.id] = mechanism.source_chapters

        graph_mechanisms = self._extract_from_graph(bu, graph)
        for mech in graph_mechanisms:
            system.mechanisms.append(mech)
            traceability[mech.id] = mech.source_chapters

        return MechanismAnalysis(system=system, traceability=traceability)

    def _extract_mechanism_from_text(
        self,
        mech_text: str,
        cu: ChapterUnderstanding,
        all_chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> BookMechanism | None:
        if len(mech_text.strip()) < 10:
            return None

        trigger = self._find_trigger(mech_text, cu)
        precondition = self._find_precondition(mech_text, cu)
        operation = mech_text[:500]
        intermediate = self._find_intermediate(mech_text)
        outcome = self._find_outcome(mech_text, cu)
        evidence_refs = self._find_evidence_for_mechanism(mech_text, cu, all_chapters)
        provenance = self._determine_provenance(mech_text, cu, evidence_refs)

        return BookMechanism(
            id=_stable_id("mech", cu.chapter_id, mech_text[:50]),
            trigger=trigger,
            precondition=precondition,
            operation=operation,
            intermediate_state=intermediate,
            outcome=outcome,
            evidence_refs=evidence_refs,
            confidence=0.6 if evidence_refs else 0.3,
            provenance=provenance,
            source_chapters=[cu.chapter_id],
        )

    def _extract_from_graph(
        self, bu: BookUnderstandingV2, graph: BookReasoningGraph | None
    ) -> list[BookMechanism]:
        if not graph:
            return []

        mechanisms = []
        for node in graph.nodes.values():
            if node.node_type == "MECHANISM":
                evidence_refs = node.metadata.get("evidence_refs", [])
                source_chapters = [node.chapter_id] if node.chapter_id else []

                trigger = node.metadata.get("trigger", "")
                precondition = node.metadata.get("precondition", "")
                operation = node.label
                intermediate = node.metadata.get("intermediate", "")
                outcome = node.metadata.get("outcome", "")

                provenance = ThesisProvenance.AUTHOR_ASSERTED if evidence_refs else ThesisProvenance.MODEL_INFERRED

                mechanisms.append(BookMechanism(
                    id=_stable_id("mech", "graph", node.node_id),
                    trigger=trigger,
                    precondition=precondition,
                    operation=operation,
                    intermediate_state=intermediate,
                    outcome=outcome,
                    evidence_refs=evidence_refs,
                    confidence=node.confidence,
                    provenance=provenance,
                    source_chapters=source_chapters,
                ))
        return mechanisms

    def _find_trigger(self, text: str, cu: ChapterUnderstanding) -> str:
        sentences = re.split(r"[.!?]+", text)
        for s in sentences:
            if _MECH_CUES.search(s) or _STEP_CUES.search(s):
                return s.strip()[:200]
        return text[:200]

    def _find_precondition(self, text: str, cu: ChapterUnderstanding) -> str:
        for dep in cu.dependencies_on_prior:
            return f"Requires: {dep}"
        for asm in cu.assumptions:
            return f"Assumes: {asm}"
        return ""

    def _find_intermediate(self, text: str) -> str:
        matches = _STEP_CUES.findall(text)
        if matches:
            return "; ".join(matches[:5])
        return ""

    def _find_outcome(self, text: str, cu: ChapterUnderstanding) -> str:
        sentences = re.split(r"[.!?]+", text)
        for s in reversed(sentences):
            if any(w in s.lower() for w in ["result", "conclude", "therefore", "thus", "hence", "gives", "yields", "produces"]):
                return s.strip()[:200]
        if cu.qualifications:
            return cu.qualifications[0][:200]
        return ""

    def _find_evidence_for_mechanism(
        self, mech_text: str, cu: ChapterUnderstanding, all_chapters: list[ChapterUnderstanding]
    ) -> list[str]:
        evidence = []
        mech_lower = mech_text.lower()[:100]
        for ep in cu.evidence_program:
            if mech_lower in ep.claim_ref.lower():
                evidence.extend(ep.evidence_refs)
        return list(dict.fromkeys(evidence))[:10]

    def _determine_provenance(
        self, text: str, cu: ChapterUnderstanding, evidence_refs: list[str]
    ) -> ThesisProvenance:
        if evidence_refs:
            return ThesisProvenance.AUTHOR_ASSERTED
        for ep in cu.evidence_program:
            if text.lower()[:50] in ep.claim_ref.lower():
                return ThesisProvenance.STRUCTURALLY_DERIVED
        return ThesisProvenance.MODEL_INFERRED