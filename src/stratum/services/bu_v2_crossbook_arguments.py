"""P14: Cross-Book Argument Comparison.

Compares arguments across independently understood books with full traceability.
Identifies cross-book argument transfers (theory-to-application, etc.).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookArgument,
    BookSynthesis,
    CrossBookArgument,
    CrossBookArgumentRelation,
    CrossBookArgumentRelationType,
    CrossBookArgumentTransfer,
    CrossBookArgumentTransferType,
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


def _is_argument_extends(a1: "BookArgument", a2: "BookArgument") -> bool:
    """Detect EXTENDS: general argument -> specific argument."""
    # General -> Specific patterns
    specific_indicators = {
        "instantaneous",
        "measure",
        "compute",
        "calculate",
        "derive",
        "limit",
        "quotient",
        "sum",
        "integral",
    }

    a1_what = _normalize_text(a1.what)
    a2_what = _normalize_text(a2.what)
    a1_words = set(a1_what.split())
    a2_words = set(a2_what.split())

    a1_has_general = bool(a1_words & {"analyze", "analyzes", "study", "examine", "investigate"})
    a2_has_specific = bool(a2_words & specific_indicators)

    # Check if a1 is more general (has general terms, fewer specific terms)
    a1_general_count = len(a1_words & {"analyze", "analyzes", "study", "examine", "investigate"})
    a2_specific_count = len(a2_words & specific_indicators)

    if a1_has_general and a2_has_specific and a1_general_count >= a2_specific_count:
        return True
    return False


def _is_argument_generalizes(a1: "BookArgument", a2: "BookArgument") -> bool:
    """Detect GENERALIZES: specific argument -> general argument."""
    # Specific -> General patterns

    a1_what = _normalize_text(a1.what)
    a2_what = _normalize_text(a2.what)
    a1_words = set(a1_what.split())
    a2_words = set(a2_what.split())

    a1_has_specific = bool(
        a1_words
        & {
            "instantaneous",
            "measure",
            "compute",
            "calculate",
            "derive",
            "limit",
            "quotient",
            "sum",
            "integral",
        }
    )
    a2_has_general = bool(a2_words & {"analyze", "analyzes", "study", "examine", "investigate"})

    # a1 is specific, a2 is general
    a1_specific_count = len(
        a1_words
        & {
            "instantaneous",
            "measure",
            "compute",
            "calculate",
            "derive",
            "limit",
            "quotient",
            "sum",
            "integral",
        }
    )
    a2_general_count = len(a2_words & {"analyze", "analyzes", "study", "examine", "investigate"})

    if a1_has_specific and a2_has_general and a1_specific_count >= a2_general_count:
        return True
    return False


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
class ArgumentComparisonResult:
    """Result of argument comparison across books."""

    crossbook_arguments: list[CrossBookArgument]
    argument_relations: list[CrossBookArgumentRelation]
    argument_transfers: list[CrossBookArgumentTransfer]
    traceability: dict[str, list[str]]


class BU2CrossBookArgumentComparator:
    """Compares arguments across independently understood books."""

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_arguments(
        self, books: list[tuple[Any, BookSynthesis]]
    ) -> dict[str, list[BookArgument]]:
        """Extract all arguments from all books with source context."""
        all_args: dict[str, list[BookArgument]] = {}

        for bu, synth in books:
            if not synth or not synth.argument_system:
                continue

            args = synth.argument_system.all_arguments()
            all_args[bu.book_id] = args

        return all_args

    def _compute_argument_similarity(self, a1: BookArgument, a2: BookArgument) -> dict[str, float]:
        """Compute similarity metrics between two arguments."""
        return {
            "what": _jaccard_similarity(a1.what, a2.what),
            "why": _jaccard_similarity(a1.why, a2.why),
            "how": _jaccard_similarity(a1.how, a2.how),
            "conclusion": _jaccard_similarity(a1.conclusion, a2.conclusion),
            "level_match": 1.0 if a1.level == a2.level else 0.0,
            "evidence_overlap": _jaccard_similarity(
                " ".join(a1.evidence_refs), " ".join(a2.evidence_refs)
            ),
        }

    def _determine_argument_relation(
        self,
        a1: BookArgument,
        a2: BookArgument,
        similarity: dict[str, float],
    ) -> CrossBookArgumentRelationType:
        """Determine the relation type between two arguments."""

        what_sim = similarity["what"]
        similarity["why"]
        level_match = similarity["level_match"]

        # Stage 1: Semantic direction detection (highest priority)
        if _is_argument_extends(a1, a2):
            return CrossBookArgumentRelationType.EXTENDS
        if _is_argument_generalizes(a1, a2):
            return CrossBookArgumentRelationType.GENERALIZES

        # Same level, high content similarity -> supports/refines
        if level_match and what_sim > 0.6 and similarity["why"] > 0.5:
            return CrossBookArgumentRelationType.SUPPORTS

        # High similarity but different focus -> complementary
        if what_sim > 0.4 and similarity["why"] > 0.4:
            return CrossBookArgumentRelationType.COMPLEMENTARY

        # Moderate similarity -> alternative
        if what_sim > 0.3:
            return CrossBookArgumentRelationType.ALTERNATIVE

        return CrossBookArgumentRelationType.UNKNOWN

    def _detect_argument_transfer(
        self,
        a1: BookArgument,
        a2: BookArgument,
        similarity: dict[str, float],
    ) -> CrossBookArgumentTransferType | None:
        """Detect theory-to-application or other transfers."""

        # Theory (book A) -> Application (book B)
        if (
            a1.level <= 1
            and a2.level >= 2
            and similarity["what"] > 0.4
            and similarity["conclusion"] > 0.4
        ):
            return CrossBookArgumentTransferType.THEORY_TO_APPLICATION

        # Foundation -> Extension
        if a1.level == 0 and a2.level >= 1 and similarity["what"] > 0.5:
            return CrossBookArgumentTransferType.FOUNDATION_TO_EXTENSION

        # Concept -> Mechanism
        if ("concept" in a1.what.lower() or "define" in a1.why.lower()) and (
            "mechanism" in a2.what.lower() or "process" in a2.how.lower()
        ):
            return CrossBookArgumentTransferType.CONCEPT_TO_MECHANISM

        return None

    def _build_crossbook_arguments(
        self,
        all_args: dict[str, list[BookArgument]],
    ) -> list[CrossBookArgument]:
        """Build CrossBookArgument objects from all arguments."""
        crossbook_args = []

        for book_id, args in all_args.items():
            for arg in args:
                cb = CrossBookArgument(
                    argument_id=_stable_id("cba", book_id, arg.id),
                    book_id=book_id,
                    argument_ref=arg.id,
                    level=arg.level,
                    what=arg.what,
                    why=arg.why,
                    how=arg.how,
                    conclusion=arg.conclusion,
                    evidence_refs=arg.evidence_refs,
                    status=arg.status,
                    confidence=arg.confidence,
                )
                crossbook_args.append(cb)

        return crossbook_args

    def _align_argument_pairs(
        self,
        book_ids: list[str],
        all_args: dict[str, list[BookArgument]],
    ) -> tuple[list[CrossBookArgumentRelation], list[CrossBookArgumentTransfer]]:
        """Align all pairs of arguments between books."""
        relations = []
        transfers = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                args_a = all_args.get(book_a_id, [])
                args_b = all_args.get(book_b_id, [])

                for a1 in args_a:
                    for a2 in args_b:
                        similarity = self._compute_argument_similarity(a1, a2)
                        relation_type = self._determine_argument_relation(a1, a2, similarity)

                        if relation_type != CrossBookArgumentRelationType.UNKNOWN:
                            evidence = [
                                f"what_similarity={similarity['what']:.2f}",
                                f"why_similarity={similarity['why']:.2f}",
                                f"conclusion_similarity={similarity['conclusion']:.2f}",
                                f"level_a={a1.level}, level_b={a2.level}",
                            ]

                            avg_sim = (
                                sum(v for k, v in similarity.items() if k != "level_match") / 5
                            )
                            confidence = round(avg_sim, 3)

                            relation = CrossBookArgumentRelation(
                                relation_id=_stable_id("abr", book_a_id, a1.id, book_b_id, a2.id),
                                source_argument=CrossBookArgument(
                                    argument_id=_stable_id("cba", book_a_id, a1.id),
                                    book_id=book_a_id,
                                    argument_ref=a1.id,
                                    level=a1.level,
                                    what=a1.what,
                                    why=a1.why,
                                    how=a1.how,
                                    conclusion=a1.conclusion,
                                    evidence_refs=a1.evidence_refs,
                                    status=a1.status,
                                    confidence=a1.confidence,
                                ),
                                target_argument=CrossBookArgument(
                                    argument_id=_stable_id("cba", book_b_id, a2.id),
                                    book_id=book_b_id,
                                    argument_ref=a2.id,
                                    level=a2.level,
                                    what=a2.what,
                                    why=a2.why,
                                    how=a2.how,
                                    conclusion=a2.conclusion,
                                    evidence_refs=a2.evidence_refs,
                                    status=a2.status,
                                    confidence=a2.confidence,
                                ),
                                relation=relation_type,
                                reason=f"L{a1.level}:{a1.what[:40]}... {relation_type.value} L{a2.level}:{a2.what[:40]}...",
                                evidence=evidence,
                                confidence=confidence,
                                provenance=ThesisProvenance.MODEL_INFERRED,
                            )
                            relations.append(relation)

                        # Check for transfer
                        transfer_type = self._detect_argument_transfer(a1, a2, similarity)
                        if transfer_type:
                            transfer = CrossBookArgumentTransfer(
                                transfer_id=_stable_id("xfer", book_a_id, a1.id, book_b_id, a2.id),
                                source_book_id=book_a_id,
                                source_argument_id=a1.id,
                                target_book_id=book_b_id,
                                target_argument_id=a2.id,
                                transfer_type=transfer_type,
                                reason=f"L{a1.level} argument transfers to L{a2.level} via {transfer_type.value}",
                                confidence=round(similarity["what"], 3),
                            )
                            transfers.append(transfer)

        return relations, transfers

    def compare(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> ArgumentComparisonResult:
        """Compare arguments across all books.

        Args:
            books: List of (BookUnderstandingV2, BookSynthesis) tuples

        Returns:
            ArgumentComparisonResult with crossbook arguments, relations, transfers
        """
        if len(books) < 2:
            return ArgumentComparisonResult(
                crossbook_arguments=[],
                argument_relations=[],
                argument_transfers=[],
                traceability={},
            )

        all_args = self._extract_arguments(books)
        book_ids = list(all_args.keys())

        crossbook_args = self._build_crossbook_arguments(all_args)
        relations, transfers = self._align_argument_pairs(book_ids, all_args)

        # Build traceability
        traceability = {}
        for ca in crossbook_args:
            traceability[ca.argument_id] = [ca.book_id]
        for rel in relations:
            traceability[rel.relation_id] = [
                rel.source_argument.book_id,
                rel.target_argument.book_id,
            ]
        for xfer in transfers:
            traceability[xfer.transfer_id] = [xfer.source_book_id, xfer.target_book_id]

        return ArgumentComparisonResult(
            crossbook_arguments=crossbook_args,
            argument_relations=relations,
            argument_transfers=transfers,
            traceability=traceability,
        )
