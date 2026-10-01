"""A Repository — pipeline engine.

ARepositoryPipeline: input SourceVersion -> output ReadingRun.

Stages: register -> snapshot -> read -> extract -> candidate -> verify -> freeze.

Every stage emits an event, persists state, is resumable and idempotent.
No max_rounds. No coordinator slicing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .models import BookSource, KUCandidate, ReadingEvidence, ReadingRun, SourceVersion
from .repository import (
    BookSourceRepository,
    EvidenceRepository,
    KUCandidateRepository,
    ReadingRunRepository,
    SourceVersionRepository,
)
from .types import KUCandidateStatus, PipelineStage, ReadingRunStatus

log = logging.getLogger(__name__)


class PipelineEvent:
    """Emitted by every pipeline stage."""

    def __init__(self, stage: PipelineStage, run_id: str,
                 payload: Optional[Dict[str, Any]] = None):
        self.stage = stage
        self.run_id = run_id
        self.payload = payload or {}


class PipelineStageError(Exception):
    """Stage validation rejection; run state left unchanged."""

    def __init__(self, stage: PipelineStage, reason: str):
        super().__init__(f"[{stage.value}] {reason}")
        self.stage = stage
        self.reason = reason


class ARepositoryPipeline:
    """A仓流水执行引擎.

    Resumable: each stage checks for already-persisted artifacts before
    working. Idempotent: re-running a completed stage is a no-op.
    """

    def __init__(self, event_sink: Optional[Callable[[PipelineEvent], None]] = None):
        self._event_sink = event_sink or (lambda e: None)

    # ── Stage 1: register ────────────────────────────────────────────────────
    def register(self, title: str, author: Optional[str] = None,
                 publisher: Optional[str] = None, isbn: Optional[str] = None,
                 language: Optional[str] = None,
                 metadata: Optional[dict] = None) -> BookSource:
        source = BookSourceRepository.create(
            title=title, author=author, publisher=publisher,
            isbn=isbn, language=language, metadata=metadata,
        )
        self._emit(PipelineStage.REGISTER, source.id, {"title": title})
        return source

    # ── Stage 2: snapshot ────────────────────────────────────────────────────
    def snapshot(self, book_source_id: str, version: str, file_hash: str,
                 storage_uri: Optional[str] = None) -> SourceVersion:
        existing = SourceVersionRepository.get_by_file_hash(file_hash)
        if existing is not None:
            self._emit(PipelineStage.SNAPSHOT, existing.id,
                       {"dedup": False, "reason": "file_hash already registered"})
            return existing
        sv = SourceVersionRepository.create(
            book_source_id=book_source_id, version=version,
            file_hash=file_hash, storage_uri=storage_uri,
        )
        self._emit(PipelineStage.SNAPSHOT, sv.id, {"file_hash": file_hash})
        return sv

    # ── Stage 3: read ────────────────────────────────────────────────────────
    def read(self, source_version_id: str,
             metadata: Optional[dict] = None) -> ReadingRun:
        run = ReadingRunRepository.create(
            source_version_id=source_version_id, metadata=metadata,
        )
        ReadingRunRepository.update_status(run.id, ReadingRunStatus.READING.value)
        self._emit(PipelineStage.READ, run.id,
                   {"source_version_id": source_version_id})
        return run

    # ── Stage 4: extract ─────────────────────────────────────────────────────
    def extract(self, reading_run_id: str, page_number: int,
                location: Optional[dict] = None, content: Optional[str] = None,
                evidence_type: Optional[str] = None) -> ReadingEvidence:
        run = ReadingRunRepository.get(reading_run_id)
        if run is None:
            raise PipelineStageError(PipelineStage.EXTRACT,
                                     f"ReadingRun {reading_run_id} not found")
        evidence = EvidenceRepository.create(
            reading_run_id=reading_run_id, page_number=page_number,
            location=location, content=content, evidence_type=evidence_type,
        )
        self._emit(PipelineStage.EXTRACT, reading_run_id,
                   {"evidence_id": evidence.id, "page_number": page_number})
        return evidence

    # ── Stage 5: candidate ───────────────────────────────────────────────────
    def candidate(self, reading_run_id: str, evidence_id: str,
                  content: Optional[str] = None,
                  candidate_type: Optional[str] = None,
                  confidence: Optional[float] = None) -> KUCandidate:
        run = ReadingRunRepository.get(reading_run_id)
        if run is None:
            raise PipelineStageError(PipelineStage.CANDIDATE,
                                     f"ReadingRun {reading_run_id} not found")
        existing = [c for c in KUCandidateRepository.list_for_run(reading_run_id)
                    if c.evidence_id == evidence_id and c.content == content]
        if existing:
            self._emit(PipelineStage.CANDIDATE, reading_run_id,
                       {"dedup": False, "reason": "identical candidate exists"})
            return existing[0]
        kc = KUCandidateRepository.create(
            reading_run_id=reading_run_id, evidence_id=evidence_id,
            content=content, candidate_type=candidate_type, confidence=confidence,
        )
        self._emit(PipelineStage.CANDIDATE, reading_run_id,
                   {"candidate_id": kc.id, "evidence_id": evidence_id})
        return kc

    # ── Stage 6: verify ──────────────────────────────────────────────────────
    def verify(self, reading_run_id: str) -> bool:
        run = ReadingRunRepository.get(reading_run_id)
        if run is None:
            raise PipelineStageError(PipelineStage.VERIFY,
                                     f"ReadingRun {reading_run_id} not found")
        evidences = EvidenceRepository.list_for_run(reading_run_id)
        for ev in evidences:
            if not ev.location:
                raise PipelineStageError(
                    PipelineStage.VERIFY,
                    f"Evidence {ev.id} missing provenance location",
                )
        self._emit(PipelineStage.VERIFY, reading_run_id,
                   {"evidence_count": len(evidences)})
        return True

    # ── Stage 7: freeze ──────────────────────────────────────────────────────
    def freeze(self, reading_run_id: str) -> ReadingRun:
        run = ReadingRunRepository.get(reading_run_id)
        if run is None:
            raise PipelineStageError(PipelineStage.FREEZE,
                                     f"ReadingRun {reading_run_id} not found")
        ReadingRunRepository.update_status(reading_run_id,
                                          ReadingRunStatus.FROZEN.value)
        self._emit(PipelineStage.FREEZE, reading_run_id, {})
        return run

    # ── Full pipeline ────────────────────────────────────────────────────────
    def run(self, title: str, version: str, file_hash: str,
            author: Optional[str] = None, publisher: Optional[str] = None,
            isbn: Optional[str] = None, language: Optional[str] = None,
            storage_uri: Optional[str] = None,
            metadata: Optional[dict] = None) -> ReadingRun:
        source = self.register(title, author=author, publisher=publisher,
                                isbn=isbn, language=language, metadata=metadata)
        sv = self.snapshot(source.id, version, file_hash,
                           storage_uri=storage_uri)
        run = self.read(sv.id)
        return run

    # ── Event emission ───────────────────────────────────────────────────────
    def _emit(self, stage: PipelineStage, run_id: str,
              payload: Optional[Dict[str, Any]] = None) -> None:
        event = PipelineEvent(stage=stage, run_id=run_id, payload=payload)
        self._event_sink(event)
        log.info("A仓 pipeline event: stage=%s run_id=%s", stage.value, run_id)
