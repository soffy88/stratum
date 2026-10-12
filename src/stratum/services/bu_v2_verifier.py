"""Verification for produced understanding — spec §12.

§12 forbids the direct jump:

    GENERATED -> VERIFIED

so a BU cannot reach VERIFIED by being produced. It has to pass checks that are
computed from the artifact itself. The existing ``_require_verified`` in
``bu_v2_pipeline`` already refuses a BU whose artifact is missing, FAIL, BLOCKED,
mismatched, or that self-reports unresolved gaps. This module produces that
artifact honestly: it runs the checks, records which ones ran, and derives the
outcome from them.

The important property is that this module does not decide what the answer
should be. It runs checks and reports. A FAIL is the correct outcome for a book
that was understood poorly, and the gate's job is to make that failure visible
rather than to let a DRAFT BU reach VERIFIED.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    VerificationArtifact,
    VerificationOutcome,
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.name,
            "status": "pass" if self.passed else "fail",
            "detail": self.detail,
        }


@dataclass
class VerificationReport:
    run_id: str
    book_id: str
    checks: list[CheckResult] = field(default_factory=list)
    # P11 §11: quality_level is carried here for convenience but COMPUTED by the
    # quality evaluator and never gates verification. A low-quality
    # understanding is still a correctly produced one, and §11 explicitly
    # forbids quality from blocking publication.
    quality_level: str = ""

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def outcome(self) -> VerificationOutcome:
        """FAIL beats BLOCKED beats PASS, the same precedence the pipeline uses.

        Every check here is executable, so BLOCKED is not currently reachable
        from this module; it is part of the outcome vocabulary because
        ``_require_verified`` distinguishes it, and a future check that cannot
        run must not silently count as a pass.
        """
        if any(c.passed is False for c in self.checks):
            return VerificationOutcome.FAIL
        return VerificationOutcome.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "book_id": self.book_id,
            "outcome": self.outcome.value,
            "checks": [c.to_dict() for c in self.checks],
            "failed_count": len(self.failed),
            "quality_level": self.quality_level,
            "quality_is_not_a_verdict": True,
        }


class BUVerifier:
    """Run the checks §12 implies, and derive an outcome from them."""

    def verify(
        self,
        bu: BookUnderstandingV2,
        *,
        chapter_count: int,
        evidence_count: int,
        failed_chapters: int,
    ) -> VerificationReport:
        rep = VerificationReport(run_id=bu.run_id, book_id=bu.book_id)

        # 1. Provenance. A BU with no book or run cannot be cited back.
        rep.checks.append(
            CheckResult(
                "provenance_present",
                bool(bu.book_id and bu.run_id and bu.substrate_id),
                f"book_id={bool(bu.book_id)} run_id={bool(bu.run_id)} substrate={bool(bu.substrate_id)}",
            )
        )

        # 2. Coverage. A book "understood" at 20% is not understood.
        min_cov = 0.5
        rep.checks.append(
            CheckResult(
                "coverage_floor",
                bu.coverage_score >= min_cov,
                f"coverage={bu.coverage_score:.2f} floor={min_cov}",
            )
        )

        # 3. Framing exists. Essence is derived from these, so without them §13
        #    cannot be answered at all.
        rep.checks.append(
            CheckResult(
                "has_governing_questions",
                len(bu.governing_questions) > 0,
                f"count={len(bu.governing_questions)}",
            )
        )
        rep.checks.append(
            CheckResult(
                "has_central_theses", len(bu.central_theses) > 0, f"count={len(bu.central_theses)}"
            )
        )

        # 4. Evidence. §11 requires claims to be traceable; zero evidence for a
        #    non-trivial book means nothing is traceable.
        if chapter_count > 0:
            rep.checks.append(
                CheckResult(
                    "evidence_present",
                    evidence_count > 0,
                    f"evidence={evidence_count} chapters={chapter_count}",
                )
            )

        # 5. Structural derivation. §10.4 forbids a concatenation; a book with
        #    no dependency edges and no evolution is a concatenation.
        edges = getattr(bu.chapter_dependency_graph, "dependencies", []) or []
        structure = len(edges) + len(bu.concept_evolution or [])
        if chapter_count > 2:
            rep.checks.append(
                CheckResult(
                    "structure_derived",
                    structure > 0,
                    f"edges={len(edges)} evolution_steps={len(bu.concept_evolution)}",
                )
            )

        # 6. Chapter production actually succeeded.
        if chapter_count:
            rep.checks.append(
                CheckResult(
                    "chapter_extraction_complete",
                    failed_chapters == 0,
                    f"failed={failed_chapters}/{chapter_count}",
                )
            )

        # 7. The BU must not claim verification it was not given.
        rep.checks.append(
            CheckResult(
                "not_self_verified",
                bu.verification_score == 0.0,
                f"verification_score={bu.verification_score}",
            )
        )
        return rep

    def to_artifact(self, rep: VerificationReport, bu: BookUnderstandingV2) -> VerificationArtifact:
        """The artifact ``_require_verified`` consumes.

        ``unresolved_gap_count`` is the honest count of failed checks. A report
        that failed three checks must not self-report zero gaps, because the
        gate checks that field.
        """
        ts = datetime.now(timezone.utc).isoformat()
        fingerprint = hashlib.sha256(
            f"{rep.run_id}|{rep.book_id}|{rep.outcome.value}|{len(rep.checks)}".encode()
        ).hexdigest()[:12]
        return VerificationArtifact(
            id=f"va_{fingerprint}",
            run_id=rep.run_id,
            book_id=rep.book_id,
            status=rep.outcome,
            checked_artifacts=[c.name for c in rep.checks],
            unresolved_gap_count=len(rep.failed),
            verification_timestamp=ts,
        )
