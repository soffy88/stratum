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
