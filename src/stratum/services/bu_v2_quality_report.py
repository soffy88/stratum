"""Quality reporting — spec §4, §9, §18.

One place that turns a quality evaluation into something a person can read, and
that keeps the two questions the spec insists on separating actually separate:

    VerificationReport  "did the pipeline do its job"     PASS / FAIL
    BUQualityReport     "how much did it understand"      A / B / C / D

A run is routinely pipeline-PASS at quality-C. Printing them side by side without
that separation is how a green tick comes to mean "the book was understood", which
§10 forbids.

Nothing here writes. A report is a rendering of an existing evaluation, so it
cannot become a second authority for what a book says.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stratum.services.bu_v2_quality_evaluator import (
    BUQualityReport,
    level_for,
)


@dataclass
class QualityGateResult:
    """One of §15's gates, evaluated from measurements rather than asserted."""

    gate: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": "PASS" if self.passed else "FAIL",
            "detail": self.detail,
        }


def evaluate_p12_gates(
    result: Any,
    *,
    structure: dict[str, Any] | None = None,
) -> list[QualityGateResult]:
    """P12 §17: seven gates over the reasoning artefacts.

    Each is computed from a measurement. §13's thresholds are checked here rather
    than asserted in prose, so a run that misses one fails a gate instead of
    being described as a pass.
    """
    p12 = getattr(result, "p12", None) or {}
    dep = p12.get("dependency")
    evo = p12.get("evolution")
    arg = p12.get("argument")
    deep = p12.get("deep_quality")
    numbered_ids = numbered_chapter_ids(result, structure)
    chapters = [c for c in result.chapters if c.chapter_id in numbered_ids]
    n_chapters = len(chapters)

    gates: list[QualityGateResult] = []

    # Gate 1: a reasoning graph exists at all.
    nodes = len(dep.graph.nodes) if dep else 0
    edges = len(dep.graph.edges) if dep else 0
    gates.append(
        QualityGateResult(
            "p12_1_reasoning_graph",
            bool(dep) and nodes > 0,
            f"{nodes} nodes, {edges} edges" if dep else "no reasoning graph was built",
        )
    )

    # Gate 2: cross-chapter dependency, against §13's >= chapter_count / 2.
    # Only asserted relations count: the sequence fallback (document order)
    # is reported in the graph but must not clear the threshold on its own.
    # Same rule as Q10; the gate and the dimension measure the same thing.
    cross = dep.asserted_cross_chapter_count if dep else 0
    fallback = (dep.cross_chapter_count - cross) if dep else 0
    threshold = max(1, n_chapters // 2)
    gates.append(
        QualityGateResult(
            "p12_2_cross_chapter_dependency",
            cross >= threshold,
            f"{cross} asserted cross-chapter relations"
            + (f" (+{fallback} from document order, not counted)" if fallback else "")
            + f", §13 requires >= {threshold} for {n_chapters} chapters",
        )
    )

    # Gate 3: concept evolution, against §13's >= 10 evolving concepts.
    # §13 says "introduced, refined and applied". The lenient count is
    # introduced+refined; both are reported so the number that cleared the gate
    # is visible rather than implied by which one was chosen.
    evolving = evo.evolving_count if evo else 0
    full = evo.fully_evolving_count if evo else 0
    gates.append(
        QualityGateResult(
            "p12_3_concept_evolution",
            full >= 10,
            f"{full} concepts introduced, refined and applied "
            f"({evolving} introduced and refined, "
            f"{len(evo.trajectories) if evo else 0} tracked), §13 requires >= 10",
        )
    )

    # Gate 4: argument graph, against §13's >= 5 chains.
    chains = len(arg.chains) if arg else 0
    gates.append(
        QualityGateResult(
            "p12_4_argument_graph",
            chains >= 5,
            f"{chains} reasoning chains ({arg.complete_chains if arg else 0} complete), "
            "§13 requires >= 5",
        )
    )

    # Gate 5: evidence strength is available and bound.
    bound = sum(len(getattr(c, "evidence_strengths", {}) or {}) for c in chapters)
    strengths = {
        kind for c in chapters for kind in (getattr(c, "evidence_strengths", {}) or {}).values()
    }
    gates.append(
        QualityGateResult(
            "p12_5_evidence_strength",
            bound > 0 and bool(strengths),
            f"{bound} claim-evidence bindings across {len(strengths)} strength kinds",
        )
    )

    # Gate 6: deep quality Q8-Q11 generated.
    q = [d for d in (deep.dimensions if deep else []) if d.key in ("Q8", "Q9", "Q10", "Q11")]
    gates.append(
        QualityGateResult(
            "p12_6_deep_quality",
            len(q) == 4,
            f"{len(q)} of 4 deep dimensions scored, overall {deep.overall:.2f} ({deep.deep_level})"
            if deep
            else "no deep quality report",
        )
    )

    # Gate 7: boundaries held, measured on the produced artefacts.
    blob = ""
    for obj in (dep.graph if dep else None,):
        blob += repr(obj.to_dict()) if obj else ""
    isolated = all(
        b not in blob for b in ("rf.", "aii_refined", "refined_ku", "cx.learning_progress")
    )
    gates.append(
        QualityGateResult(
            "p12_7_boundaries",
            isolated,
            "reasoning graph references neither the B warehouse nor learning state",
        )
    )
    return gates


def numbered_chapter_ids(result: Any, structure: dict[str, Any] | None = None) -> set[str]:
    """The ids of chapters that are actually chapters.

    §13's thresholds are stated per chapter, so the denominator has to exclude
    front and back matter. The structure report types every span (`chapter`,
    `front_matter`, `back_matter`), so ask it rather than guessing from the id:
    an earlier `int(digits) <= 100` test counted an appendix as a chapter
    whenever the loader happened to give it a low id.
    """
    excluded: set[str] = set()
    structure = structure if structure is not None else getattr(result, "structure", None) or {}
    for c in structure.get("chapters", []) or []:
        if c.get("kind") in ("back_matter", "front_matter") and c.get("chapter_id"):
            excluded.add(str(c["chapter_id"]))
    # The pipeline stores only the metadata dict on result.structure, which has
    # no per-span kinds. The kinds travel on result.structure_kinds instead;
    # without this fallback every span counts as a chapter in a real run.
    kinds = getattr(result, "structure_kinds", None) or {}
    for cid, kind in kinds.items():
        if kind in ("back_matter", "front_matter"):
            excluded.add(str(cid))
    return {c.chapter_id for c in result.chapters if c.chapter_id not in excluded}


def evaluate_gates(
    quality: BUQualityReport,
    *,
    structure: dict[str, Any] | None = None,
    detection_ratio: float | None = None,
    coverage_ratio: float | None = None,
    content_coverage: float | None = None,
    legacy_fused: bool = False,
    b_isolated: bool = True,
    learning_isolated: bool = True,
    chapter_count: int = 0,
    context_used: bool = False,
) -> list[QualityGateResult]:
    """§15's six gates, each computed from a measurement.

    A gate that cannot be measured is reported FAIL rather than skipped. A
    skipped gate reads as a passed one once it is a bullet in a list, which is
    the failure mode §15 exists to prevent.
    """
    gates: list[QualityGateResult] = []

    # Gate 1: structure reliable.
    if detection_ratio is None or structure is None:
        gates.append(QualityGateResult("1_structure", False, "structure metadata unavailable"))
    else:
        conf = float(structure.get("confidence_mean") or 0.0)
        ok = detection_ratio >= 0.95 and conf >= 0.80
        gates.append(
            QualityGateResult(
                "1_structure",
                ok,
                f"detection {detection_ratio:.0%} of declared chapters, mean confidence {conf:.2f}",
            )
        )

    # Gate 2: chapter context enhanced.
    gates.append(
        QualityGateResult(
            "2_producer",
            context_used and chapter_count > 0,
            f"book/chapter/role/position context injected for {chapter_count} chapters"
            if context_used
            else "no chapter context was injected",
        )
    )

    # Gate 3: whole-book model exists.
    by = {d.key: d for d in quality.dimensions}
    integ = by["Q5"].score
    gates.append(
        QualityGateResult(
            "3_integration",
            integ >= 0.5 and (by["Q5"].detail.startswith("0 cross-chapter") is False),
            f"integration {integ:.2f}: {by['Q5'].detail}",
        )
    )

    # Gate 4: legacy fusion.
    gates.append(
        QualityGateResult(
            "4_legacy_fusion",
            legacy_fused,
            "one real legacy BU mapped through the adapter"
            if legacy_fused
            else "no legacy BU was imported",
        )
    )

    # Gate 5: quality dimensions generated.
    gates.append(
        QualityGateResult(
            "5_quality_report",
            len(quality.dimensions) == 7,
            f"{len(quality.dimensions)} of 7 dimensions scored, overall "
            f"{quality.overall:.2f} (level {quality.quality_level})",
        )
    )

    # Gate 6: boundary.
    gates.append(
        QualityGateResult(
            "6_boundary",
            b_isolated and learning_isolated,
            f"B warehouse isolated={b_isolated}, learning isolated={learning_isolated}",
        )
    )

    # §14's coverage requirement, reported with both measures so neither is read
    # alone: document coverage counts front matter and the index as uncovered,
    # content coverage excludes them because they are not chapter content.
    if coverage_ratio is not None and content_coverage is not None:
        gates.append(
            QualityGateResult(
                "7_real_book_coverage",
                coverage_ratio >= 0.99 or content_coverage >= 0.99,
                f"document {coverage_ratio:.2%}, content {content_coverage:.2%} "
                "(document coverage counts front matter and index as uncovered)",
            )
        )
    else:
        gates.append(QualityGateResult("7_real_book_coverage", False, "coverage not measured"))
    return gates


def render_gates(gates: list[QualityGateResult]) -> str:
    lines = ["", "P11 ACCEPTANCE GATES", "-" * 70]
    for g in gates:
        lines.append(f"  [{g.to_dict()['status']:>4}] {g.gate:<24} {g.detail[:40]}")
    passed = sum(1 for g in gates if g.passed)
    lines += ["-" * 70, f"  {passed} of {len(gates)} gates passed"]
    return "\n".join(lines)


def render_hard_gates(report: Any) -> list[str]:
    """Task D: the hard gates and the six-dimension score, as report lines."""
    lines = ["", "P13 HARD QUALITY GATES (task D)", "-" * 70]
    for g in report.gates:
        status = "PASS" if g.passed else "FAIL"
        lines.append(f"  [{status:>4}] {g.gate:<30} {g.detail[:34]}")
    lines += [
        "-" * 70,
        f"  {sum(1 for g in report.gates if g.passed)} of {len(report.gates)} hard gates passed",
        "",
        "SIX-DIMENSION SCORE (0-10)",
        "-" * 70,
    ]
    for d in report.dimensions:
        lines.append(f"  {d.name:<26}{d.score:>6.2f}  {d.detail[:40]}")
    lines += [
        "-" * 70,
        f"  {'OVERALL':<26}{report.overall:>6.2f}",
    ]
    return lines


@dataclass
class BU2QualityReportBundle:
    """§4's report artifact: quality plus gates plus the run that produced them."""

    quality: BUQualityReport
    gates: list[QualityGateResult] = field(default_factory=list)
    run_id: str = ""
    book_id: str = ""
    substrate_id: str = ""
    pipeline_status: str = "UNKNOWN"
    legacy_fusion: dict[str, Any] | None = None
    chapter_roles: list[dict[str, str]] = field(default_factory=list)
    # Task D: the hard gates and six-dimension score, when a run produced them.
    hard_gates: Any = None

    @property
    def all_gates_pass(self) -> bool:
        return bool(self.gates) and all(g.passed for g in self.gates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "book_id": self.book_id,
            "substrate_id": self.substrate_id,
            "pipeline_status": self.pipeline_status,
            "quality": self.quality.to_dict(),
            "gates": [g.to_dict() for g in self.gates],
            "all_gates_pass": self.all_gates_pass,
            "legacy_fusion": self.legacy_fusion,
            "chapter_roles": self.chapter_roles,
            "hard_gates": self.hard_gates.to_dict() if self.hard_gates is not None else None,
        }

    def render(self) -> str:
        parts = [
            self.quality.render(),
            render_gates(self.gates),
            "",
            f"  PIPELINE STATUS : {self.pipeline_status}",
            f"  QUALITY LEVEL   : {self.quality.quality_level}",
            "  These are independent. A PASS pipeline with a low quality level",
            "  means the book was processed correctly and understood shallowly.",
        ]
        if self.hard_gates is not None:
            parts += render_hard_gates(self.hard_gates)
        if self.legacy_fusion:
            parts += [
                "",
                "LEGACY FUSION (§7.4)",
                f"  legacy bu_id={self.legacy_fusion.get('legacy_id')}",
                f"  claims mapped    {self.legacy_fusion.get('claims_mapped')}",
                f"  arguments mapped {self.legacy_fusion.get('arguments_mapped')}",
                f"  unmappable fields {len(self.legacy_fusion.get('unmapped_fields') or [])}",
            ]
            for d in (self.legacy_fusion.get("degradations") or [])[:5]:
                parts.append(f"  - {d[:96]}")
        return "\n".join(parts)


def build_report(
    quality: BUQualityReport,
    *,
    run_id: str = "",
    book_id: str = "",
    substrate_id: str = "",
    pipeline_status: str = "UNKNOWN",
    gates: list[QualityGateResult] | None = None,
    legacy_fusion: dict[str, Any] | None = None,
    chapter_roles: list[dict[str, str]] | None = None,
) -> BU2QualityReportBundle:
    return BU2QualityReportBundle(
        quality=quality,
        gates=gates or [],
        run_id=run_id or quality.run_id,
        book_id=book_id or quality.book_id,
        substrate_id=substrate_id,
        pipeline_status=pipeline_status,
        legacy_fusion=legacy_fusion,
        chapter_roles=chapter_roles or [],
    )


def write_report(bundle: BU2QualityReportBundle, path: str) -> str:
    """Persist as JSON. Writes a report, never a BU, so no authority is created."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bundle.to_dict(), fh, indent=2, ensure_ascii=False)
    return path


def summarise(bundle: BU2QualityReportBundle) -> str:
    """One line for a log or a commit message."""
    q = bundle.quality
    passed = sum(1 for g in bundle.gates if g.passed)
    return (
        f"quality={q.quality_level}({q.overall:.2f}) "
        f"pipeline={bundle.pipeline_status} "
        f"gates={passed}/{len(bundle.gates)} "
        f"chapters={q.chapter_count} evidence={q.evidence_count}"
    )


def legacy_fusion_gates(result: Any) -> list[QualityGateResult]:
    """Gates for the legacy adapter alone, for testing without a book run."""
    if result is None or result.bu is None:
        return [QualityGateResult("legacy", False, "no BU produced from the legacy row")]
    mapped = result.claims_mapped + result.arguments_mapped
    return [
        QualityGateResult(
            "legacy_mapped",
            mapped > 0,
            f"{result.claims_mapped} claims and {result.arguments_mapped} arguments mapped",
        ),
        QualityGateResult(
            "legacy_degradations_recorded",
            bool(result.degradations) or mapped == 0,
            f"{len(result.degradations)} degradation(s) recorded rather than hidden",
        ),
        QualityGateResult(
            "legacy_not_self_verifying",
            result.bu.verification_score == 0.0,
            "a mapped legacy BU carries no verification score of its own",
        ),
        QualityGateResult(
            "legacy_status_draft",
            result.bu.status.value == "DRAFT",
            f"status={result.bu.status.value}",
        ),
    ]


def overall_from_dimensions(scores: dict[str, float]) -> tuple[float, str]:
    """Weighted overall from raw dimension scores, without a full report."""
    if not scores:
        return 0.0, "D"
    overall = round(sum(scores.values()) / len(scores), 4)
    return overall, level_for(overall)
