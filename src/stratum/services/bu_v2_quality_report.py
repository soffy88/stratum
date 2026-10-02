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
        return {"gate": self.gate, "status": "PASS" if self.passed else "FAIL", "detail": self.detail}


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
                f"detection {detection_ratio:.0%} of declared chapters, "
                f"mean confidence {conf:.2f}",
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