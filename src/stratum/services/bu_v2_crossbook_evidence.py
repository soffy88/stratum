"""P14: Cross-Book Evidence Comparison.

Compares evidence across independently understood books with full traceability.
Maintains evidence independence - never pretends Book B confirms Book A.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    CrossBookEvidence,
    CrossBookEvidenceRelation,
    CrossBookEvidenceRelationType,
    EvidenceStrengthP13,
    ThesisProvenance,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _normalize_text(text: str) -> str:
    import re

    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = set(_normalize_text(a).split())
    set_b = set(_normalize_text(b).split())
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


@dataclass
class EvidenceComparisonResult:
    """Result of evidence comparison across books."""

    crossbook_evidence: list[CrossBookEvidence]
    evidence_relations: list[CrossBookEvidenceRelation]
    traceability: dict[str, list[str]]


class BU2CrossBookEvidenceComparator:
    """Compares evidence across independently understood books.

    Core principle: evidence independence. Book A's evidence never
    confirms Book B's claim without Book B's own evidence.
    """

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_evidence(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all evidence from all books."""
        all_evidence: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.evidence_map:
                continue

            book_evidence = []
            for entry in synth.evidence_map.entries:
                book_evidence.append(
                    {
                        "evidence_id": entry.claim_id,  # Using claim_id as proxy
                        "claim_id": entry.claim_id,
                        "claim_statement": entry.claim_statement,
                        "evidence_ids": entry.evidence_ids,
                        "evidence_strengths": entry.evidence_strengths,
                        "argument_ids": entry.argument_ids,
                        "chapter_ids": entry.chapter_ids,
                        "is_supported": entry.is_supported,
                        "provenance": entry.provenance,
                    }
                )
            all_evidence[bu.book_id] = book_evidence

        return all_evidence

    def _compute_evidence_similarity(self, e1: dict, e2: dict) -> dict[str, float]:
        """Compute similarity metrics between two evidence entries."""
        return {
            "claim": _jaccard_similarity(
                e1.get("claim_statement", ""), e2.get("claim_statement", "")
            ),
            "evidence_overlap": _jaccard_similarity(
                " ".join(e1.get("evidence_ids", [])), " ".join(e2.get("evidence_ids", []))
            ),
            "argument_overlap": _jaccard_similarity(
                " ".join(e1.get("argument_ids", [])), " ".join(e2.get("argument_ids", []))
            ),
            "chapter_overlap": _jaccard_similarity(
                " ".join(e1.get("chapter_ids", [])), " ".join(e2.get("chapter_ids", []))
            ),
            "support_match": 1.0 if e1.get("is_supported") == e2.get("is_supported") else 0.0,
        }

    def _determine_evidence_relation(
        self,
        e1: dict,
        e2: dict,
        similarity: dict[str, float],
    ) -> CrossBookEvidenceRelationType:
        """Determine the relation type between two evidence entries."""

        claim_sim = similarity["claim"]
        evidence_overlap = similarity["evidence_overlap"]
        support_match = similarity["support_match"]

        # Same claim, both supported, independent evidence -> convergent
        if claim_sim > 0.7 and support_match and evidence_overlap < 0.3:
            return CrossBookEvidenceRelationType.CONVERGENT

        # Same claim, conflicting support -> conflicting
        if claim_sim > 0.7 and not support_match:
            return CrossBookEvidenceRelationType.CONFLICTING

        # Same claim, shared evidence -> convergent (but note shared source)
        if claim_sim > 0.7 and evidence_overlap > 0.5:
            return CrossBookEvidenceRelationType.CONVERGENT

        # Related claims, both supported -> independent
        if claim_sim > 0.4 and claim_sim < 0.7 and support_match:
            return CrossBookEvidenceRelationType.INDEPENDENT

        # Divergent: different support for related claims
        if claim_sim > 0.3 and not support_match:
            return CrossBookEvidenceRelationType.DIVERGENT

        # Some similarity -> independent
        avg_sim = sum(similarity.values()) / len(similarity)
        if avg_sim > 0.4:
            return CrossBookEvidenceRelationType.INDEPENDENT

        return CrossBookEvidenceRelationType.INSUFFICIENT

    def _build_crossbook_evidence(
        self,
        all_evidence: dict[str, list[dict]],
    ) -> list[CrossBookEvidence]:
        """Build CrossBookEvidence objects."""
        crossbook_evidence = []

        for book_id, entries in all_evidence.items():
            for entry in entries:
                # Use first evidence_id as primary
                primary_ev_id = (
                    entry.get("evidence_ids", [""])[0] if entry.get("evidence_ids") else ""
                )

                cb = CrossBookEvidence(
                    evidence_id=_stable_id("cbe", book_id, entry["claim_id"]),
                    book_id=book_id,
                    evidence_ref=primary_ev_id,
                    claim_id=entry["claim_id"],
                    locator=f"chapters:{','.join(entry.get('chapter_ids', [])[:3])}",
                    strength=EvidenceStrengthP13.MODEL_INFERENCE,  # Default
                )
                crossbook_evidence.append(cb)

        return crossbook_evidence

    def _align_evidence_pairs(
        self,
        book_ids: list[str],
        all_evidence: dict[str, list[dict]],
    ) -> list[CrossBookEvidenceRelation]:
        """Align all pairs of evidence between books."""
        relations = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                evidence_a = all_evidence.get(book_a_id, [])
                evidence_b = all_evidence.get(book_b_id, [])

                for e1 in evidence_a:
                    for e2 in evidence_b:
                        similarity = self._compute_evidence_similarity(e1, e2)
                        relation_type = self._determine_evidence_relation(e1, e2, similarity)

                        if relation_type == CrossBookEvidenceRelationType.INSUFFICIENT:
                            continue

                        evidence = [
                            f"claim_similarity={similarity['claim']:.2f}",
                            f"evidence_overlap={similarity['evidence_overlap']:.2f}",
                            f"support_match={similarity['support_match']}",
                            f"argument_overlap={similarity['argument_overlap']:.2f}",
                        ]

                        avg_sim = sum(similarity.values()) / len(similarity)
                        confidence = round(avg_sim, 3)

                        relation = CrossBookEvidenceRelation(
                            relation_id=_stable_id(
                                "ebr", book_a_id, e1["claim_id"], book_b_id, e2["claim_id"]
                            ),
                            source_evidence=CrossBookEvidence(
                                evidence_id=_stable_id("cbe", book_a_id, e1["claim_id"]),
                                book_id=book_a_id,
                                evidence_ref=(e1.get("evidence_ids") or [""])[0],
                                claim_id=e1["claim_id"],
                                locator=f"chapters:{','.join(e1.get('chapter_ids', [])[:3])}",
                                strength=EvidenceStrengthP13.MODEL_INFERENCE,
                            ),
                            target_evidence=CrossBookEvidence(
                                evidence_id=_stable_id("cbe", book_b_id, e2["claim_id"]),
                                book_id=book_b_id,
                                evidence_ref=(e2.get("evidence_ids") or [""])[0],
                                claim_id=e2["claim_id"],
                                locator=f"chapters:{','.join(e2.get('chapter_ids', [])[:3])}",
                                strength=EvidenceStrengthP13.MODEL_INFERENCE,
                            ),
                            relation=relation_type,
                            reason=f"Claim:{e1['claim_statement'][:40]}... {relation_type.value} Claim:{e2['claim_statement'][:40]}...",
                            evidence=evidence,
                            confidence=confidence,
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        relations.append(relation)

        return relations

    def compare(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> EvidenceComparisonResult:
        """Compare evidence across all books."""
        if len(books) < 2:
            return EvidenceComparisonResult(
                crossbook_evidence=[],
                evidence_relations=[],
                traceability={},
            )

        all_evidence = self._extract_evidence(books)
        book_ids = list(all_evidence.keys())

        crossbook_evidence = self._build_crossbook_evidence(all_evidence)
        relations = self._align_evidence_pairs(book_ids, all_evidence)

        # Build traceability
        traceability = {}
        for ce in crossbook_evidence:
            traceability[ce.evidence_id] = [ce.book_id]
        for rel in relations:
            traceability[rel.relation_id] = [
                rel.source_evidence.book_id,
                rel.target_evidence.book_id,
            ]

        return EvidenceComparisonResult(
            crossbook_evidence=crossbook_evidence,
            evidence_relations=relations,
            traceability=traceability,
        )
