"""P13: Evidence Map.

Builds the complete claim-evidence-argument-chapter map with coverage metrics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookEvidenceMap,
    BookUnderstandingV2,
    ChapterUnderstanding,
    EvidenceMapEntry,
    EvidenceStrengthP13,
    ThesisProvenance,
)
from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class EvidenceMapAnalysis:
    evidence_map: BookEvidenceMap
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class EvidenceMapBuilder:
    """Build BookEvidenceMap from all P12 artefacts."""

    def build(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        argument_analysis: ArgumentAnalysis | None = None,
        graph: BookReasoningGraph | None = None,
    ) -> EvidenceMapAnalysis:
        em = BookEvidenceMap()
        traceability: dict[str, list[str]] = {}

        entries = self._build_entries(bu, chapters, argument_analysis, graph)
        em.entries = entries
        for e in entries:
            traceability[e.claim_id] = e.chapter_ids

        self._compute_coverage_metrics(em)

        return EvidenceMapAnalysis(evidence_map=em, traceability=traceability)

    def _build_entries(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        argument_analysis: ArgumentAnalysis | None,
        graph: BookReasoningGraph | None,
    ) -> list[EvidenceMapEntry]:
        entries = []
        claim_to_entry: dict[str, EvidenceMapEntry] = {}

        for cu in chapters:
            for ep in cu.evidence_program:
                claim_key = ep.claim_ref
                if claim_key not in claim_to_entry:
                    strengths = {}
                    for er in ep.evidence_refs:
                        strengths[er] = self._infer_strength(er, cu, ep)
                    entry = EvidenceMapEntry(
                        claim_id=_stable_id("claim", claim_key, bu.book_id),
                        claim_statement=claim_key,
                        evidence_ids=list(ep.evidence_refs),
                        evidence_strengths=strengths,
                        argument_ids=[],
                        chapter_ids=[cu.chapter_id],
                        is_supported=ep.is_supported,
                        provenance=self._determine_provenance(ep, cu),
                    )
                    claim_to_entry[claim_key] = entry
                else:
                    entry = claim_to_entry[claim_key]
                    entry.evidence_ids.extend(ep.evidence_refs)
                    for er in ep.evidence_refs:
                        if er not in entry.evidence_strengths:
                            entry.evidence_strengths[er] = self._infer_strength(er, cu, ep)
                    if cu.chapter_id not in entry.chapter_ids:
                        entry.chapter_ids.append(cu.chapter_id)
                    if ep.is_supported:
                        entry.is_supported = True

        if argument_analysis:
            for chain in argument_analysis.chains:
                claim_key = chain.claim.label
                if claim_key in claim_to_entry:
                    entry = claim_to_entry[claim_key]
                    if chain.chain_id not in entry.argument_ids:
                        entry.argument_ids.append(chain.chain_id)
                else:
                    strengths = {}
                    for ev in chain.evidence:
                        for er in ev.evidence_refs:
                            strengths[er] = EvidenceStrengthP13.MODEL_INFERENCE
                    entry = EvidenceMapEntry(
                        claim_id=_stable_id("claim", claim_key, bu.book_id),
                        claim_statement=claim_key,
                        evidence_ids=[er for ev in chain.evidence for er in ev.evidence_refs],
                        evidence_strengths=strengths,
                        argument_ids=[chain.chain_id],
                        chapter_ids=[chain.chapter_id] if chain.chapter_id else [],
                        is_supported=bool(chain.evidence),
                        provenance=ThesisProvenance.MODEL_INFERRED,
                    )
                    claim_to_entry[claim_key] = entry

        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CLAIM":
                    claim_key = node.label
                    if claim_key in claim_to_entry:
                        entry = claim_to_entry[claim_key]
                        for edge in graph.out_edges(node.node_id):
                            if edge.evidence_refs:
                                for er in edge.evidence_refs:
                                    if er not in entry.evidence_ids:
                                        entry.evidence_ids.append(er)
                                    if er not in entry.evidence_strengths:
                                        entry.evidence_strengths[er] = self._edge_to_strength(
                                            edge.evidence_type
                                        )
                            if edge.edge_id not in entry.argument_ids:
                                entry.argument_ids.append(edge.edge_id)
                    else:
                        evidence_refs = []
                        strengths = {}
                        argument_ids = []
                        for edge in graph.out_edges(node.node_id):
                            evidence_refs.extend(edge.evidence_refs)
                            for er in edge.evidence_refs:
                                strengths[er] = self._edge_to_strength(edge.evidence_type)
                            argument_ids.append(edge.edge_id)
                        entry = EvidenceMapEntry(
                            claim_id=_stable_id("claim", claim_key, bu.book_id),
                            claim_statement=claim_key,
                            evidence_ids=evidence_refs,
                            evidence_strengths=strengths,
                            argument_ids=argument_ids,
                            chapter_ids=[node.chapter_id] if node.chapter_id else [],
                            is_supported=len(evidence_refs) > 0,
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        claim_to_entry[claim_key] = entry

        return list(claim_to_entry.values())

    def _infer_strength(
        self, evidence_ref: str, cu: ChapterUnderstanding, ep: Any
    ) -> EvidenceStrengthP13:
        for e in cu.evidence_program:
            if evidence_ref in e.evidence_refs:
                if hasattr(cu, "evidence_strengths") and evidence_ref in cu.evidence_strengths:
                    try:
                        return EvidenceStrengthP13(cu.evidence_strengths[evidence_ref])
                    except ValueError:
                        pass
        if ep.is_supported:
            return EvidenceStrengthP13.DIRECT
        return EvidenceStrengthP13.MODEL_INFERENCE

    def _edge_to_strength(self, edge_type: str) -> EvidenceStrengthP13:
        mapping = {
            "DIRECT": EvidenceStrengthP13.DIRECT,
            "DEFINITION": EvidenceStrengthP13.DEFINITION,
            "EXAMPLE": EvidenceStrengthP13.EXAMPLE,
            "DERIVED": EvidenceStrengthP13.DERIVED,
            "MODEL_INFERENCE": EvidenceStrengthP13.MODEL_INFERENCE,
        }
        return mapping.get(edge_type, EvidenceStrengthP13.MODEL_INFERENCE)

    def _determine_provenance(self, ep: Any, cu: ChapterUnderstanding) -> ThesisProvenance:
        if ep.is_supported and ep.evidence_refs:
            return ThesisProvenance.AUTHOR_ASSERTED
        if cu.chapter_thesis and ep.claim_ref in cu.chapter_thesis:
            return ThesisProvenance.STRUCTURALLY_DERIVED
        return ThesisProvenance.MODEL_INFERRED

    def _compute_coverage_metrics(self, em: BookEvidenceMap) -> None:
        total_claims = len(em.entries)
        if total_claims == 0:
            em.evidence_coverage = 0.0
            em.unsupported_claim_count = 0
            em.model_inference_ratio = 0.0
            em.contradiction_count = 0
            return

        supported = sum(1 for e in em.entries if e.is_supported)
        em.evidence_coverage = round(supported / total_claims, 4)
        em.unsupported_claim_count = total_claims - supported

        model_inferred = sum(
            1
            for e in em.entries
            for s in e.evidence_strengths.values()
            if s == EvidenceStrengthP13.MODEL_INFERENCE
        )
        total_evidence = sum(len(e.evidence_strengths) for e in em.entries)
        em.model_inference_ratio = (
            round(model_inferred / total_evidence, 4) if total_evidence else 0.0
        )
        em.contradiction_count = 0
