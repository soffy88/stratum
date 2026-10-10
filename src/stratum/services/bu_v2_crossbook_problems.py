"""P14: Cross-Book Problem Alignment.

Identifies and aligns problems/questions across independently understood books.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    CrossBookProblem,
    CrossBookProblemRelation,
    CrossBookProblemRelationType,
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
class ProblemAlignmentResult:
    """Result of problem alignment across books."""

    crossbook_problems: list[CrossBookProblem]
    problem_relations: list[CrossBookProblemRelation]
    traceability: dict[str, list[str]]


class BU2CrossBookProblemAligner:
    """Aligns problems/questions across independently understood books."""

    def __init__(self, provider=None):
        self.provider = provider

    def _extract_problems(self, books: list[tuple[Any, BookSynthesis]]) -> dict[str, list[dict]]:
        """Extract all problems/questions from all books."""
        all_problems: dict[str, list[dict]] = {}

        for bu, synth in books:
            if not synth or not synth.thesis:
                continue

            problems = []
            # Extract problem statements and central questions
            for t in synth.thesis.problem_statements:
                problems.append(
                    {
                        "problem_id": t.id,
                        "statement": t.statement,
                        "type": "PROBLEM",
                        "confidence": t.confidence,
                        "provenance": t.provenance,
                    }
                )
            for t in synth.thesis.central_questions:
                problems.append(
                    {
                        "problem_id": t.id,
                        "statement": t.statement,
                        "type": "QUESTION",
                        "confidence": t.confidence,
                        "provenance": t.provenance,
                    }
                )
            all_problems[bu.book_id] = problems

        return all_problems

    def _determine_problem_relation(
        self,
        p1: dict,
        p2: dict,
        similarity: float,
    ) -> CrossBookProblemRelationType:
        """Determine the relation type between two problems."""

        if similarity > 0.8:
            return CrossBookProblemRelationType.SAME_PROBLEM
        elif similarity > 0.6:
            # Check for sub/super problem
            if len(p1["statement"]) < len(p2["statement"]):
                return CrossBookProblemRelationType.SUBPROBLEM
            else:
                return CrossBookProblemRelationType.SUPERPROBLEM
        elif similarity > 0.4:
            return CrossBookProblemRelationType.RELATED_PROBLEM
        elif similarity > 0.2:
            return CrossBookProblemRelationType.ORTHOGONAL
        else:
            return CrossBookProblemRelationType.UNKNOWN

    def _build_crossbook_problems(
        self,
        all_problems: dict[str, list[dict]],
    ) -> list[CrossBookProblem]:
        """Build CrossBookProblem objects."""
        crossbook_problems = []

        for book_id, problems in all_problems.items():
            for prob in problems:
                cb = CrossBookProblem(
                    problem_id=_stable_id("cbp", book_id, prob["problem_id"]),
                    book_id=book_id,
                    problem_ref=prob["problem_id"],
                    statement=prob["statement"],
                    scope=prob["type"],
                    domain="",  # Could extract from book metadata
                )
                crossbook_problems.append(cb)

        return crossbook_problems

    def _align_problem_pairs(
        self,
        book_ids: list[str],
        all_problems: dict[str, list[dict]],
    ) -> list[CrossBookProblemRelation]:
        """Align all pairs of problems between books."""
        relations = []

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                probs_a = all_problems.get(book_a_id, [])
                probs_b = all_problems.get(book_b_id, [])

                for p1 in probs_a:
                    for p2 in probs_b:
                        sim = _jaccard_similarity(p1["statement"], p2["statement"])
                        relation_type = self._determine_problem_relation(p1, p2, sim)

                        if relation_type == CrossBookProblemRelationType.UNKNOWN:
                            continue

                        evidence = [
                            f"statement_similarity={sim:.2f}",
                            f"type_a={p1['type']}, type_b={p2['type']}",
                        ]

                        confidence = round(sim, 3)

                        relation = CrossBookProblemRelation(
                            relation_id=_stable_id(
                                "pbr", book_a_id, p1["problem_id"], book_b_id, p2["problem_id"]
                            ),
                            source_problem=CrossBookProblem(
                                problem_id=_stable_id("cbp", book_a_id, p1["problem_id"]),
                                book_id=book_a_id,
                                problem_ref=p1["problem_id"],
                                statement=p1["statement"],
                                scope=p1["type"],
                                domain="",
                            ),
                            target_problem=CrossBookProblem(
                                problem_id=_stable_id("cbp", book_b_id, p2["problem_id"]),
                                book_id=book_b_id,
                                problem_ref=p2["problem_id"],
                                statement=p2["statement"],
                                scope=p2["type"],
                                domain="",
                            ),
                            relation=relation_type,
                            reason=f"{p1['type']}:{p1['statement'][:50]}... {relation_type.value} {p2['type']}:{p2['statement'][:50]}...",
                            evidence=evidence,
                            confidence=confidence,
                        )
                        relations.append(relation)

        return relations

    def align(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> ProblemAlignmentResult:
        """Align problems across all books."""
        if len(books) < 2:
            return ProblemAlignmentResult(
                crossbook_problems=[],
                problem_relations=[],
                traceability={},
            )

        all_problems = self._extract_problems(books)
        book_ids = list(all_problems.keys())

        crossbook_problems = self._build_crossbook_problems(all_problems)
        relations = self._align_problem_pairs(book_ids, all_problems)

        traceability = {}
        for cp in crossbook_problems:
            traceability[cp.problem_id] = [cp.book_id]
        for rel in relations:
            traceability[rel.relation_id] = [rel.source_problem.book_id, rel.target_problem.book_id]

        return ProblemAlignmentResult(
            crossbook_problems=crossbook_problems,
            problem_relations=relations,
            traceability=traceability,
        )
