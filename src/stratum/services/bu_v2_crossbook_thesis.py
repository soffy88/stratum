"""P14: Cross-Book Thesis Comparison.

Compares theses across independently understood books with full traceability.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    BookThesis,
    CrossBookThesis,
    CrossBookThesisRelation,
    CrossBookThesisRelationType,
    ThesisProvenance,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _normalize_text(text: str) -> str:
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
class ThesisComparisonResult:
    """Result of thesis comparison across books."""

    crossbook_theses: list["CrossBookThesis"]
    thesis_relations: list["CrossBookThesisRelation"]
    traceability: dict[str, list[str]] = field(default_factory=dict)


# Minimum statement overlap before a type/indicator rule may call it EXTENDS.
_EXTENDS_TOPIC_FLOOR = 0.1


class BU2CrossBookThesisComparator:
    """Compares theses across independently understood books."""

    def __init__(self, provider=None):
        self.provider = provider

    def _determine_thesis_relation(
        self,
        t1: "BookThesis",
        t2: "BookThesis",
        similarity: dict[str, float],
    ) -> "CrossBookThesisRelationType":
        """Determine the relation type between two theses using layered classification."""

        # Check EXTENDS special patterns first (before similarity threshold)
        if self._is_extends(t1, t2, similarity):
            return "EXTENDS"

        # Stage 1: Candidate retrieval (high recall)
        if similarity["statement"] < 0.2:
            return "UNKNOWN"

        # Stage 2: Check for contradiction (highest priority)
        if self._is_contradiction(t1, t2, similarity):
            return "CONTRADICTS"

        # Stage 2c: QUALIFIES (similar but with qualification/constraint)
        if self._is_qualifies(t1, t2, similarity):
            return "QUALIFIES"

        # Stage 3: SUPPORTS (same type, high similarity, or PROBLEM -> CORE/SUPPORTING)
        if self._is_supports(t1, t2, similarity):
            return "SUPPORTS"

        # Stage 3b: EXTENDS (general -> specific)
        if self._is_extends(t1, t2, similarity):
            return "EXTENDS"

        # Stage 3c: COMPLEMENTS (different aspects of same topic)
        if self._is_complementary(t1, t2, similarity):
            return "COMPLEMENTS"

        return "UNKNOWN"

    def _is_contradiction(self, t1: "BookThesis", t2: "BookThesis", sim: dict[str, float]) -> bool:
        """Detect contradiction: opposing statements about same topic."""
        stmt_sim = sim["statement"]
        if stmt_sim < 0.3 or stmt_sim > 0.7:
            return False
        # Check for negation patterns
        t1_words = set(_normalize_text(t1.statement).split())
        t2_words = set(_normalize_text(t2.statement).split())
        negation_words = {"not", "no", "never", "cannot", "does not", "is not", "are not"}
        t1_has_neg = bool(t1_words & negation_words)
        t2_has_neg = bool(t2_words & negation_words)
        if t1_has_neg != t2_has_neg:
            # Same topic, one has negation, other doesn't
            return True
        return False

    def _is_supports(self, t1: "BookThesis", t2: "BookThesis", sim: dict[str, float]) -> bool:
        """Check for SUPPORTS relation."""
        # Same type, high similarity
        if sim["type_match"] and sim["statement"] > 0.7:
            return True
        # CORE -> SUPPORTING (same direction, natural progression)
        if t1.type == "CORE" and t2.type == "SUPPORTING":
            return True
        return False

    def _is_qualifies(self, t1: "BookThesis", t2: "BookThesis", sim: dict[str, float]) -> bool:
        """Check for QUALIFIES relation."""
        stmt_sim = sim["statement"]
        if stmt_sim < 0.3:
            return False
        # Check for qualification patterns: "when", "if", "except", "provided", "unless", "except"
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        t1_words = set(t1_text.split())
        t2_words = set(t2_text.split())
        # t2 is t1 with qualification (t2 has extra constraint words)
        qualifier_words = {
            "when",
            "if",
            "except",
            "provided",
            "unless",
            "except",
            "only",
            "where",
            "condition",
            "constraint",
            "provided that",
            "assuming",
            "given",
        }
        extra_qualifiers = t2_words - t1_words
        if extra_qualifiers & qualifier_words:
            return True
        # Similar content but t2 adds constraint
        if sim["statement"] > 0.4 and len(t2_words - t1_words) > 0:
            added_words = t2_words - t1_words
            if any(w in qualifier_words for w in added_words):
                return True
        # Structural qualification: t2 narrows scope of t1
        if sim["statement"] > 0.3 and len(t2_words) <= len(t1_words):
            # t2 is more specific/narrower
            overlap = t1_words & t2_words
            if len(overlap) >= 2:
                return True
        return False

    def _is_extends(self, t1: "BookThesis", t2: "BookThesis", sim: dict[str, float]) -> bool:
        """Detect EXTENDS: general -> specific, problem -> solution, claim -> evidence."""
        # The type and indicator rules below say nothing about topic: without a
        # floor every PROBLEM thesis "extended" every CORE thesis of the other
        # book, and any statement containing "theorem" extended everything.
        if sim["statement"] < _EXTENDS_TOPIC_FLOOR:
            return False
        # Problem -> Solution (type-based, doesn't require high text similarity)
        if t1.type == "PROBLEM" and t2.type in ("CORE", "SUPPORTING"):
            return True
        # Claim -> Evidence (based on evidence indicators in t2)
        if self._is_claim_evidence(t1, t2):
            return True
        # General concept -> Specific elaboration (based on text similarity)
        if sim["statement"] >= 0.25 and self._is_elaboration(t1, t2):
            return True
        return False

    def _is_claim_evidence(self, t1: "BookThesis", t2: "BookThesis") -> bool:
        """Check if t1 is a claim and t2 is supporting evidence."""
        _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        evidence_indicators = {
            "defined as",
            "defined by",
            "formula",
            "limit of",
            "limit of the",
            "formula for",
            "because",
            "since",
            "given that",
            "proof",
            "definition",
            "theorem",
        }
        set(t2_text.split())
        if any(ind in t2_text for ind in evidence_indicators):
            return True
        return False

    def _is_elaboration(self, t1: "BookThesis", t2: "BookThesis") -> bool:
        """Check if t2 elaborates on t1 (general concept -> specific detail)."""
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        # t2 has more specific terms, t1 is more general
        t1_words = set(t1_text.split())
        t2_words = set(t2_text.split())
        if len(t2_words) > len(t1_words) * 1.2:
            # t2 is more detailed
            # Check if t2 contains t1's key concepts
            overlap = set(t1_text.split()) & set(t2_text.split())
            if len(overlap) >= 2:
                return True
        return False

    def _is_generalizes(self, t1: "BookThesis", t2: "BookThesis") -> bool:
        """Detect GENERALIZES: specific -> general."""
        # Specific rule/instance -> general principle
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        # t1 is specific instance, t2 is general pattern
        set(t1_text.split())
        set(t2_text.split())
        if len(t1_text.split()) > len(t2_text.split()) and len(t2_text.split()) > 3:
            # t1 is more specific, t2 is more general
            overlap = set(t1_text.split()) & set(t2_text.split())
            if len(overlap) >= 2:
                return True
        # Check for generalization keywords
        gen_keywords = {
            "generalizes",
            "generalize",
            "pattern",
            "rule",
            "principle",
            "rule of",
            "for all",
        }
        if any(kw in _normalize_text(t2.statement) for kw in gen_keywords):
            return True
        return False

    def _is_complementary(self, t1: "BookThesis", t2: "BookThesis", sim: dict[str, float]) -> bool:
        """Detect complementary theses (different aspects of same topic)."""
        stmt_sim = sim["statement"]
        if stmt_sim < 0.3 or stmt_sim > 0.7:
            return False
        # Check for complementary patterns
        complementary_pairs = [
            ("derivative", "integral"),
            ("instantaneous", "accumulated"),
            ("rate", "total"),
            ("rate", "accumulation"),
            ("differentiation", "integration"),
            ("limit", "continuity"),
        ]
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        for p1, p2 in complementary_pairs:
            if (p1 in t1_text and p2 in t2_text) or (p2 in t1_text and p1 in t2_text):
                return True
        return False

    def _compute_thesis_similarity(self, t1: "BookThesis", t2: "BookThesis") -> dict[str, float]:
        """Compute similarity metrics between two theses."""
        return {
            "statement": _jaccard_similarity(t1.statement, t2.statement),
            "type_match": 1.0 if t1.type == t2.type else 0.0,
            "scope_match": 1.0 if t1.scope == t2.scope else 0.0,
            "provenance_match": 1.0 if t1.provenance == t2.provenance else 0.0,
        }

    def _extract_theses(
        self, books: list[tuple[Any, "BookSynthesis"]]
    ) -> dict[str, list["BookThesis"]]:
        """Extract all theses from all books with source context."""
        all_theses: dict[str, list["BookThesis"]] = {}

        for bu, synth in books:
            if not synth or not synth.thesis:
                continue

            theses = synth.thesis.all_theses()
            all_theses[bu.book_id] = theses

        return all_theses

    def _build_crossbook_theses(
        self,
        all_theses: dict[str, list["BookThesis"]],
    ) -> list["CrossBookThesis"]:
        """Build CrossBookThesis objects from all theses."""
        crossbook_theses = []

        for book_id, theses in all_theses.items():
            for thesis in theses:
                cb = CrossBookThesis(
                    thesis_id=_stable_id("cbt", book_id, thesis.id),
                    book_id=book_id,
                    thesis_ref=thesis.id,
                    statement=thesis.statement,
                    type=thesis.type,
                    confidence=thesis.confidence,
                    provenance=thesis.provenance,
                )
                crossbook_theses.append(cb)
        return crossbook_theses

    def _align_thesis_pairs(
        self,
        book_ids: list[str],
        all_theses: dict[str, list["BookThesis"]],
    ) -> list["CrossBookThesisRelation"]:
        """Align all pairs of theses between books."""
        relations = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                theses_a = all_theses.get(book_a_id, [])
                theses_b = all_theses.get(book_b_id, [])

                for t1 in theses_a:
                    for t2 in theses_b:
                        similarity = self._compute_thesis_similarity(t1, t2)
                        relation_type = self._determine_thesis_relation(t1, t2, similarity)

                        if relation_type == "UNKNOWN":
                            continue

                        evidence = [
                            f"statement_similarity={similarity['statement']:.2f}",
                            f"type_match={similarity['type_match']}",
                            f"scope_match={similarity['scope_match']}",
                            f"type_a={t1.type}, type_b={t2.type}",
                        ]

                        avg_sim = sum(similarity.values()) / len(similarity)
                        confidence = round(avg_sim, 3)

                        relation = CrossBookThesisRelation(
                            relation_id=_stable_id("tbr", book_a_id, t1.id, book_b_id, t2.id),
                            source_thesis=CrossBookThesis(
                                thesis_id=_stable_id("cbt", book_a_id, t1.id),
                                book_id=book_a_id,
                                thesis_ref=t1.id,
                                statement=t1.statement,
                                type=t1.type,
                                confidence=t1.confidence,
                                provenance=t1.provenance,
                            ),
                            target_thesis=CrossBookThesis(
                                thesis_id=_stable_id("cbt", book_b_id, t2.id),
                                book_id=book_b_id,
                                thesis_ref=t2.id,
                                statement=t2.statement,
                                type=t2.type,
                                confidence=t2.confidence,
                                provenance=t2.provenance,
                            ),
                            relation=CrossBookThesisRelationType(relation_type),
                            reason=f"{t1.type}:{t1.statement[:50]}... {relation_type} {t2.type}:{t2.statement[:50]}...",
                            evidence=evidence,
                            confidence=confidence,
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        relations.append(relation)

        return relations

    def compare(
        self,
        books: list[tuple[Any, "BookSynthesis"]],
    ) -> "ThesisComparisonResult":
        """Compare theses across all books.

        Args:
            books: List of (BookUnderstandingV2, BookSynthesis) tuples

        Returns:
            ThesisComparisonResult with crossbook theses and relations
        """
        if len(books) < 2:
            return ThesisComparisonResult(
                crossbook_theses=[],
                thesis_relations=[],
                traceability={},
            )

        all_theses = self._extract_theses(books)
        book_ids = list(all_theses.keys())

        crossbook_theses = self._build_crossbook_theses(all_theses)
        relations = self._align_thesis_pairs(book_ids, all_theses)

        # Build traceability
        traceability = {}
        for cb in crossbook_theses:
            traceability[cb.thesis_id] = [cb.book_id]
        for rel in relations:
            traceability[rel.relation_id] = [rel.source_thesis.book_id, rel.target_thesis.book_id]

        return ThesisComparisonResult(
            crossbook_theses=crossbook_theses,
            thesis_relations=relations,
            traceability=traceability,
        )
