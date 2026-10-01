"""A Repository P2 — evidence quality + KU candidate classification.

Quality flow:

    ReadingEvidence
        |
        v
    EvidenceQuality
        |
        v
    KU Candidate Classification

Rules:
- resumable: each stage skips work already persisted.
- idempotent: re-running produces no duplicate rows.
- event emitting: every transition emits an event.
- no max_rounds.
- append only: quality rows and classifications are never overwritten.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import KIClassification, PipelineStage


QUALITY_VERSION = "p2-v1"

PAGINATED_SOURCE_TYPES = frozenset({"PDF", "OCR_TEXT"})


def deterministic_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


@dataclass
class EvidenceLocator:
    """Canonical locator per docs/book-understanding-2.0/A_SOURCE_LOCATOR_SPEC.md."""

    source_type: str
    source_id: str
    content_hash: str
    logical_locator: str
    physical_locator: Optional[str] = None
    line_range: Optional[tuple] = None
    page_number: Optional[int] = None

    def is_valid(self) -> bool:
        """Rule 2: resolvable — a logical or physical address must exist."""
        return bool(self.logical_locator) or bool(self.physical_locator)


@dataclass
class EvidenceQuality:
    id: str
    evidence_id: str
    source_trace_score: float
    locator_score: float
    completeness_score: float
    confidence_score: float
    quality_version: str = QUALITY_VERSION
    metadata: Dict = field(default_factory=dict)


@dataclass
class QualityEvent:
    stage: PipelineStage
    run_id: str
    payload: Dict = field(default_factory=dict)


class QualityViolation(Exception):
    """Raised on a forbidden A仓 quality operation."""


class EvidenceQualityPipeline:
    """P2 quality + classification stage.

    Append-only. Scored evidence and classified candidates only:
    no overwrite, no second reading of the source, no conclusion
    about what the evidence means.
    """

    def __init__(self, ingestion_pipeline, event_sink=None):
        self.p = ingestion_pipeline
        self.store = ingestion_pipeline.store
        self._events: List[QualityEvent] = []
        self._event_sink = event_sink or (lambda e: None)

    # ── scoring ──────────────────────────────────────────────────────────────

    @staticmethod
    def score_locator(locator: Dict) -> float:
        """Per A_SOURCE_LOCATOR_SPEC.md §5."""
        logical = bool(locator.get("logical_locator"))
        physical = bool(locator.get("physical_locator"))
        if logical and physical:
            return 1.0
        if logical and not physical:
            paginated = locator.get("source_type") in PAGINATED_SOURCE_TYPES
            # A paginated source lacking a physical locator is degraded.
            return 0.9 if not paginated else 0.6
        if physical:
            return 0.5
        return 0.0

    @staticmethod
    def score_source_trace(locator: Dict) -> float:
        """Full trace = source_id + content_hash + logical address."""
        checks = [bool(locator.get("source_id")),
                  bool(locator.get("content_hash")),
                  bool(locator.get("logical_locator")
                       or locator.get("physical_locator"))]
        return sum(checks) / len(checks)

    @staticmethod
    def score_completeness(ev) -> float:
        """Provenance completeness of an evidence row."""
        checks = [bool(ev.content_span),
                  bool(ev.extractor_version),
                  ev.page_number is not None,
                  bool(ev.locator),
                  bool(ev.source_version_id)]
        return sum(checks) / len(checks)

    # ── stage: quality ───────────────────────────────────────────────────────

    def has_quality(self, evidence_id: str) -> bool:
        return evidence_id in self.store.quality

    def score_evidence(self, evidence_id: str, locator: Dict,
                       confidence: float = 1.0,
                       quality_id: Optional[str] = None) -> EvidenceQuality:
        ev = self.store.evidence.get(evidence_id)
        if ev is None:
            raise ValueError(f"Evidence {evidence_id} not found")

        q = EvidenceQuality(
            id=quality_id or deterministic_id(
                "eq", evidence_id, QUALITY_VERSION),
            evidence_id=evidence_id,
            source_trace_score=self.score_source_trace(locator),
            locator_score=self.score_locator(locator),
            completeness_score=self.score_completeness(ev),
            confidence_score=max(0.0, min(1.0, confidence)),
            quality_version=QUALITY_VERSION,
        )
        self.store.quality[q.id] = q
        self.store._quality_by_evidence[evidence_id] = q.id
        self._emit(PipelineStage.QUALITY, ev.reading_run_id,
                   {"evidence_id": evidence_id, "quality_id": q.id})
        return q

    # ── stage: classification ────────────────────────────────────────────────

    @staticmethod
    def classify(candidate, evidence) -> KIClassification:
        """Classify a candidate from its own evidence only.

        Deliberately shallow: reads the candidate text and the evidence
        span, and returns a type. It never compares against other
        candidates (that would be dedup) and never emits a concept.
        """
        text = f"{candidate.content} {evidence.content_span}"

        # An explicit numeric/threshold claim is a FACT about a rate, rule
        # or date.
        numeric_markers = ("%", "年", "上限", "法典", "公元前", "世纪")
        if any(m in text for m in numeric_markers):
            return KIClassification.FACT

        # A named institution or body acting at a time.
        if any(m in text for m in ("取消", "废除", "颁布", "取代", "改为")):
            return KIClassification.EVENT

        # A causal / therefore structure.
        if any(m in text for m in ("因为", "因此", "导致", "所以", "使得")):
            return KIClassification.RELATION

        # A defended claim.
        if any(m in text for m in ("认为", "主张", "证明", "论证")):
            return KIClassification.ARGUMENT

        return KIClassification.CONCEPT

    def classify_candidate(self, candidate_id: str) -> KIClassification:
        kc = self.store.ku_candidates.get(candidate_id)
        if kc is None:
            raise ValueError(f"Candidate {candidate_id} not found")
        ev = self.store.evidence.get(kc.evidence_id)
        if ev is None:
            raise ValueError(
                f"Candidate {candidate_id} has no evidence; "
                "classification requires evidence."
            )
        kc.classification = self.classify(kc, ev)
        kc.classified_at = QUALITY_VERSION
        self._emit(PipelineStage.QUALITY, kc.reading_run_id,
                   {"candidate_id": candidate_id,
                    "classification": kc.classification.value})
        return kc.classification

    # ── forbidden operations ─────────────────────────────────────────────────

    def overwrite_quality(self, quality_id: str, **changes) -> None:
        raise QualityViolation(
            f"A仓 forbids overwriting evidence_quality {quality_id}; "
            "quality rows are append-only."
        )

    def overwrite_classification(self, candidate_id: str, classification) -> None:
        raise QualityViolation(
            f"A仓 forbids overwriting classification on {candidate_id}; "
            "re-classify by writing a new classification event."
        )

    def merge_candidates(self, *candidate_ids: str) -> None:
        raise QualityViolation(
            "A仓 candidates stay separate verifiable units; "
            "the quality layer has no merge step."
        )

    def write_conclusion(self, candidate_id: str) -> None:
        raise QualityViolation(
            "A仓 stores verifiable units only; a conclusion about what "
            "the evidence means is not storable here."
        )

    # ── queries ──────────────────────────────────────────────────────────────

    def quality_count(self, reading_run_id: str) -> int:
        ids = {q.evidence_id for q in self.store.quality.values()}
        return sum(1 for ev_id in ids
                   if ev_id in self.store.evidence
                   and self.store.evidence[ev_id].reading_run_id == reading_run_id)

    def classification_count(self, reading_run_id: str) -> int:
        return sum(
            1 for kc in self.store.ku_candidates.values()
            if kc.reading_run_id == reading_run_id and kc.classification is not None
        )

    def orphan_quality(self) -> List[str]:
        return [q.id for q in self.store.quality.values()
                if q.evidence_id not in self.store.evidence]

    def unclassified_candidates(self, reading_run_id: str) -> List[str]:
        return [kc.id for kc in self.store.ku_candidates.values()
                if kc.reading_run_id == reading_run_id
                and kc.classification is None]

    def overall_quality(self, reading_run_id: str) -> Dict[str, float]:
        rows = [
            self.store.quality[self.store._quality_by_evidence[ev_id]]
            for ev_id in self.store._quality_by_evidence
            if ev_id in self.store.evidence
            and self.store.evidence[ev_id].reading_run_id == reading_run_id
        ]
        if not rows:
            return {}
        keys = ("source_trace_score", "locator_score",
                "completeness_score", "confidence_score")
        return {k: sum(getattr(r, k) for r in rows) / len(rows) for k in keys}

    # ── events ───────────────────────────────────────────────────────────────

    @property
    def events(self) -> List[QualityEvent]:
        return list(self._events)

    def _emit(self, stage: PipelineStage, run_id: str, payload: Dict) -> None:
        ev = QualityEvent(stage=stage, run_id=run_id, payload=payload)
        self._events.append(ev)
        self._event_sink(ev)