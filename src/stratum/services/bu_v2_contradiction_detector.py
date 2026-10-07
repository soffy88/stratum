"""P13: Contradiction Detection.

Detects contradictions and tensions in the book's claims, concepts, and arguments.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookContradictions,
    BookUnderstandingV2,
    ChapterUnderstanding,
    ContradictionEntry,
    ContradictionType,
)
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class ContradictionAnalysis:
    contradictions: BookContradictions
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class ContradictionDetector:
    """Detect contradictions in the book's understanding."""

    def detect(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        thesis_model: Any = None,
        concept_system: Any = None,
        argument_system: Any = None,
        graph: BookReasoningGraph | None = None,
    ) -> ContradictionAnalysis:
        contra = BookContradictions()
        traceability: dict[str, list[str]] = {}

        claim_contra = self._detect_claim_contradictions(bu, chapters, graph)
        for c in claim_contra:
            contra.contradictions.append(c)
            traceability[c.id] = c.source_chapters

        concept_contra = self._detect_concept_contradictions(bu, chapters, concept_system)
        for c in concept_contra:
            contra.contradictions.append(c)
            traceability[c.id] = c.source_chapters

        argument_contra = self._detect_argument_contradictions(bu, chapters, argument_system, graph)
        for c in argument_contra:
            contra.contradictions.append(c)
            traceability[c.id] = c.source_chapters

        return ContradictionAnalysis(contradictions=contra, traceability=traceability)

    def _detect_claim_contradictions(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> list[ContradictionEntry]:
        contradictions = []
        claim_map: dict[str, list[tuple[str, str]]] = {}

        for cu in chapters:
            for ep in cu.evidence_program:
                claim = ep.claim_ref.strip()
                if not claim or len(claim) < 10:
                    continue
                claim_lower = claim.lower()[:80]
                if claim_lower not in claim_map:
                    claim_map[claim_lower] = []
                claim_map[claim_lower].append((cu.chapter_id, claim))

        for claim_lower, instances in claim_map.items():
            if len(instances) < 2:
                continue
            for i, (ch1, c1) in enumerate(instances):
                for ch2, c2 in instances[i+1:]:
                    if self._are_contradictory(c1, c2):
                        contra = ContradictionEntry(
                            id=_stable_id("contra", "claim", bu.book_id, ch1, ch2),
                            type=ContradictionType.DIRECT_CONTRADICTION,
                            element_a=c1[:200],
                            element_b=c2[:200],
                            element_type="claim",
                            description=f"Claim '{c1[:80]}...' in {ch1} vs '{c2[:80]}...' in {ch2}",
                            classification=ContradictionType.DIRECT_CONTRADICTION,
                            source_chapters=[ch1, ch2],
                            confidence=0.6,
                        )
                        contradictions.append(contra)

        return contradictions

    def _detect_concept_contradictions(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        concept_system: Any,
    ) -> list[ContradictionEntry]:
        contradictions = []
        concept_defs: dict[str, list[tuple[str, str]]] = {}

        for cu in chapters:
            for cid in cu.concepts_introduced_refs:
                if cid not in concept_defs:
                    concept_defs[cid] = []
                concept_defs[cid].append((cu.chapter_id, cu.chapter_thesis or ""))

        for cid, instances in concept_defs.items():
            if len(instances) < 2:
                continue
            for i, (ch1, def1) in enumerate(instances):
                for ch2, def2 in instances[i+1:]:
                    if def1 and def2 and self._definitions_conflict(def1, def2):
                        contra = ContradictionEntry(
                            id=_stable_id("contra", "concept", bu.book_id, cid, ch1, ch2),
                            type=ContradictionType.CONTEXTUAL_DIFFERENCE,
                            element_a=f"{cid}: {def1[:150]}",
                            element_b=f"{cid}: {def2[:150]}",
                            element_type="concept",
                            description=f"Concept '{cid}' defined differently in {ch1} vs {ch2}",
                            classification=ContradictionType.CONTEXTUAL_DIFFERENCE,
                            source_chapters=[ch1, ch2],
                            confidence=0.5,
                        )
                        contradictions.append(contra)

        return contradictions

    def _detect_argument_contradictions(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        argument_system: Any,
        graph: BookReasoningGraph | None,
    ) -> list[ContradictionEntry]:
        contradictions = []

        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CLAIM":
                    for edge in graph.out_edges(node.node_id):
                        if edge.relation_type == "CONTRADICTS":
                            tgt = graph.nodes.get(edge.target_node_id)
                            if tgt:
                                contra = ContradictionEntry(
                                    id=_stable_id("contra", "arg", edge.edge_id),
                                    type=ContradictionType.DIRECT_CONTRADICTION,
                                    element_a=node.label[:200],
                                    element_b=tgt.label[:200],
                                    element_type="argument",
                                    description=f"Argument contradiction: {edge.reason}",
                                    classification=ContradictionType.DIRECT_CONTRADICTION,
                                    source_chapters=[node.chapter_id, tgt.chapter_id],
                                    confidence=edge.confidence,
                                )
                                contradictions.append(contra)

        return contradictions

    def _are_contradictory(self, claim1: str, claim2: str) -> bool:
        c1 = claim1.lower()
        c2 = claim2.lower()

        negations = ["not", "never", "cannot", "impossible", "false", "incorrect", "wrong", "denies", "rejects"]
        has_neg1 = any(n in c1 for n in negations)
        has_neg2 = any(n in c2 for n in negations)

        if has_neg1 != has_neg2:
            common_words = set(c1.split()) & set(c2.split())
            if len(common_words) >= 3:
                return True

        return False

    def _definitions_conflict(self, def1: str, def2: str) -> bool:
        d1 = def1.lower()
        d2 = def2.lower()

        if " is " in d1 and " is " in d2:
            parts1 = d1.split(" is ")
            parts2 = d2.split(" is ")
            if len(parts1) > 1 and len(parts2) > 1:
                if parts1[0].strip() == parts2[0].strip():
                    rest1 = parts1[1].strip()
                    rest2 = parts2[1].strip()
                    neg1 = any(n in rest1 for n in ["not", "never", "no ", "non-"])
                    neg2 = any(n in rest2 for n in ["not", "never", "no ", "non-"])
                    if neg1 != neg2:
                        return True

        return False