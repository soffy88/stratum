"""P14: Cross-Book Knowledge Gap Detection.

Identifies knowledge gaps across independently understood books with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    CrossBookKnowledgeGap,
    KnowledgeGapType,
    ThesisProvenance,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


@dataclass
class GapDetectionResult:
    """Result of knowledge gap detection across books."""

    knowledge_gaps: list[CrossBookKnowledgeGap]
    traceability: dict[str, list[str]]


class BU2CrossBookGapDetector:
    """Detects knowledge gaps across independently understood books.

    Does not invent gaps - only identifies what is genuinely missing
    based on the available evidence across books.
    """

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_theses(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all theses from all books."""
        all_theses: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.thesis:
                continue

            theses = []
            for t in synth.thesis.all_theses():
                theses.append(
                    {
                        "thesis_id": t.id,
                        "type": t.type,
                        "statement": t.statement,
                        "confidence": t.confidence,
                        "evidence_refs": t.evidence_refs,
                        "supporting_arguments": t.supporting_arguments,
                    }
                )
            all_theses[bu.book_id] = theses

        return all_theses

    def _extract_evidence_coverage(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, dict]:
        """Extract evidence coverage metrics from all books."""
        coverage: dict[str, dict] = {}

        for bu, synth in books:
            if not synth or not synth.evidence_map:
                continue

            coverage[bu.book_id] = {
                "coverage": synth.evidence_map.evidence_coverage,
                "unsupported_count": synth.evidence_map.unsupported_claim_count,
                "model_inference_ratio": synth.evidence_map.model_inference_ratio,
                "entries": len(synth.evidence_map.entries),
            }

        return coverage

    def _extract_mechanisms(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all mechanisms from all books."""
        all_mechs: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.mechanism_system:
                continue

            mechs = []
            for m in synth.mechanism_system.mechanisms:
                mechs.append(
                    {
                        "mechanism_id": m.id,
                        "trigger": m.trigger,
                        "precondition": m.precondition,
                        "operation": m.operation,
                        "outcome": m.outcome,
                        "confidence": m.confidence,
                        "source_chapters": m.source_chapters,
                    }
                )
            all_mechs[bu.book_id] = mechs

        return all_mechs

    def _extract_arguments(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all arguments from all books."""
        all_args: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.argument_system:
                continue

            args = []
            for arg in synth.argument_system.all_arguments():
                args.append(
                    {
                        "argument_id": arg.id,
                        "level": arg.level,
                        "what": arg.what,
                        "conclusion": arg.conclusion,
                        "evidence_refs": arg.evidence_refs,
                    }
                )
            all_args[bu.book_id] = args

        return all_args

    def _detect_unanswered(
        self,
        all_theses: dict[str, list[dict]],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect unanswered questions across books."""
        gaps = []

        # Collect all questions
        all_questions = []
        for book_id, theses in all_theses.items():
            for t in theses:
                if t["type"] in ("QUESTION", "PROBLEM"):
                    all_questions.append(
                        {
                            "book_id": book_id,
                            "thesis_id": t["thesis_id"],
                            "statement": t["statement"],
                            "evidence_refs": t["evidence_refs"],
                            "supporting_arguments": t["supporting_arguments"],
                        }
                    )

        # Questions with no evidence and no supporting arguments -> unanswered
        for q in all_questions:
            if not q["evidence_refs"] and not q["supporting_arguments"]:
                gap = CrossBookKnowledgeGap(
                    gap_id=_stable_id("gap", q["book_id"], q["thesis_id"]),
                    type=KnowledgeGapType.UNANSWERED,
                    description=f"Question '{q['statement'][:100]}...' has no evidence or supporting arguments",
                    affected_books=[q["book_id"]],
                    missing_elements=["evidence", "supporting_arguments"],
                    reason="No evidence or arguments found for this question",
                    confidence=0.8,
                    provenance=ThesisProvenance.MODEL_INFERRED,
                )
                gaps.append(gap)

        return gaps

    def _detect_weakly_supported(
        self,
        all_theses: dict[str, list[dict]],
        evidence_coverage: dict[str, dict],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect weakly supported theses."""
        gaps = []

        for book_id, theses in all_theses.items():
            coverage = evidence_coverage.get(book_id, {})
            model_inference_ratio = coverage.get("model_inference_ratio", 0)

            for t in theses:
                if t["type"] in ("CORE", "SUPPORTING", "CONCLUSION"):
                    # High model inference ratio + low confidence -> weakly supported
                    if model_inference_ratio > 0.5 and t["confidence"] < 0.5:
                        gap = CrossBookKnowledgeGap(
                            gap_id=_stable_id("gap", t["thesis_id"]),
                            type=KnowledgeGapType.WEAKLY_SUPPORTED,
                            description=f"Thesis '{t['statement'][:100]}...' has low confidence ({t['confidence']}) and high model inference ratio ({model_inference_ratio})",
                            affected_books=[book_id],
                            missing_elements=["direct_evidence", "stronger_arguments"],
                            reason="High reliance on model inference rather than direct evidence",
                            confidence=round(model_inference_ratio, 3),
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        gaps.append(gap)

        return gaps

    def _detect_conflicting(
        self,
        books: list[tuple[Any, Any]],  # Would need contradiction detector
    ) -> list[CrossBookKnowledgeGap]:
        """Detect conflicting evidence leading to gaps."""
        gaps = []
        # This would be populated by contradiction detector
        # For now, return empty - contradictions are handled separately
        return gaps

    def _detect_missing_bridge(
        self,
        books: list[tuple[Any, Any]],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect missing bridges between mechanisms/arguments across books."""
        gaps = []

        # Example: Book A explains mechanism X, Book B explains outcome Y
        # No book establishes X -> Y
        # This would require cross-book mechanism/argument comparison
        # For now, return empty
        return gaps

    def _detect_missing_evidence(
        self,
        evidence_coverage: dict[str, dict],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect claims with missing evidence."""
        gaps = []

        for book_id, coverage in evidence_coverage.items():
            unsupported = coverage.get("unsupported_count", 0)
            if unsupported > 0:
                gap = CrossBookKnowledgeGap(
                    gap_id=_stable_id("gap", book_id, "missing_evidence"),
                    type=KnowledgeGapType.MISSING_EVIDENCE,
                    description=f"Book {book_id} has {unsupported} unsupported claims",
                    affected_books=[book_id],
                    missing_elements=["direct_evidence"],
                    reason=f"{unsupported} claims lack direct evidence support",
                    confidence=0.7,
                    provenance=ThesisProvenance.MODEL_INFERRED,
                )
                gaps.append(gap)

        return gaps

    def _detect_scope_gap(
        self,
        books: list[tuple[Any, Any]],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect scope gaps - topics covered in one book but not another."""
        gaps = []

        # Would require topic modeling across books
        # For now, return empty
        return gaps

    def _detect_book_set_limit(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> list[CrossBookKnowledgeGap]:
        """Detect if the book set itself is insufficient for a domain."""
        gaps = []

        if len(books) < 3:
            gap = CrossBookKnowledgeGap(
                gap_id=_stable_id("gap", "collection", "size"),
                type=KnowledgeGapType.BOOK_SET_LIMIT,
                description=f"Collection has only {len(books)} books, may be insufficient for comprehensive cross-book analysis",
                affected_books=[bu.book_id for bu, _ in books],
                missing_elements=["additional_books"],
                reason="Small collection size limits cross-book analysis validity",
                confidence=0.9,
                provenance=ThesisProvenance.MODEL_INFERRED,
            )
            gaps.append(gap)

        return gaps

    def detect(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> GapDetectionResult:
        """Detect knowledge gaps across all books."""
        if len(books) < 2:
            return GapDetectionResult(
                knowledge_gaps=[],
                traceability={},
            )

        all_theses = self._extract_theses(books)
        evidence_coverage = self._extract_evidence_coverage(books)

        gaps = []
        gaps.extend(self._detect_unanswered(all_theses))
        gaps.extend(self._detect_weakly_supported(all_theses, evidence_coverage))
        gaps.extend(self._detect_missing_evidence(evidence_coverage))
        gaps.extend(self._detect_book_set_limit(books))

        # Build traceability
        traceability = {}
        for gap in gaps:
            traceability[gap.gap_id] = gap.affected_books

        return GapDetectionResult(
            knowledge_gaps=gaps,
            traceability=traceability,
        )
