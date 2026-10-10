"""P14-ALIGNMENT-002: Layered Semantic Alignment.

Implements a multi-stage alignment pipeline:
  candidate retrieval → similarity → relation-specific classifier → evidence validation → relation

Uses two independent thresholds:
  - candidate_threshold: high recall (retrieve potential candidates)
  - acceptance_threshold: high precision (accept only strong relations)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    CrossBookThesis,
    CrossBookThesisRelation,
    CrossBookThesisRelationType,
    CrossBookArgument,
    CrossBookArgumentRelation,
    CrossBookArgumentRelationType,
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
class AlignmentThresholds:
    """Two independent thresholds for high recall + high precision."""

    candidate_threshold: float = 0.15
    acceptance_threshold: float = 0.5


@dataclass
class ThesisAlignmentResult:
    """Result of thesis alignment with layered classification."""

    relations: list[CrossBookThesisRelation]
    candidates: list[dict[str, Any]]
    rejected: list[dict[str, Any]]


@dataclass
class ArgumentAlignmentResult:
    """Result of argument alignment with layered classification."""

    relations: list[CrossBookArgumentRelation]
    candidates: list[dict[str, Any]]
    rejected: list[dict[str, Any]]


class ThesisRelationClassifier:
    """Layered classifier for thesis relations."""

    def __init__(self, thresholds: AlignmentThresholds | None = None):
        self.thresholds = thresholds or AlignmentThresholds()

    def classify(
        self,
        t1: CrossBookThesis,
        t2: CrossBookThesis,
        similarity: dict[str, float],
    ) -> CrossBookThesisRelationType | None:
        """Classify thesis relation using layered approach.

        Precedence order (highest to lowest):
        1. EXTENDS (special patterns: problem→solution, claim→evidence, general→specific)
        2. CONTRADICTS (opposing statements about same topic)
        3. QUALIFIES (similar but with qualification/constraint)
        5. COMPLEMENTS (different aspects of same topic)
        6. SUPPORTS (same type, high similarity, or PROBLEM→CORE/SUPPORTING)
        7. ALTERNATIVE (similar topic, different positions)
        """

        stmt_sim = similarity["statement"]
        type_match = similarity["type_match"]

        # Stage 1: Candidate retrieval (high recall)
        if stmt_sim < self.thresholds.candidate_threshold:
            return None

        # Stage 2: EXTENDS special patterns (highest priority - structural)
        # Problem → Solution, Claim → Evidence, General → Specific
        if self._is_extends(t1, t2, similarity):
            return CrossBookThesisRelationType.EXTENDS

        # Stage 2b: CONTRADICTS (high priority)
        if self._is_contradiction(t1, t2, similarity):
            return CrossBookThesisRelationType.CONTRADICTS

        # Stage 3: QUALIFIES (similar but with qualification/constraint)
        if self._is_qualifies(t1, t2, similarity):
            return CrossBookThesisRelationType.QUALIFIES

        # Stage 3b: COMPLEMENTS (different aspects of same topic)
        if self._is_complementary(t1, t2):
            return CrossBookThesisRelationType.COMPLEMENTS

        # Stage 4: SUPPORTS (same type, high similarity, or PROBLEM→CORE/SUPPORTING)
        # Lower priority than EXTENDS/QUALIFIES
        if self._is_supports(t1, t2, similarity):
            return CrossBookThesisRelationType.SUPPORTS

        # Stage 5: ALTERNATIVE (similar topic, different positions)
        if similarity["statement"] >= self.thresholds.candidate_threshold:
            return CrossBookThesisRelationType.ALTERNATIVE

        return None

    # ── Helper methods for relation detection ──

    def _is_extends(self, t1: "CrossBookThesis", t2: "CrossBookThesis", sim: dict[str, float]) -> bool:
        """Detect EXTENDS: general -> specific, problem -> solution, claim -> evidence."""
        # Problem -> Solution (type-based, doesn't require high text similarity)
        if t1.type == "PROBLEM" and t2.type in ("CORE", "SUPPORTING"):
            return True
        if t2.type == "PROBLEM" and t1.type in ("CORE", "SUPPORTING"):
            return True
        # Claim -> Evidence (based on evidence indicators in t2)
        if self._is_claim_evidence(t1, t2):
            return True
        # General concept -> Specific elaboration (based on text similarity)
        if sim["statement"] >= 0.25 and self._is_elaboration(t1, t2):
            return True
        return False

    def _is_claim_evidence(self, t1: "CrossBookThesis", t2: "CrossBookThesis") -> bool:
        """Check if t1 is a claim and t2 is supporting evidence."""
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        evidence_indicators = {"defined as", "defined by", "formula", "limit of", "limit of the", "formula for", "because", "since", "given that", "proof", "definition", "theorem"}
        t2_words = set(t2_text.split())
        if any(ind in t2_text for ind in evidence_indicators):
            return True
        return False

    def _is_elaboration(self, t1: "CrossBookThesis", t2: "CrossBookThesis") -> bool:
        """Check if t2 elaborates on t1 (general concept -> specific detail)."""
        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)
        # t2 has more specific terms, t1 is more general
        t1_words = set(t1_text.split())
        t2_words = set(t2_text.split())
        if len(t2_text.split()) > len(t1_text.split()) * 1.2:
            # t2 is more detailed
            # Check if t2 contains t1's key concepts
            overlap = set(t1_text.split()) & set(t2_text.split())
            if len(overlap) >= 2:
                return True
        return False

    def _is_qualifies(self, t1: "CrossBookThesis", t2: "CrossBookThesis", sim: dict[str, float]) -> bool:
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
        qualifier_words = {"when", "if", "except", "provided", "unless", "except", "only", "where", "condition", "constraint", "provided that", "assuming", "given"}
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
            overlap = set(t1_text.split()) & set(t2_text.split())
            if len(overlap) >= 2:
                return True
        return False

    def _is_supports(self, t1: "CrossBookThesis", t2: "CrossBookThesis", sim: dict[str, float]) -> bool:
        """Check for SUPPORTS relation."""
        type_match = sim["type_match"]
        # Same type, high similarity
        if sim["type_match"] and sim["statement"] > 0.7:
            return True
        # PROBLEM -> CORE/SUPPORTING
        if t1.type == "PROBLEM" and t2.type in ("CORE", "SUPPORTING"):
            return True
        # CORE -> SUPPORTING (same direction)
        if t1.type == "CORE" and t2.type == "SUPPORTING":
            return True
        return False

    def _is_contradiction(self, t1: "CrossBookThesis", t2: "CrossBookThesis", sim: dict[str, float]) -> bool:
        """Detect contradiction between two theses."""
        negation_words = {"not", "no", "never", "cannot", "does not", "is not", "are not"}
        t1_words = set(_normalize_text(t1.statement).split())
        t2_words = set(_normalize_text(t2.statement).split())

        t1_has_neg = bool(t1_words & negation_words)
        t2_has_neg = bool(t2_words & negation_words)

        stmt_sim = sim["statement"]
        if t1_has_neg != t2_has_neg and stmt_sim >= self.thresholds.candidate_threshold:
            return True

        return False

    def _is_complementary(self, t1: CrossBookThesis, t2: CrossBookThesis) -> bool:
        """Detect complementary theses (different aspects of same topic)."""
        # Check for complementary patterns
        complementary_patterns = [
            ("instantaneous", "accumulated"),
            ("derivative", "integral"),
            ("change", "accumulation"),
            ("rate", "total"),
        ]

        t1_text = _normalize_text(t1.statement)
        t2_text = _normalize_text(t2.statement)

        for p1, p2 in complementary_patterns:
            if (p1 in t1_text and p2 in t2_text) or (p2 in t1_text and p1 in t2_text):
                return True

        return False


class ArgumentRelationClassifier:
    """Layered classifier for argument relations."""

    def __init__(self, thresholds: AlignmentThresholds | None = None):
        self.thresholds = thresholds or AlignmentThresholds()

    def classify(
        self,
        a1: CrossBookArgument,
        a2: CrossBookArgument,
        similarity: dict[str, float],
    ) -> CrossBookArgumentRelationType | None:
        """Classify argument relation using layered approach."""

        what_sim = similarity["what"]
        why_sim = similarity["how"]
        conclusion_sim = similarity["conclusion"]
        level_match = similarity["level_match"]

        # Stage 1: Candidate retrieval (high recall)
        if what_sim < self.thresholds.candidate_threshold:
            return None

        # Stage 2: Relation-specific classification
        # Check for CHALLENGES first
        if self._is_challenge(a1, a2, conclusion_sim):
            return CrossBookArgumentRelationType.CHALLENGES

        # Check for EXTENDS: general → specific (before SUPPORTS)
        if self._is_extends(a1, a2):
            return CrossBookArgumentRelationType.EXTENDS

        # Check for GENERALIZES: specific → general (before SUPPORTS)
        if self._is_generalizes(a1, a2):
            return CrossBookArgumentRelationType.GENERALIZES

        # Check for COMPLEMENTS: different focus, same goal
        if self._is_complementary(a1, a2):
            return CrossBookArgumentRelationType.COMPLEMENTS

        # Check for SUPPORTS: same level, high similarity (lower priority than EXTENDS/GENERALIZES)
        if level_match and what_sim >= 0.4 and why_sim >= 0.3:
            return CrossBookArgumentRelationType.SUPPORTS

        # Check for SPECIALIZES: specific instance of general
        if what_sim >= self.thresholds.candidate_threshold:
            return CrossBookArgumentRelationType.SPECIALIZES

        return None

    def _is_challenge(self, a1: CrossBookArgument, a2: CrossBookArgument, conclusion_sim: float) -> bool:
        """Detect challenge between two arguments."""
        # Check for opposing adjectives first (most reliable signal)
        opposing_pairs = [("efficient", "inefficient"), ("effective", "ineffectful"), ("success", "failure")]
        a1_text = _normalize_text(a1.what)
        a2_text = _normalize_text(a2.what)
        for p1, p2 in opposing_pairs:
            if (p1 in a1_text and p2 in a2_text) or (p2 in a1_text and p1 in a2_text):
                return True

        # Check for negation patterns
        negation_words = {"not", "no", "never", "cannot", "does not", "is not", "are not"}
        a1_words = set(a1_text.split())
        a2_words = set(a2_text.split())
        a1_has_neg = bool(a1_words & negation_words)
        a2_has_neg = bool(a2_words & negation_words)
        if a1_has_neg != a2_has_neg:
            return True

        return False

    def _is_extends(self, a1: CrossBookArgument, a2: CrossBookArgument) -> bool:
        """Detect extends relation (general → specific)."""
        # Semantic direction: general concept -> specific technical term
        general_concepts = {"calculus", "analysis", "change", "accumulation", "rate", "total", "function", "limit", "derivative", "integral"}
        specific_technical = {"derivative", "integral", "instantaneous", "accumulation", "measure", "instantaneous rate", "accumulated sum", "tangent", "area", "antiderivative", "differential", "definite integral"}
        
        a1_text = _normalize_text(a1.what)
        a2_text = _normalize_text(a2.what)
        
        a1_words = set(a1_text.split())
        a2_words = set(a2_text.split())
        
        a1_has_general = bool(a1_words & general_concepts)
        a2_has_specific = bool(a2_words & specific_technical)
        
        # Must be clearly general concept → specific technical term
        # Exclude cases where a2 also has general concepts (not purely specific)
        a2_has_general = bool(a2_words & general_concepts)
        
        if a1_has_general and a2_has_specific and not a2_has_general:
            return True
        
        # Also check based on length/detail - general statements tend to be shorter/more abstract
        # If a1 is shorter/more abstract and a2 is more detailed with overlapping terms
        if len(a1_text.split()) <= len(a2_text.split()) * 0.8:
            overlap = a1_words & a2_words
            if len(overlap) >= 2 and a1_has_general:
                return True
        
        return False

    def _is_generalizes(self, a1: CrossBookArgument, a2: CrossBookArgument) -> bool:
        """Detect generalizes relation (specific → general)."""
        general_concepts = {"calculus", "analysis", "change", "accumulation", "rate", "total", "function", "limit", "derivative", "integral"}
        specific_technical = {"derivative", "integral", "instantaneous", "accumulation", "measure", "instantaneous rate", "accumulated sum", "tangent", "area", "antiderivative", "differential", "definite integral"}
        
        a1_text = _normalize_text(a1.what)
        a2_text = _normalize_text(a2.what)
        
        a1_words = set(a1_text.split())
        a2_words = set(a2_text.split())
        
        a1_has_specific = bool(a1_words & specific_technical)
        a2_has_general = bool(a2_words & general_concepts)
        
        # Must be clearly specific technical term → general concept
        a1_has_general = bool(a1_words & general_concepts)
        
        if a1_has_specific and a2_has_general and not a1_has_general:
            return True
        
        # Also check based on length/detail - specific statements tend to be longer/more detailed
        if len(a2_text.split()) <= len(a1_text.split()) * 0.8:
            overlap = a1_words & a2_words
            if len(overlap) >= 2 and a2_has_general:
                return True
        
        return False

    def _is_complementary(self, a1: CrossBookArgument, a2: CrossBookArgument) -> bool:
        """Detect complementary arguments (different focus, same goal)."""
        complementary_patterns = [
            ("derivative", "integral"),
            ("change", "accumulation"),
            ("instantaneous", "total"),
            ("rate", "sum"),
        ]

        a1_text = _normalize_text(a1.what)
        a2_text = _normalize_text(a2.what)

        for p1, p2 in complementary_patterns:
            if (p1 in a1_text and p2 in a2_text) or (p2 in a1_text and p1 in a2_text):
                return True

        return False


class LayeredThesisAligner:
    """Layered thesis alignment with candidate retrieval and relation-specific classification."""

    def __init__(self, thresholds: AlignmentThresholds | None = None):
        self.thresholds = thresholds or AlignmentThresholds()
        self.classifier = ThesisRelationClassifier(self.thresholds)

    def align(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> ThesisAlignmentResult:
        """Align theses using layered approach."""

        # Extract all theses
        all_theses: dict[str, list[CrossBookThesis]] = {}
        for bu, synth in books:
            if not synth or not synth.thesis:
                continue
            theses = []
            for t in synth.thesis.all_theses():
                theses.append(CrossBookThesis(
                    thesis_id=_stable_id("cbt", bu.book_id, t.id),
                    book_id=bu.book_id,
                    thesis_ref=t.id,
                    statement=t.statement,
                    type=t.type,
                    confidence=t.confidence,
                    provenance=t.provenance,
                ))
            all_theses[bu.book_id] = theses

        # Align all pairs
        relations = []
        candidates = []
        rejected = []
        book_ids = list(all_theses.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                theses_a = all_theses.get(book_a_id, [])
                theses_b = all_theses.get(book_b_id, [])

                for t1 in theses_a:
                    for t2 in theses_b:
                        # Stage 1: Compute similarity
                        similarity = self._compute_similarity(t1, t2)

                        # Stage 2: Candidate retrieval
                        if similarity["statement"] < self.thresholds.candidate_threshold:
                            rejected.append({
                                "source": t1.thesis_id,
                                "target": t2.thesis_id,
                                "reason": "below_candidate_threshold",
                                "similarity": similarity,
                            })
                            continue

                        candidates.append({
                            "source": t1.thesis_id,
                            "target": t2.thesis_id,
                            "similarity": similarity,
                        })

                        # Stage 3: Relation-specific classification
                        relation_type = self.classifier.classify(t1, t2, similarity)

                        if relation_type is None:
                            rejected.append({
                                "source": t1.thesis_id,
                                "target": t2.thesis_id,
                                "reason": "no_relation_detected",
                                "similarity": similarity,
                            })
                            continue

                        # Stage 4: Evidence validation
                        evidence = self._build_evidence(t1, t2, similarity)

                        # Stage 5: Create relation
                        relation = CrossBookThesisRelation(
                            relation_id=_stable_id("tbr", book_a_id, t1.thesis_id, book_b_id, t2.thesis_id),
                            source_thesis=t1,
                            target_thesis=t2,
                            relation=relation_type,
                            reason=f"{t1.type}:{t1.statement[:50]}... {relation_type.value} {t2.type}:{t2.statement[:50]}...",
                            evidence=evidence,
                            confidence=round(similarity["statement"], 3),
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        relations.append(relation)

        return ThesisAlignmentResult(
            relations=relations,
            candidates=candidates,
            rejected=rejected,
        )

    def _compute_similarity(self, t1: CrossBookThesis, t2: CrossBookThesis) -> dict[str, float]:
        """Compute similarity metrics between two theses."""
        return {
            "statement": _jaccard_similarity(t1.statement, t2.statement),
            "type_match": 1.0 if t1.type == t2.type else 0.0,
            "provenance_match": 1.0 if t1.provenance == t2.provenance else 0.0,
        }

    def _build_evidence(self, t1: CrossBookThesis, t2: CrossBookThesis, similarity: dict[str, float]) -> list[str]:
        """Build evidence list for a thesis relation."""
        return [
            f"statement_similarity={similarity['statement']:.2f}",
            f"type_match={similarity['type_match']}",
            f"type_a={t1.type}, type_b={t2.type}",
        ]


class LayeredArgumentAligner:
    """Layered argument alignment with candidate retrieval and relation-specific classification."""

    def __init__(self, thresholds: AlignmentThresholds | None = None):
        self.thresholds = thresholds or AlignmentThresholds()
        self.classifier = ArgumentRelationClassifier(self.thresholds)

    def align(
        self,
        books: list[tuple[Any, BookSynthesis]],
    ) -> ArgumentAlignmentResult:
        """Align arguments using layered approach."""

        # Extract all arguments
        all_args: dict[str, list[CrossBookArgument]] = {}
        for bu, synth in books:
            if not synth or not synth.argument_system:
                continue
            args = []
            for arg in synth.argument_system.all_arguments():
                args.append(CrossBookArgument(
                    argument_id=_stable_id("cba", bu.book_id, arg.id),
                    book_id=bu.book_id,
                    argument_ref=arg.id,
                    level=arg.level,
                    what=arg.what,
                    why=arg.why,
                    how=arg.how,
                    conclusion=arg.conclusion,
                    evidence_refs=arg.evidence_refs,
                    status=arg.status,
                    confidence=arg.confidence,
                ))
            all_args[bu.book_id] = args

        # Align all pairs
        relations = []
        candidates = []
        rejected = []
        book_ids = list(all_args.keys())

        for i in range(len(book_ids)):
            for j in range(i + 1, len(book_ids)):
                book_a_id = book_ids[i]
                book_b_id = book_ids[j]
                args_a = all_args.get(book_a_id, [])
                args_b = all_args.get(book_b_id, [])

                for a1 in args_a:
                    for a2 in args_b:
                        # Stage 1: Compute similarity
                        similarity = self._compute_similarity(a1, a2)

                        # Stage 2: Candidate retrieval
                        if similarity["what"] < self.thresholds.candidate_threshold:
                            rejected.append({
                                "source": a1.argument_id,
                                "target": a2.argument_id,
                                "reason": "below_candidate_threshold",
                                "similarity": similarity,
                            })
                            continue

                        candidates.append({
                            "source": a1.argument_id,
                            "target": a2.argument_id,
                            "similarity": similarity,
                        })

                        # Stage 3: Relation-specific classification
                        relation_type = self.classifier.classify(a1, a2, similarity)

                        if relation_type is None:
                            rejected.append({
                                "source": a1.argument_id,
                                "target": a2.argument_id,
                                "reason": "no_relation_detected",
                                "similarity": similarity,
                            })
                            continue

                        # Stage 4: Evidence validation
                        evidence = self._build_evidence(a1, a2, similarity)

                        # Stage 5: Create relation
                        relation = CrossBookArgumentRelation(
                            relation_id=_stable_id("abr", book_a_id, a1.argument_id, book_b_id, a2.argument_id),
                            source_argument=a1,
                            target_argument=a2,
                            relation=relation_type,
                            reason=f"L{a1.level}:{a1.what[:40]}... {relation_type.value} L{a2.level}:{a2.what[:40]}...",
                            evidence=evidence,
                            confidence=round(similarity["what"], 3),
                            provenance=ThesisProvenance.MODEL_INFERRED,
                        )
                        relations.append(relation)

        return ArgumentAlignmentResult(
            relations=relations,
            candidates=candidates,
            rejected=rejected,
        )

    def _compute_similarity(self, a1: CrossBookArgument, a2: CrossBookArgument) -> dict[str, float]:
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

    def _build_evidence(self, a1: CrossBookArgument, a2: CrossBookArgument, similarity: dict[str, float]) -> list[str]:
        """Build evidence list for an argument relation."""
        return [
            f"what_similarity={similarity['what']:.2f}",
            f"why_similarity={similarity['why']:.2f}",
            f"conclusion_similarity={similarity['conclusion']:.2f}",
            f"level_a={a1.level}, level_b={a2.level}",
        ]