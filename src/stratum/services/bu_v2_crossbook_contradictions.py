"""P14: Cross-Book Contradiction Detection.

Detects contradictions across independently understood books with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookContradictions,
    BookSynthesis,
    CrossBookContradiction,
    CrossBookContradictionType,
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
class ContradictionDetectionResult:
    """Result of contradiction detection across books."""

    contradictions: list[CrossBookContradiction]
    traceability: dict[str, list[str]]


class BU2CrossBookContradictionDetector:
    """Detects contradictions across independently understood books.

    Does not resolve contradictions - only detects, locates, classifies, and preserves.
    """

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_claims(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all claims from all books."""
        all_claims: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.evidence_map:
                continue

            claims = []
            for entry in synth.evidence_map.entries:
                claims.append({
                    "claim_id": entry.claim_id,
                    "statement": entry.claim_statement,
                    "evidence_ids": entry.evidence_ids,
                    "is_supported": entry.is_supported,
                    "provenance": entry.provenance,
                    "chapter_ids": entry.chapter_ids,
                    "argument_ids": entry.argument_ids,
                })
            all_claims[bu.book_id] = claims

        return all_claims

    def _extract_concepts(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all concepts from all books."""
        all_concepts: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.concept_system:
                continue

            concepts = []
            for role_attr in ["foundational", "core", "derived", "bridging", "application", "terminal"]:
                for c in getattr(synth.concept_system, role_attr, []):
                    concepts.append({
                        "concept_id": c.concept_id,
                        "label": c.label,
                        "definition": c.definition,
                        "role": c.final_role,
                        "chapter_refs": c.chapter_refs,
                    })
            all_concepts[bu.book_id] = concepts

        return all_concepts

    def _extract_arguments(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all arguments from all books."""
        all_args: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.argument_system:
                continue

            args = []
            for arg in synth.argument_system.all_arguments():
                args.append({
                    "argument_id": arg.id,
                    "level": arg.level,
                    "what": arg.what,
                    "why": arg.why,
                    "conclusion": arg.conclusion,
                    "status": arg.status,
                })
            all_args[bu.book_id] = args

        return all_args

    def _extract_theses(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all theses from all books."""
        all_theses: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.thesis:
                continue

            theses = []
            for t in synth.thesis.all_theses():
                theses.append({
                    "thesis_id": t.id,
                    "type": t.type,
                    "statement": t.statement,
                    "confidence": t.confidence,
                    "provenance": t.provenance,
                })
            all_theses[bu.book_id] = theses

        return all_theses

    def _detect_claim_contradictions(
        self,
        all_claims: dict[str, list[dict]],
    ) -> list[CrossBookContradiction]:
        """Detect contradictions between claims across books."""
        contradictions = []
        book_ids = list(all_claims.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                claims_a = all_claims.get(book_a_id, [])
                claims_b = all_claims.get(book_b_id, [])

                for c1 in claims_a:
                    for c2 in claims_b:
                        sim = _jaccard_similarity(c1["statement"], c2["statement"])

                        # High similarity, opposing support status -> contradiction
                        if sim > 0.6 and c1["is_supported"] != c2["is_supported"]:
                            contra = CrossBookContradiction(
                                contradiction_id=_stable_id("cc", book_a_id, c1["claim_id"], book_b_id, c2["claim_id"]),
                                type=CrossBookContradictionType.DIRECT_CONTRADICTION,
                                book_a_id=book_a_id,
                                element_a=c1["claim_id"],
                                book_b_id=book_b_id,
                                element_b=c2["claim_id"],
                                element_type="claim",
                                description=f"Claim '{c1['statement'][:80]}...' supported in {book_a_id} but not in {book_b_id}",
                                classification=CrossBookContradictionType.DIRECT_CONTRADICTION,
                                confidence=round(sim, 3),
                                provenance=ThesisProvenance.MODEL_INFERRED,
                            )
                            contradictions.append(contra)

                        # High similarity, both supported but different evidence -> potential conflict
                        elif sim > 0.7 and c1["is_supported"] and c2["is_supported"]:
                            # Check if evidence is completely disjoint
                            ev_a = set(c1.get("evidence_ids", []))
                            ev_b = set(c2.get("evidence_ids", []))
                            if not (ev_a & ev_b):
                                contra = CrossBookContradiction(
                                    contradiction_id=_stable_id("cc", book_a_id, c1["claim_id"], book_b_id, c2["claim_id"]),
                                    type=CrossBookContradictionType.EMPIRICAL_CONFLICT,
                                    book_a_id=book_a_id,
                                    element_a=c1["claim_id"],
                                    book_b_id=book_b_id,
                                    element_b=c2["claim_id"],
                                    element_type="claim",
                                    description=f"Same claim '{c1['statement'][:80]}...' supported by disjoint evidence in {book_a_id} vs {book_b_id}",
                                    classification=CrossBookContradictionType.EMPIRICAL_CONFLICT,
                                    confidence=round(sim, 3),
                                    provenance=ThesisProvenance.MODEL_INFERRED,
                                )
                                contradictions.append(contra)

        return contradictions

    def _detect_concept_contradictions(
        self,
        all_concepts: dict[str, list[dict]],
    ) -> list[CrossBookContradiction]:
        """Detect contradictions between concepts across books."""
        contradictions = []
        book_ids = list(all_concepts.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                concepts_a = all_concepts.get(book_a_id, [])
                concepts_b = all_concepts.get(book_b_id, [])

                for c1 in concepts_a:
                    for c2 in concepts_b:
                        sim = _jaccard_similarity(c1["label"], c2["label"])
                        def_sim = _jaccard_similarity(c1["definition"], c2["definition"])

                        # Same term, different definition -> definitional conflict
                        if sim > 0.8 and def_sim < 0.4:
                            contra = CrossBookContradiction(
                                contradiction_id=_stable_id("cc", book_a_id, c1["concept_id"], book_b_id, c2["concept_id"]),
                                type=CrossBookContradictionType.DEFINITIONAL_CONFLICT,
                                book_a_id=book_a_id,
                                element_a=c1["concept_id"],
                                book_b_id=book_b_id,
                                element_b=c2["concept_id"],
                                element_type="concept",
                                description=f"Term '{c1['label']}' has different definitions: '{c1['definition'][:60]}...' vs '{c2['definition'][:60]}...'",
                                classification=CrossBookContradictionType.DEFINITIONAL_CONFLICT,
                                confidence=round(sim, 3),
                                provenance=ThesisProvenance.MODEL_INFERRED,
                            )
                            contradictions.append(contra)

        return contradictions

    def _detect_argument_contradictions(
        self,
        all_args: dict[str, list[dict]],
    ) -> list[CrossBookContradiction]:
        """Detect contradictions between arguments across books."""
        contradictions = []
        book_ids = list(all_args.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                args_a = all_args.get(book_a_id, [])
                args_b = all_args.get(book_b_id, [])

                for a1 in args_a:
                    for a2 in args_b:
                        sim = _jaccard_similarity(a1["what"], a2["what"])
                        conclusion_sim = _jaccard_similarity(a1["conclusion"], a2["conclusion"])

                        # Similar argument, contradictory conclusions
                        if sim > 0.5 and conclusion_sim < 0.3:
                            contra = CrossBookContradiction(
                                contradiction_id=_stable_id("cc", book_a_id, a1["argument_id"], book_b_id, a2["argument_id"]),
                                type=CrossBookContradictionType.THEORETICAL_CONFLICT,
                                book_a_id=book_a_id,
                                element_a=a1["argument_id"],
                                book_b_id=book_b_id,
                                element_b=a2["argument_id"],
                                element_type="argument",
                                description=f"Similar argument '{a1['what'][:60]}...' reaches different conclusions in {book_a_id} vs {book_b_id}",
                                classification=CrossBookContradictionType.THEORETICAL_CONFLICT,
                                confidence=round(sim, 3),
                                provenance=ThesisProvenance.MODEL_INFERRED,
                            )
                            contradictions.append(contra)

        return contradictions

    def _detect_thesis_contradictions(
        self,
        all_theses: dict[str, list[dict]],
    ) -> list[CrossBookContradiction]:
        """Detect contradictions between theses across books."""
        contradictions = []
        book_ids = list(all_theses.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                theses_a = all_theses.get(book_a_id, [])
                theses_b = all_theses.get(book_b_id, [])

                for t1 in theses_a:
                    for t2 in theses_b:
                        sim = _jaccard_similarity(t1["statement"], t2["statement"])

                        # Core theses contradicting
                        if sim > 0.5 and t1["type"] == "CORE" and t2["type"] == "CORE":
                            contra = CrossBookContradiction(
                                contradiction_id=_stable_id("cc", book_a_id, t1["thesis_id"], book_b_id, t2["thesis_id"]),
                                type=CrossBookContradictionType.THEORETICAL_CONFLICT,
                                book_a_id=book_a_id,
                                element_a=t1["thesis_id"],
                                book_b_id=book_b_id,
                                element_b=t2["thesis_id"],
                                element_type="thesis",
                                description=f"Core theses conflict: '{t1['statement'][:80]}...' vs '{t2['statement'][:80]}...'",
                                classification=CrossBookContradictionType.THEORETICAL_CONFLICT,
                                confidence=round(sim, 3),
                                provenance=ThesisProvenance.MODEL_INFERRED,
                            )
                            contradictions.append(contra)

        return contradictions

    def detect(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> ContradictionDetectionResult:
        """Detect contradictions across all books."""
        if len(books) < 2:
            return ContradictionDetectionResult(
                contradictions=[],
                traceability={},
            )

        all_claims = self._extract_claims(books)
        all_concepts = self._extract_concepts(books)
        all_args = self._extract_arguments(books)
        all_theses = self._extract_theses(books)

        contradictions = []
        contradictions.extend(self._detect_claim_contradictions(all_claims))
        contradictions.extend(self._detect_concept_contradictions(all_concepts))
        contradictions.extend(self._detect_argument_contradictions(all_args))
        contradictions.extend(self._detect_thesis_contradictions(all_theses))

        # Build traceability
        traceability = {}
        for c in contradictions:
            traceability[c.contradiction_id] = [c.book_a_id, c.book_b_id]

        return ContradictionDetectionResult(
            contradictions=contradictions,
            traceability=traceability,
        )