"""Understanding quality evaluation — spec §8, §9, §10, §11.

§8 is explicit that this is not about truth:

    评价不是事实真假, 而是 understanding completeness

so every dimension here measures whether a part of understanding is *present,
traceable and derived*, never whether a claim is correct. That separation is
the whole point of §10, and it is why this module never writes to
``book_understandings_v2.status`` or produces a verdict.

§10 requires the two to be separable in practice, so they are separate
objects: ``VerificationReport`` answers "did the pipeline do its job", and
``BUQualityReport`` answers "how much did it understand". A run can be
pipeline-PASS and quality-D, and both facts are reported.

§11 requires quality not to block publication, so quality never raises and
never sets a status. It only describes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

QualityLevel = Literal["A", "B", "C", "D"]

# A quality level is a band on the overall score, not a judgement about the
# book. The bands are named rather than numbered because a reader of the report
# should not have to look up what "quality 3" means.
LEVEL_BANDS: tuple[tuple[QualityLevel, float], ...] = (
    ("A", 0.80),
    ("B", 0.65),
    ("C", 0.45),
    ("D", 0.0),
)

LEVEL_MEANING = {
    "A": "comprehensive: structure, concept, mechanism, argument and boundary all present",
    "B": "substantial: the book's spine is understood, with identifiable gaps",
    "C": "partial: some structure or concept, but the argument is not reconstructed",
    "D": "minimal: the book was located but not meaningfully understood",
}


@dataclass
class QualityDimension:
    """One of Q1-Q7. ``detail`` is what made it this score."""

    key: str
    name: str
    score: float
    weight: float = 1.0
    detail: str = ""
    findings: list[str] = field(default_factory=list)

    @property
    def level(self) -> QualityLevel:
        return level_for(self.score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "score": round(self.score, 4),
            "weight": self.weight,
            "level": self.level,
            "detail": self.detail,
            "findings": self.findings[:8],
        }


@dataclass
class BUQualityReport:
    """§9 output."""

    book_id: str
    run_id: str = ""
    bu_id: str = ""
    structure_score: float = 0.0
    concept_score: float = 0.0
    mechanism_score: float = 0.0
    argument_score: float = 0.0
    integration_score: float = 0.0
    evidence_score: float = 0.0
    boundary_score: float = 0.0
    overall: float = 0.0
    quality_level: QualityLevel = "D"
    limitations: list[str] = field(default_factory=list)
    dimensions: list[QualityDimension] = field(default_factory=list)
    # §10: the pipeline verdict is carried, never computed here.
    pipeline_status: str = "UNKNOWN"
    chapter_count: int = 0
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "run_id": self.run_id,
            "bu_id": self.bu_id,
            "structure_score": round(self.structure_score, 4),
            "concept_score": round(self.concept_score, 4),
            "mechanism_score": round(self.mechanism_score, 4),
            "argument_score": round(self.argument_score, 4),
            "integration_score": round(self.integration_score, 4),
            "evidence_score": round(self.evidence_score, 4),
            "boundary_score": round(self.boundary_score, 4),
            "overall": round(self.overall, 4),
            "quality_level": self.quality_level,
            "quality_meaning": LEVEL_MEANING[self.quality_level],
            "pipeline_status": self.pipeline_status,
            "chapter_count": self.chapter_count,
            "evidence_count": self.evidence_count,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "limitations": self.limitations[:20],
        }

    def render(self) -> str:
        lines = [
            "=" * 74,
            "BU2 UNDERSTANDING QUALITY REPORT",
            f"book_id={self.book_id}  run_id={self.run_id}",
            f"pipeline status: {self.pipeline_status}   (independent of quality)",
            "=" * 74,
            "",
            f"{'DIMENSION':<16}{'SCORE':>7}  {'LV':<3} DETAIL",
            "-" * 74,
        ]
        for d in self.dimensions:
            lines.append(f"{d.name:<16}{d.score:>7.2f}  {d.level:<3} {d.detail[:44]}")
        lines += [
            "-" * 74,
            f"{'OVERALL':<16}{self.overall:>7.2f}  {self.quality_level:<3} "
            f"{LEVEL_MEANING[self.quality_level]}",
            "",
            "REPORTED LIMITATIONS (what this understanding does not know):",
        ]
        lines += [f"  - {lim}" for lim in self.limitations] or ["  (none recorded)"]
        if self.evidence_count == 0:
            lines += ["", "No understanding here is traceable to source text."]
        return "\n".join(lines)


def level_for(score: float) -> QualityLevel:
    for level, floor in LEVEL_BANDS:
        if score >= floor:
            return level
    return "D"


class BUQualityEvaluator:
    """§8.1: evaluate a BookUnderstandingV2.

    Takes the persisted BU plus the run's own chapters and evidence, because a
    dimension like evidence completeness is a property of the run rather than of
    the BU row: the BU stores counts, not the artifacts themselves.
    """

    def evaluate(
        self,
        bu: Any,
        *,
        chapters: list[Any] | None = None,
        evidence: list[Any] | None = None,
        pipeline_status: str = "UNKNOWN",
        structure: dict[str, Any] | None = None,
    ) -> BUQualityReport:
        chapters = chapters or []
        evidence = evidence or []
        rep = BUQualityReport(
            book_id=getattr(bu, "book_id", ""),
            run_id=getattr(bu, "run_id", ""),
            bu_id=getattr(bu, "id", ""),
            pipeline_status=pipeline_status,
            chapter_count=len(chapters),
            evidence_count=len(evidence),
        )

        rep.dimensions = [
            self._q1_structure(bu, chapters, structure),
            self._q2_concept(bu, chapters),
            self._q3_mechanism(bu, chapters),
            self._q4_argument(bu, chapters, evidence),
            self._q5_integration(bu, chapters),
            self._q6_evidence(bu, chapters, evidence),
            self._q7_boundary(bu, chapters),
        ]
        by_key = {d.key: d for d in rep.dimensions}
        rep.structure_score = by_key["Q1"].score
        rep.concept_score = by_key["Q2"].score
        rep.mechanism_score = by_key["Q3"].score
        rep.argument_score = by_key["Q4"].score
        rep.integration_score = by_key["Q5"].score
        rep.evidence_score = by_key["Q6"].score
        rep.boundary_score = by_key["Q7"].score
        rep.overall = round(sum(d.score * d.weight for d in rep.dimensions) / sum(d.weight for d in rep.dimensions), 4)
        rep.quality_level = level_for(rep.overall)
        rep.limitations = [f for d in rep.dimensions for f in d.findings if f]
        return rep

    # ── Q1 structure ───────────────────────────────────────────────────────

    def _q1_structure(self, bu, chapters, structure) -> QualityDimension:
        d = QualityDimension("Q1", "Structure", 0.0, detail="")
        if structure:
            # The denominator is what the parser index declared; the numerator is
            # numbered chapters only. Counting back matter in the numerator
            # produces "18 of 16 chapters", which reads as an error in a report
            # and would make a perfect extraction look like a 112% one.
            expected = int(structure.get("expected_chapters") or 0) or len(chapters)
            located = len(chapters)
            ratio = min(1.0, located / expected) if expected else (1.0 if located else 0.0)
            located_label = expected
            conf = float(structure.get("confidence_mean") or 0.0)
            d.score = round(min(1.0, 0.6 * ratio + 0.4 * conf), 4)
            d.detail = (
                f"{min(located, located_label)} of {located_label} chapters located, "
                f"mean confidence {conf:.2f}"
            )
            if ratio < 0.95:
                d.findings.append(f"structure: only {ratio:.0%} of declared chapters located")
            if conf < 0.85:
                d.findings.append(f"structure: mean boundary confidence {conf:.2f} is low")
        elif chapters:
            d.score = 0.6
            d.detail = f"{len(chapters)} chapters, no structure metadata"
            d.findings.append("structure: extraction metadata unavailable, quality not assessed")
        else:
            d.score = 0.0
            d.detail = "no chapters"
            d.findings.append("structure: the book yielded no chapters")
        return d

    # ── Q2 concept ─────────────────────────────────────────────────────────

    def _q2_concept(self, bu, chapters) -> QualityDimension:
        d = QualityDimension("Q2", "Concept", 0.0)
        system = getattr(bu, "concept_system", {}) or {}
        concepts = system.get("concepts", {}) if isinstance(system, dict) else {}
        n_concepts = len(concepts)
        introduced = sum(len(c.concepts_introduced_refs) for c in chapters)
        redefined = sum(len(c.concepts_redefined_refs) for c in chapters)
        evolution = len(getattr(bu, "concept_evolution", []) or [])

        # Three things must hold: concepts were extracted, they persist to book
        # level, and at least one was seen again later.
        extraction = min(1.0, introduced / 20.0)
        persistence = min(1.0, n_concepts / 10.0)
        evolution_score = min(1.0, evolution / 8.0)
        d.score = round(0.4 * extraction + 0.35 * persistence + 0.25 * evolution_score, 4)
        d.detail = f"{n_concepts} book concepts, {introduced} introduced, {evolution} evolution steps"
        if introduced == 0:
            d.findings.append("concept: no concepts extracted from any chapter")
        if evolution == 0 and len(chapters) > 1:
            d.findings.append("concept: no concept was seen again, so no evolution was observed")
        if redefined == 0 and len(chapters) > 1:
            d.findings.append("concept: no chapter recorded redefinition of an earlier concept")
        return d

    # ── Q3 mechanism ───────────────────────────────────────────────────────

    def _q3_mechanism(self, bu, chapters) -> QualityDimension:
        d = QualityDimension("Q3", "Mechanism", 0.0)
        system = getattr(bu, "concept_system", {}) or {}
        book_mech = system.get("mechanisms", []) if isinstance(system, dict) else []
        chapter_mech = sum(len(c.mechanisms_refs) for c in chapters)
        with_mech = sum(1 for c in chapters if c.mechanisms_refs)

        coverage = with_mech / len(chapters) if chapters else 0.0
        volume = min(1.0, chapter_mech / 15.0)
        carried = min(1.0, len(book_mech) / 3.0)
        d.score = round(0.45 * coverage + 0.3 * volume + 0.25 * carried, 4)
        d.detail = f"{chapter_mech} chapter mechanisms, {len(book_mech)} carried to book level"
        if coverage < 0.5:
            d.findings.append(
                f"mechanism: only {coverage:.0%} of chapters recorded a causal explanation"
            )
        if not book_mech:
            d.findings.append("mechanism: nothing was carried to whole-book level")
        return d

    # ── Q4 argument ────────────────────────────────────────────────────────

    def _q4_argument(self, bu, chapters, evidence) -> QualityDimension:
        d = QualityDimension("Q4", "Argument", 0.0)
        arch = getattr(bu, "argument_architecture", None)
        roots = len(getattr(arch, "root_arguments", []) or [])
        supporting = len(getattr(arch, "supporting_arguments", []) or [])
        claims = sum(len(c.evidence_program) for c in chapters)
        thesis = len(getattr(bu, "central_theses", []) or [])

        thesis_score = min(1.0, thesis / 2.0) if thesis else 0.0
        support_score = min(1.0, supporting / 3.0)
        claim_score = min(1.0, claims / 8.0)
        d.score = round(0.3 * thesis_score + 0.25 * support_score + 0.45 * claim_score, 4)
        d.detail = f"{roots} root arguments, {supporting} supporting, {claims} evidenced claims"
        if thesis == 0:
            d.findings.append("argument: the book has no central thesis recorded")
        if supporting == 0:
            d.findings.append("argument: central claims have no supporting structure")
        if claims == 0:
            d.findings.append("argument: no claim was linked to evidence")
        return d

    # ── Q5 integration — §10.4 in evaluative form ──────────────────────────

    def _q5_integration(self, bu, chapters) -> QualityDimension:
        """Distinguishes a whole-book model from a chapter collection.

        The test is structural, not stylistic: a concatenation has N theses for
        N chapters and no cross-chapter relation. A whole-book model has few
        book-level claims and some relation that spans chapters.
        """
        d = QualityDimension("Q5", "Integration", 0.0)
        graph = getattr(bu, "chapter_dependency_graph", None)
        edges = len(getattr(graph, "dependencies", []) or [])
        arc_steps = len(getattr(getattr(bu, "discourse_arc", None), "steps", []) or [])
        evolution = len(getattr(bu, "concept_evolution", []) or [])
        book_theses = len(getattr(bu, "central_theses", []) or [])
        questions = len(getattr(bu, "governing_questions", []) or [])
        n = len(chapters)

        cross = min(1.0, edges / max(1.0, n - 1))          # relations spanning chapters
        arc = min(1.0, arc_steps / max(1.0, n))            # a shape for the whole book
        evo = min(1.0, evolution / 8.0)                     # something changed over time
        framing = min(1.0, (book_theses + questions) / 3.0)  # book-level, not chapter-level
        d.score = round(0.3 * cross + 0.2 * arc + 0.2 * evo + 0.3 * framing, 4)
        d.detail = f"{edges} cross-chapter edges, {arc_steps} arc steps, {book_theses} book theses"
        if n > 1 and edges == 0:
            d.findings.append(
                "integration: chapters record no relation to one another, so this reads "
                "as a collection rather than a model of the whole book"
            )
        if book_theses == 0 and questions == 0:
            d.findings.append("integration: no book-level framing was produced")
        return d

    # ── Q6 evidence ─────────────────────────────────────────────────────────

    def _q6_evidence(self, bu, chapters, evidence) -> QualityDimension:
        """Traceability, not correctness. §8 names this explicitly."""
        d = QualityDimension("Q6", "Evidence", 0.0)
        n_ev = len(evidence)
        located = sum(1 for e in evidence if getattr(e, "locator", ""))
        quotes = sum(1 for e in evidence if getattr(e, "quote", ""))
        programs = sum(len(c.evidence_program) for c in chapters)

        if n_ev == 0:
            d.score = 0.0
            d.detail = "no evidence recorded"
            d.findings.append("evidence: nothing in this understanding is traceable to source text")
            return d
        locator_rate = located / n_ev
        quote_rate = quotes / n_ev
        program_rate = min(1.0, programs / max(1, n_ev))
        d.score = round(0.4 * locator_rate + 0.3 * quote_rate + 0.3 * program_rate, 4)
        d.detail = f"{n_ev} artifacts, {locator_rate:.0%} with a locator"
        if locator_rate < 1.0:
            d.findings.append(f"evidence: {n_ev - located} artifacts carry no source location")
        if programs < n_ev:
            d.findings.append(
                "evidence: not every artifact is referenced by a chapter's evidence program"
            )
        return d

    # ── Q7 boundary ─────────────────────────────────────────────────────────

    def _q7_boundary(self, bu, chapters) -> QualityDimension:
        """§9: whether the understanding knows what it does not know."""
        d = QualityDimension("Q7", "Boundary", 0.0)
        nk = getattr(bu, "negative_knowledge", None)
        limitations = len(getattr(nk, "limitations", []) or [])
        problems = len(getattr(nk, "open_problems", []) or [])
        conflicts = len(getattr(nk, "unresolved_conflicts", []) or [])
        unresolved = len(getattr(bu, "unresolved_questions", []) or [])
        qualified = sum(1 for c in chapters if c.qualifications or c.assumptions)
        coverage = float(getattr(bu, "coverage_score", 0.0) or 0.0)
        failed = sum(1 for c in chapters if c.primary_role == "UNDERSTANDING_FAILED")

        stated = min(1.0, (limitations + problems) / 4.0)
        open_q = min(1.0, (unresolved + conflicts) / 4.0)
        per_chapter = qualified / len(chapters) if chapters else 0.0
        honesty = 1.0 if failed == 0 else max(0.0, 1.0 - failed / max(1, len(chapters)))
        d.score = round(0.3 * stated + 0.25 * open_q + 0.25 * per_chapter + 0.2 * honesty, 4)
        d.detail = (
            f"{limitations} limitations, {problems} open problems, "
            f"{unresolved} unresolved questions, coverage {coverage:.0%}"
        )
        if limitations + problems == 0:
            d.findings.append("boundary: the understanding states no limits on itself")
        if unresolved == 0:
            d.findings.append("boundary: no unresolved question is recorded")
        if failed:
            d.findings.append(
                f"boundary: {failed} chapter(s) could not be understood and are recorded as such"
            )
        return d


def quality_context_lines(report: BUQualityReport) -> list[str]:
    """§12: the quality lines an expression is allowed to carry.

    Deliberately phrased as understanding confidence, never as a truth score.
    §12 forbids disguising this as a book-truth score, and "the book's
    statements were checked" would be exactly that disguise.
    """
    by = {d.key: d for d in report.dimensions}
    return [
        f"Structure (Q1): {by['Q1'].level} — {by['Q1'].detail}",
        f"Evidence (Q6): {by['Q6'].level} — {by['Q6'].detail}",
        f"Mechanism (Q3): {by['Q3'].level} — {by['Q3'].detail}",
        f"Integration (Q5): {by['Q5'].level} — {by['Q5'].detail}",
        f"Boundary (Q7): {by['Q7'].level} — {by['Q7'].detail}",
        f"Overall understanding confidence: {report.quality_level} "
        f"({report.overall:.2f}) — {LEVEL_MEANING[report.quality_level]}",
        f"Pipeline status: {report.pipeline_status} "
        f"(independent of understanding quality)",
    ]