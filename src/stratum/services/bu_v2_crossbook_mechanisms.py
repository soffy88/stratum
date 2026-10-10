"""P14: Cross-Book Mechanism Comparison.

Compares mechanisms across independently understood books with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookMechanism,
    BookSynthesis,
    CrossBookMechanism,
    CrossBookMechanismRelation,
    CrossBookMechanismRelationType,
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
        # Two empty fields share nothing; scoring them 1.0 manufactured
        # matches between unrelated items whose optional fields were blank.
        return 0.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


@dataclass
class MechanismComparisonResult:
    """Result of mechanism comparison across books."""

    crossbook_mechanisms: list[CrossBookMechanism]
    mechanism_relations: list[CrossBookMechanismRelation]
    traceability: dict[str, list[str]]


class BU2CrossBookMechanismComparator:
    """Compares mechanisms across independently understood books."""

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_mechanisms(
        self, books: list[tuple[Any, BookSynthesis]]
    ) -> dict[str, list[BookMechanism]]:
        """Extract all mechanisms from all books."""
        all_mechs: dict[str, list[BookMechanism]] = {}

        for bu, synth in books:
            if not synth or not synth.mechanism_system:
                continue
            all_mechs[bu.book_id] = synth.mechanism_system.mechanisms

        return all_mechs

    def _compute_mechanism_similarity(
        self, m1: BookMechanism, m2: BookMechanism
    ) -> dict[str, float]:
        """Compute similarity metrics between two mechanisms."""
        return {
            "trigger": _jaccard_similarity(m1.trigger, m2.trigger),
            "precondition": _jaccard_similarity(m1.precondition, m2.precondition),
            "operation": _jaccard_similarity(m1.operation, m2.operation),
            "outcome": _jaccard_similarity(m1.outcome, m2.outcome),
        }

    def _determine_mechanism_relation(
        self,
        m1: BookMechanism,
        m2: BookMechanism,
        similarity: dict[str, float],
    ) -> CrossBookMechanismRelationType:
        """Determine the relation type between two mechanisms."""

        op_sim = similarity["operation"]
        outcome_sim = similarity["outcome"]
        trigger_sim = similarity["trigger"]
        precondition_sim = similarity["precondition"]

        # High operation + outcome similarity -> same mechanism
        if op_sim > 0.7 and outcome_sim > 0.7:
            return CrossBookMechanismRelationType.SAME

        # High operation, different outcome -> variant
        if op_sim > 0.6 and outcome_sim < 0.5:
            return CrossBookMechanismRelationType.VARIANT

        # Complementary: different triggers/preconditions, same outcome
        if outcome_sim > 0.6 and trigger_sim < 0.4 and precondition_sim < 0.4:
            return CrossBookMechanismRelationType.COMPLEMENTARY

        # Competing: same trigger, different operations
        if trigger_sim > 0.6 and op_sim < 0.4:
            return CrossBookMechanismRelationType.COMPETING

        # Incompatible: same trigger, opposite outcomes
        if trigger_sim > 0.5 and outcome_sim < 0.3:
            return CrossBookMechanismRelationType.INCOMPATIBLE

        # Some similarity -> related
        avg_sim = sum(similarity.values()) / len(similarity)
        if avg_sim > 0.4:
            return CrossBookMechanismRelationType.COMPLEMENTARY

        return CrossBookMechanismRelationType.UNKNOWN

    def _build_crossbook_mechanisms(
        self,
        all_mechs: dict[str, list[BookMechanism]],
    ) -> list[CrossBookMechanism]:
        """Build CrossBookMechanism objects."""
        crossbook_mechs = []

        for book_id, mechs in all_mechs.items():
            for mech in mechs:
                cb = CrossBookMechanism(
                    mechanism_id=_stable_id("cbm", book_id, mech.id),
                    book_id=book_id,
                    mechanism_ref=mech.id,
                    trigger=mech.trigger,
                    precondition=mech.precondition,
                    operation=mech.operation,
                    outcome=mech.outcome,
                    confidence=mech.confidence,
                )
                crossbook_mechs.append(cb)

        return crossbook_mechs

    def _align_mechanism_pairs(
        self,
        book_ids: list[str],
        all_mechs: dict[str, list[BookMechanism]],
    ) -> list[CrossBookMechanismRelation]:
        """Align all pairs of mechanisms between books."""
        relations = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                mechs_a = all_mechs.get(book_a_id, [])
                mechs_b = all_mechs.get(book_b_id, [])

                for m1 in mechs_a:
                    for m2 in mechs_b:
                        similarity = self._compute_mechanism_similarity(m1, m2)
                        relation_type = self._determine_mechanism_relation(m1, m2, similarity)

                        if relation_type == CrossBookMechanismRelationType.UNKNOWN:
                            continue

                        evidence = [
                            f"operation_similarity={similarity['operation']:.2f}",
                            f"outcome_similarity={similarity['outcome']:.2f}",
                            f"trigger_similarity={similarity['trigger']:.2f}",
                            f"precondition_similarity={similarity['precondition']:.2f}",
                        ]

                        avg_sim = sum(similarity.values()) / len(similarity)
                        confidence = round(avg_sim, 3)

                        relation = CrossBookMechanismRelation(
                            relation_id=_stable_id("mbr", book_a_id, m1.id, book_b_id, m2.id),
                            source_mechanism=CrossBookMechanism(
                                mechanism_id=_stable_id("cbm", book_a_id, m1.id),
                                book_id=book_a_id,
                                mechanism_ref=m1.id,
                                trigger=m1.trigger,
                                precondition=m1.precondition,
                                operation=m1.operation,
                                outcome=m1.outcome,
                                confidence=m1.confidence,
                            ),
                            target_mechanism=CrossBookMechanism(
                                mechanism_id=_stable_id("cbm", book_b_id, m2.id),
                                book_id=book_b_id,
                                mechanism_ref=m2.id,
                                trigger=m2.trigger,
                                precondition=m2.precondition,
                                operation=m2.operation,
                                outcome=m2.outcome,
                                confidence=m2.confidence,
                            ),
                            relation=relation_type,
                            reason=f"{m1.operation[:40]}... {relation_type.value} {m2.operation[:40]}...",
                            evidence=evidence,
                            confidence=confidence,
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        relations.append(relation)

        return relations

    def compare(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> MechanismComparisonResult:
        """Compare mechanisms across all books."""
        if len(books) < 2:
            return MechanismComparisonResult(
                crossbook_mechanisms=[],
                mechanism_relations=[],
                traceability={},
            )

        all_mechs = self._extract_mechanisms(books)
        book_ids = list(all_mechs.keys())

        crossbook_mechs = self._build_crossbook_mechanisms(all_mechs)
        relations = self._align_mechanism_pairs(book_ids, all_mechs)

        # Build traceability
        traceability = {}
        for cm in crossbook_mechs:
            traceability[cm.mechanism_id] = [cm.book_id]
        for rel in relations:
            traceability[rel.relation_id] = [
                rel.source_mechanism.book_id,
                rel.target_mechanism.book_id,
            ]

        return MechanismComparisonResult(
            crossbook_mechanisms=crossbook_mechs,
            mechanism_relations=relations,
            traceability=traceability,
        )
