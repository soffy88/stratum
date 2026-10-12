"""Deep understanding quality — spec §10.

P11 measured seven dimensions and its lowest, Q5 Integration, was 0.72. That
number was the honest report of the gap P12 exists to close: chapters were
understood, the relations between them were barely there.

Four more dimensions, each asking a question the first seven cannot:

  Q8  Reasoning            do claims have a reasoning chain, or are they asserted?
  Q9  Concept Evolution    are concepts introduced, changed and connected?
  Q10 Cross-Chapter        do the chapters form a graph, or isolated summaries?
  Q11 Author Model         is there an answer to "why is the book organised
                           this way?"

Same discipline as P11 and for the same reason: these measure completeness, not
truth, and none of them can block publication. A shallow but correctly produced
understanding still verifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stratum.services.bu_v2_argument_analyzer import ArgumentAnalysis
from stratum.services.bu_v2_concept_evolution import EvolutionResult
from stratum.services.bu_v2_quality_evaluator import (
    LEVEL_MEANING,
    QualityDimension,
    QualityLevel,
    level_for,
)
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class DeepQualityReport:
    """§10's Q8-Q11 plus the overall picture they belong to."""

    book_id: str
    run_id: str = ""
    reasoning_score: float = 0.0
    evolution_score: float = 0.0
    coherence_score: float = 0.0
    author_model_score: float = 0.0
    overall: float = 0.0
    quality_level: QualityLevel = "D"
    deep_level: QualityLevel = "D"
    pipeline_status: str = "UNKNOWN"
    limitations: list[str] = field(default_factory=list)
    dimensions: list[QualityDimension] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "run_id": self.run_id,
            "reasoning_score": round(self.reasoning_score, 4),
            "evolution_score": round(self.evolution_score, 4),
            "coherence_score": round(self.coherence_score, 4),
            "author_model_score": round(self.author_model_score, 4),
            "overall": round(self.overall, 4),
            "quality_level": self.quality_level,
            "deep_level": self.deep_level,
            "deep_meaning": LEVEL_MEANING[self.deep_level],
            "pipeline_status": self.pipeline_status,
            "counts": self.counts,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "limitations": self.limitations[:24],
        }

    def render(self) -> str:
        lines = [
            "=" * 74,
            "BU2 DEEP UNDERSTANDING QUALITY (P12 Q8-Q11)",
            f"book_id={self.book_id}  run_id={self.run_id}",
            f"pipeline status: {self.pipeline_status}   (independent of quality)",
            "=" * 74,
            "",
            f"{'DIMENSION':<22}{'SCORE':>7}  {'LV':<3} DETAIL",
            "-" * 74,
        ]
        for d in self.dimensions:
            lines.append(f"{d.name:<22}{d.score:>7.2f}  {d.level:<3} {d.detail[:38]}")
        lines += [
            "-" * 74,
            f"{'DEEP OVERALL':<22}{self.overall:>7.2f}  {self.deep_level:<3} "
            f"{LEVEL_MEANING[self.deep_level]}",
        ]
        if self.limitations:
            lines += ["", "WHAT THIS UNDERSTANDING DOES NOT SHOW:"]
            lines += [f"  - {l[:94]}" for l in self.limitations]
        return "\n".join(lines)


class DeepQualityEvaluator:
    """§10: Q8-Q11, computed from the P12 graph artefacts."""

    def evaluate(
        self,
        *,
        book_id: str,
        run_id: str,
        graph: BookReasoningGraph | None,
        evolution: EvolutionResult | None,
        argument: ArgumentAnalysis | None,
        chapter_count: int,
        pipeline_status: str = "UNKNOWN",
    ) -> DeepQualityReport:
        rep = DeepQualityReport(book_id=book_id, run_id=run_id, pipeline_status=pipeline_status)
        rep.counts = {
            "chapters": chapter_count,
            "nodes": len(graph.nodes) if graph else 0,
            "edges": len(graph.edges) if graph else 0,
            "cross_chapter_edges": len(graph.cross_chapter_edges()) if graph else 0,
            "trajectories": len(evolution.trajectories) if evolution else 0,
            "evolving_concepts": evolution.evolving_count if evolution else 0,
            "argument_chains": len(argument.chains) if argument else 0,
            "complete_chains": argument.complete_chains if argument else 0,
            "unresolved": (
                (len(graph.unresolved) if graph else 0)
                + (len(evolution.unresolved) if evolution else 0)
                + (len(argument.unresolved) if argument else 0)
            ),
        }

        rep.dimensions = [
            self._q8_reasoning(argument),
            self._q9_evolution(evolution),
            self._q10_coherence(graph, chapter_count),
            self._q11_author_model(graph, argument, chapter_count),
        ]
        by = {d.key: d for d in rep.dimensions}
        rep.reasoning_score = by["Q8"].score
        rep.evolution_score = by["Q9"].score
        rep.coherence_score = by["Q10"].score
        rep.author_model_score = by["Q11"].score
        rep.overall = round(sum(d.score for d in rep.dimensions) / len(rep.dimensions), 4)
        rep.deep_level = level_for(rep.overall)
        rep.quality_level = rep.deep_level
        rep.limitations = [f for d in rep.dimensions for f in d.findings if f]
        return rep

    # ── Q8 reasoning ───────────────────────────────────────────────────────

    def _q8_reasoning(self, argument: ArgumentAnalysis | None) -> QualityDimension:
        d = QualityDimension("Q8", "Q8 Reasoning", 0.0)
        if argument is None or not argument.chains:
            d.score = 0.0
            d.detail = "no argument chains"
            d.findings.append("reasoning: the author advances nothing that was recorded as a chain")
            return d
        complete = argument.complete_chains
        total = len(argument.chains)
        with_evidence = sum(1 for c in argument.chains if c.evidence)
        with_reasoning = sum(1 for c in argument.chains if c.reasoning)
        with_conclusion = sum(1 for c in argument.chains if c.conclusion)

        d.score = round(
            0.4 * (complete / total)
            + 0.25 * (with_evidence / total)
            + 0.2 * (with_reasoning / total)
            + 0.15 * (with_conclusion / total),
            4,
        )
        d.detail = f"{complete} of {total} chains complete"
        if complete == 0:
            d.findings.append("reasoning: no chain has both evidence and a conclusion")
        elif complete < total / 2:
            d.findings.append(
                f"reasoning: only {complete} of {total} chains reach a conclusion"
            )
        return d

    # ── Q9 concept evolution ───────────────────────────────────────────────

    def _q9_evolution(self, evolution: EvolutionResult | None) -> QualityDimension:
        d = QualityDimension("Q9", "Q9 Concept Evolution", 0.0)
        if evolution is None or not evolution.trajectories:
            d.score = 0.0
            d.detail = "no concept trajectories"
            d.findings.append("evolution: no concept was tracked across the book")
            return d
        total = len(evolution.trajectories)
        evolving = evolution.evolving_count
        with_ref = sum(1 for t in evolution.trajectories if "REFINEMENT" in t.kind_counts())
        with_exp = sum(1 for t in evolution.trajectories if "EXPANSION" in t.kind_counts())
        with_con = sum(1 for t in evolution.trajectories if "CONNECTION" in t.kind_counts())

        d.score = round(
            0.35 * (evolving / total)
            + 0.25 * min(1.0, with_ref / 10.0)
            + 0.2 * min(1.0, with_exp / 5.0)
            + 0.2 * min(1.0, with_con / 5.0),
            4,
        )
        d.detail = f"{evolving} of {total} concepts introduced then refined"
        if evolving == 0:
            d.findings.append("evolution: no concept is both introduced and later refined")
        if with_ref == 0:
            d.findings.append("evolution: no concept definition was recorded as changing")
        return d

    # ── Q10 cross-chapter coherence ────────────────────────────────────────

    def _q10_coherence(self, graph: BookReasoningGraph | None, chapter_count: int) -> QualityDimension:
        """§10: are the chapters a graph, or isolated summaries?

        The decisive number is how many chapters participate in a relation. A
        book where 2 of 16 chapters are connected is a collection with two ties,
        and the score says so.
        """
        d = QualityDimension("Q10", "Q10 Cross-Chapter", 0.0)
        if graph is None or not graph.edges or chapter_count < 2:
            d.score = 0.0
            d.detail = "no cross-chapter relation"
            d.findings.append("coherence: chapters are isolated; no relation connects them")
            return d

        cross = graph.cross_chapter_edges()
        # Document order connects any book with two chapters, so scoring on it
        # would make Q10 pass on a shelf of unrelated essays. Only asserted
        # relations — the author's own references, or a concept the book
        # demonstrably reuses — count towards density and volume. The adjacency
        # fallback is still reported, so nothing is hidden.
        asserted = [e for e in cross if e.status == "asserted"]
        fallback = len(cross) - len(asserted)
        participating = {e.source_node_id for e in asserted} | {
            e.target_node_id for e in asserted
        }
        density = len(participating) / chapter_count
        direct = graph.direct_edge_ratio
        volume = min(1.0, len(asserted) / max(1.0, chapter_count / 2))

        d.score = round(0.45 * density + 0.25 * direct + 0.3 * volume, 4)
        d.detail = (
            f"{len(participating)} of {chapter_count} chapters connected, "
            f"{len(asserted)} asserted relations, {direct:.0%} directly evidenced"
            + (f", {fallback} from document order alone" if fallback else "")
        )
        if not asserted:
            d.findings.append(
                "coherence: every relation is document order; the author states no "
                "dependence between chapters"
            )
        if density < 0.5:
            d.findings.append(
                f"coherence: only {len(participating)} of {chapter_count} chapters take part "
                "in any asserted cross-chapter relation"
            )
        if direct < 0.5:
            d.findings.append(
                f"coherence: {direct:.0%} of relations are directly evidenced; the rest are "
                "derived from concept recurrence or document order"
            )
        return d

    # ── Q11 author model ───────────────────────────────────────────────────

    def _q11_author_model(
        self, graph: BookReasoningGraph | None, argument: ArgumentAnalysis | None, chapter_count: int
    ) -> QualityDimension:
        """Why is the book organised this way?

        Answerable only if the graph explains the ordering: forward references
        (a chapter pointing at a later one) are evidence the author planned a
        route, and backward-only references suggest a merely cumulative text.
        """
        d = QualityDimension("Q11", "Q11 Author Model", 0.0)
        if graph is None or not graph.edges:
            d.score = 0.0
            d.detail = "no organisation evidence"
            d.findings.append("author model: nothing indicates why the book is ordered as it is")
            return d

        forward = backward = 0
        for e in graph.cross_chapter_edges():
            s = graph.nodes.get(e.source_node_id)
            t = graph.nodes.get(e.target_node_id)
            if not (s and t):
                continue
            if _num(s.chapter_id) < _num(t.chapter_id):
                forward += 1
            else:
                backward += 1
        total = forward + backward
        planning = forward / total if total else 0.0

        chains = len(argument.chains) if argument else 0
        chain_score = min(1.0, chains / max(1.0, chapter_count / 2))
        stated = sum(1 for e in graph.cross_chapter_edges() if e.is_direct)
        stated_score = min(1.0, stated / max(1.0, chapter_count / 2))

        d.score = round(0.4 * planning + 0.3 * stated_score + 0.3 * chain_score, 4)
        d.detail = f"{forward} forward and {backward} backward author references"
        if total == 0:
            d.findings.append("author model: no author-stated relation between chapters")
        elif planning < 0.2 and forward > 0:
            d.findings.append(
                f"author model: {backward} of {total} references point backwards; the text "
                "reads as cumulative rather than planned"
            )
        return d


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0


# ═══════════════════════════════════════════════════════════════════════════════
# P13 Quality Evaluators (Q12-Q18)
# ═══════════════════════════════════════════════════════════════════════════════

from stratum.knowledge.bu_v2_models import (
    BookSynthesis,
    ContradictionType,
    EvidenceStrengthP13,
    ThesisProvenance,
)
from stratum.services.bu_v2_quality_evaluator import QualityDimension, QualityLevel, level_for


@dataclass
class P13QualityReport:
    """P13 Q12-Q18 quality report."""
    book_id: str
    run_id: str = ""
    thesis_grounding: float = 0.0
    concept_system_coherence: float = 0.0
    argument_completeness: float = 0.0
    mechanism_grounding: float = 0.0
    evidence_coverage: float = 0.0
    contradiction_integrity: float = 0.0
    synthesis_traceability: float = 0.0
    overall: float = 0.0
    quality_level: QualityLevel = "D"
    dimensions: list[QualityDimension] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class P13QualityEvaluator:
    """P13: Q12-Q18 quality evaluation from BookSynthesis."""

    def evaluate(
        self,
        *,
        book_id: str,
        run_id: str,
        synthesis: BookSynthesis | None,
        pipeline_status: str = "UNKNOWN",
    ) -> P13QualityReport:
        rep = P13QualityReport(book_id=book_id, run_id=run_id)

        if synthesis is None:
            rep.dimensions = [
                QualityDimension("Q12", "Q12 Thesis Grounding", 0.0, detail="No synthesis produced"),
                QualityDimension("Q13", "Q13 Concept-System Coherence", 0.0, detail="No synthesis produced"),
                QualityDimension("Q14", "Q14 Argument Completeness", 0.0, detail="No synthesis produced"),
                QualityDimension("Q15", "Q15 Mechanism Grounding", 0.0, detail="No synthesis produced"),
                QualityDimension("Q16", "Q16 Evidence Coverage", 0.0, detail="No synthesis produced"),
                QualityDimension("Q17", "Q17 Contradiction Integrity", 0.0, detail="No synthesis produced"),
                QualityDimension("Q18", "Q18 Synthesis Traceability", 0.0, detail="No synthesis produced"),
            ]
            for d in rep.dimensions:
                d.findings.append(f"{d.key}: no synthesis artefact available")
            rep.overall = 0.0
            rep.quality_level = "D"
            return rep

        rep.dimensions = [
            self._q12_thesis_grounding(synthesis),
            self._q13_concept_coherence(synthesis),
            self._q14_argument_completeness(synthesis),
            self._q15_mechanism_grounding(synthesis),
            self._q16_evidence_coverage(synthesis),
            self._q17_contradiction_integrity(synthesis),
            self._q18_synthesis_traceability(synthesis),
        ]
        by_key = {d.key: d for d in rep.dimensions}
        rep.thesis_grounding = by_key["Q12"].score
        rep.concept_system_coherence = by_key["Q13"].score
        rep.argument_completeness = by_key["Q14"].score
        rep.mechanism_grounding = by_key["Q15"].score
        rep.evidence_coverage = by_key["Q16"].score
        rep.contradiction_integrity = by_key["Q17"].score
        rep.synthesis_traceability = by_key["Q18"].score
        rep.overall = round(sum(d.score for d in rep.dimensions) / len(rep.dimensions), 4)
        rep.quality_level = level_for(rep.overall)
        rep.limitations = [f for d in rep.dimensions for f in d.findings if f]
        return rep

    # Q12: Thesis Grounding
    def _q12_thesis_grounding(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q12", "Q12 Thesis Grounding", 0.0)
        thesis = synthesis.thesis

        if not thesis.core_thesis:
            d.score = 0.0
            d.detail = "No core thesis extracted"
            d.findings.append("thesis: no core thesis identified")
            return d

        core = thesis.core_thesis
        supporting = thesis.supporting_theses

        # Traceability: core thesis must have evidence and source locations
        has_evidence = len(core.evidence_refs) > 0
        has_locations = len(core.source_locations) > 0
        provenance_bonus = 1.0 if core.provenance == ThesisProvenance.AUTHOR_ASSERTED else (0.5 if core.provenance == ThesisProvenance.STRUCTURALLY_DERIVED else 0.0)

        evidence_score = 1.0 if has_evidence else 0.0
        location_score = 1.0 if has_locations else 0.0
        support_score = min(1.0, len(supporting) / 3.0)

        d.score = round(0.4 * evidence_score + 0.3 * location_score + 0.2 * support_score + 0.1 * provenance_bonus, 4)
        d.detail = f"Core thesis: {'grounded' if has_evidence else 'no evidence'}, {len(supporting)} supporting, provenance={core.provenance.value}"
        if not has_evidence:
            d.findings.append("thesis: core thesis lacks evidence references")
        if not has_locations:
            d.findings.append("thesis: core thesis lacks source locations")
        if core.provenance == ThesisProvenance.MODEL_INFERRED:
            d.findings.append("thesis: core thesis is model-inferred, not author-asserted")
        return d

    # Q13: Concept-System Coherence
    def _q13_concept_coherence(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q13", "Q13 Concept-System Coherence", 0.0)
        cs = synthesis.concept_system
        all_concepts = cs.all_concepts()

        if not all_concepts:
            d.score = 0.0
            d.detail = "No concepts in system"
            d.findings.append("concepts: concept system is empty")
            return d

        # Coherence checks
        has_foundational = len(cs.foundational) > 0
        has_core = len(cs.core) > 0
        has_dependencies = sum(1 for c in all_concepts if c.prerequisites) > 0
        has_applications = sum(1 for c in all_concepts if c.applied_in) > 0
        traceable = sum(1 for c in all_concepts if c.chapter_refs) / len(all_concepts)

        d.score = round(0.25 * has_foundational + 0.25 * has_core + 0.2 * has_dependencies + 0.15 * has_applications + 0.15 * traceable, 4)
        d.detail = f"{len(all_concepts)} concepts: {len(cs.foundational)} foundational, {len(cs.core)} core, {len(cs.derived)} derived, {len(cs.bridging)} bridging, {len(cs.application)} application"
        if not has_foundational:
            d.findings.append("concepts: no foundational concepts identified")
        if not has_core:
            d.findings.append("concepts: no core concepts identified")
        if traceable < 0.8:
            d.findings.append(f"concepts: only {traceable:.0%} traceable to chapters")
        return d

    # Q14: Argument Completeness
    def _q14_argument_completeness(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q14", "Q14 Argument Completeness", 0.0)
        args = synthesis.argument_system

        thesis_args = len(args.thesis_arguments)
        major_args = len(args.major_arguments)
        sub_args = len(args.sub_arguments)
        total_args = thesis_args + major_args + sub_args

        if total_args < 5:
            d.score = round(total_args / 5.0 * 0.6, 4)
            d.detail = f"Only {total_args} argument chains (need ≥5)"
            d.findings.append(f"arguments: only {total_args} chains, below threshold of 5")
            return d

        complete_chains = sum(1 for a in args.thesis_arguments if a.status.value == "SUPPORTED")
        complete_chains += sum(1 for a in args.major_arguments if a.status.value == "SUPPORTED")
        evidenced = sum(1 for a in args.all_arguments() if a.evidence_refs)
        with_conclusion = sum(1 for a in args.all_arguments() if a.conclusion)

        d.score = round(0.4 * (complete_chains / total_args) + 0.3 * (evidenced / total_args) + 0.3 * (with_conclusion / total_args), 4)
        d.detail = f"{total_args} chains ({thesis_args} thesis, {major_args} major, {sub_args} sub), {complete_chains} supported, {evidenced} evidenced, {with_conclusion} concluded"
        if complete_chains < total_args * 0.5:
            d.findings.append(f"arguments: only {complete_chains}/{total_args} chains fully supported")
        return d

    # Q15: Mechanism Grounding
    def _q15_mechanism_grounding(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q15", "Q15 Mechanism Grounding", 0.0)
        mechs = synthesis.mechanism_system.mechanisms

        if not mechs:
            d.score = 0.0
            d.detail = "No mechanisms extracted"
            d.findings.append("mechanisms: no mechanisms identified in the book")
            return d

        grounded = sum(1 for m in mechs if m.evidence_refs)
        author_asserted = sum(1 for m in mechs if m.provenance == ThesisProvenance.AUTHOR_ASSERTED)
        with_trigger = sum(1 for m in mechs if m.trigger)
        with_outcome = sum(1 for m in mechs if m.outcome)

        n = len(mechs)
        d.score = round(0.3 * (grounded / n) + 0.3 * (author_asserted / n) + 0.2 * (with_trigger / n) + 0.2 * (with_outcome / n), 4)
        d.detail = f"{n} mechanisms: {grounded} grounded, {author_asserted} author-asserted"
        if grounded < n * 0.5:
            d.findings.append(f"mechanisms: only {grounded}/{n} have evidence references")
        if n < 3:
            d.findings.append(f"mechanisms: only {n} mechanisms (gate requires ≥3 or BOOK_LIMIT)")
        return d

    # Q16: Evidence Coverage
    def _q16_evidence_coverage(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q16", "Q16 Evidence Coverage", 0.0)
        em = synthesis.evidence_map

        d.score = round(em.evidence_coverage, 4)
        d.detail = f"Coverage: {em.evidence_coverage:.0%}, {em.unsupported_claim_count} unsupported claims, model inference: {em.model_inference_ratio:.0%}"
        if em.evidence_coverage < 1.0:
            d.findings.append(f"evidence: {em.unsupported_claim_count} claims lack evidence support")
        if em.unsupported_claim_count > 0:
            d.findings.append(f"evidence: unsupported claim count > 0 (gate requires 0)")
        if em.model_inference_ratio > 0.5:
            d.findings.append(f"evidence: model inference ratio {em.model_inference_ratio:.0%} is high")
        return d

    # Q17: Contradiction Integrity
    def _q17_contradiction_integrity(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q17", "Q17 Contradiction Integrity", 0.0)
        contras = synthesis.contradictions.contradictions

        if not contras:
            d.score = 1.0
            d.detail = "No contradictions detected"
            return d

        classified = sum(1 for c in contras if c.classification != ContradictionType.UNRESOLVED)
        direct = sum(1 for c in contras if c.type == ContradictionType.DIRECT_CONTRADICTION)
        contextual = sum(1 for c in contras if c.type == ContradictionType.CONTEXTUAL_DIFFERENCE)

        d.score = round(classified / len(contras), 4)
        d.detail = f"{len(contras)} contradictions: {direct} direct, {contextual} contextual, {classified} classified"
        if classified < len(contras):
            d.findings.append(f"contradictions: {len(contras) - classified} unclassified")
        return d

    # Q18: Synthesis Traceability
    def _q18_synthesis_traceability(self, synthesis: BookSynthesis) -> QualityDimension:
        d = QualityDimension("Q18", "Q18 Synthesis Traceability", 0.0)

        # Check that synthesis evidence maps exist for all components
        se = synthesis.synthesis_evidence
        required_keys = ["thesis", "concepts", "arguments", "mechanisms", "evidence", "chapter_roles", "contradictions"]
        present = sum(1 for k in required_keys if k in se and se[k])

        # Check that components have traceability
        thesis_traceable = len(synthesis.thesis.core_thesis.source_locations) > 0 if synthesis.thesis.core_thesis else False
        concept_traceable = sum(1 for c in synthesis.concept_system.all_concepts() if c.chapter_refs) > 0
        arg_traceable = sum(1 for a in synthesis.argument_system.all_arguments() if a.source_chapters) > 0
        mech_traceable = sum(1 for m in synthesis.mechanism_system.mechanisms if m.source_chapters) > 0

        traceable_components = sum([thesis_traceable, concept_traceable, arg_traceable, mech_traceable])

        d.score = round(0.5 * (present / len(required_keys)) + 0.5 * (traceable_components / 4.0), 4)
        d.detail = f"Evidence map keys: {present}/{len(required_keys)}, traceable components: {traceable_components}/4"
        if present < len(required_keys):
            missing = [k for k in required_keys if k not in se or not se[k]]
            d.findings.append(f"traceability: missing synthesis evidence for {missing}")
        if traceable_components < 4:
            d.findings.append(f"traceability: {4 - traceable_components} component types lack chapter traceability")
        return d
