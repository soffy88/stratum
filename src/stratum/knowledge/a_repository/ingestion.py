"""A Repository P1 — real book ingestion pipeline (in-memory, no DB mutation).

Pilot: 利率史（第四版）, Chapter 1 only, ONE_BOOK_ONLY.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def deterministic_id(prefix: str, *parts: str) -> str:
    """Content-derived stable ID, so a frozen baseline is reproducible."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:12]}"


class AuthorityViolation(Exception):
    """Raised when an A仓-forbidden operation is attempted."""


@dataclass
class BookSource:
    id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class SourceVersion:
    id: str
    book_source_id: str
    version: str
    file_hash: str
    format: str
    page_count: int
    storage_uri: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ReadingRun:
    id: str
    source_version_id: str
    status: str = "CREATED"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ReadingEvidence:
    id: str
    reading_run_id: str
    source_version_id: str
    page_number: int
    locator: Dict
    content_span: str
    extractor_version: str


@dataclass
class KUCandidate:
    id: str
    reading_run_id: str
    evidence_id: str
    content: str
    candidate_type: str
    confidence: float
    source_span: str
    status: str = "EXTRACTED"
    classification: Optional[str] = None
    classified_at: Optional[str] = None


class InMemoryAStore:
    """In-memory store for P1 pilot. No DB mutation."""

    def __init__(self):
        self.book_sources: Dict[str, BookSource] = {}
        self.source_versions: Dict[str, SourceVersion] = {}
        self.reading_runs: Dict[str, ReadingRun] = {}
        self.evidence: Dict[str, ReadingEvidence] = {}
        self.ku_candidates: Dict[str, KUCandidate] = {}
        self._file_hash_index: Dict[str, str] = {}
        # P2 additions (migration 071)
        self.quality: Dict[str, "EvidenceQuality"] = {}
        self._quality_by_evidence: Dict[str, str] = {}


class AIngestionPipeline:
    """P1 real book ingestion pipeline.

    Stages: register -> snapshot -> parse -> read -> extract -> candidate
    """

    def __init__(self, store: InMemoryAStore):
        self.store = store

    # ── Stage 1: register ────────────────────────────────────────────────────
    def register(self, title: str, author: Optional[str] = None,
                 publisher: Optional[str] = None, isbn: Optional[str] = None,
                 language: Optional[str] = None,
                 metadata: Optional[Dict] = None) -> BookSource:
        bs = BookSource(
            id=_new_id("bs"),
            title=title,
            author=author,
            publisher=publisher,
            isbn=isbn,
            language=language,
            metadata=metadata or {},
        )
        self.store.book_sources[bs.id] = bs
        return bs

    # ── Stage 2: snapshot ────────────────────────────────────────────────────
    def snapshot(self, book_source_id: str, version: str, file_hash: str,
                 fmt: str, page_count: int,
                 storage_uri: Optional[str] = None,
                 version_id: Optional[str] = None) -> SourceVersion:
        if file_hash in self.store._file_hash_index:
            existing_id = self.store._file_hash_index[file_hash]
            return self.store.source_versions[existing_id]
        sv = SourceVersion(
            id=version_id or _new_id("sv"),
            book_source_id=book_source_id,
            version=version,
            file_hash=file_hash,
            format=fmt,
            page_count=page_count,
            storage_uri=storage_uri,
        )
        self.store.source_versions[sv.id] = sv
        self.store._file_hash_index[file_hash] = sv.id
        return sv

    # ── Stage 3: parse (structure only) ──────────────────────────────────────
    def parse_structure(self, source_version_id: str,
                        chapter: str,
                        sections: List[Dict]) -> List[Dict]:
        """Parse book structure. No content understanding."""
        sv = self.store.source_versions.get(source_version_id)
        if sv is None:
            raise ValueError(f"SourceVersion {source_version_id} not found")
        structure = []
        for sec in sections:
            structure.append({
                "source_version_id": source_version_id,
                "chapter": chapter,
                "section": sec.get("section"),
                "page_start": sec.get("page_start"),
                "page_end": sec.get("page_end"),
            })
        return structure

    # ── Stage 4: read ────────────────────────────────────────────────────────
    def create_reading_run(self, source_version_id: str) -> ReadingRun:
        sv = self.store.source_versions.get(source_version_id)
        if sv is None:
            raise ValueError(f"SourceVersion {source_version_id} not found")
        run = ReadingRun(
            id=_new_id("arr"),
            source_version_id=source_version_id,
            status="CREATED",
        )
        self.store.reading_runs[run.id] = run
        return run

    def resume_reading_run(self, run_id: str) -> ReadingRun:
        run = self.store.reading_runs.get(run_id)
        if run is None:
            raise ValueError(f"ReadingRun {run_id} not found")
        return run

    def transition_run(self, run_id: str, new_status: str) -> ReadingRun:
        run = self.store.reading_runs.get(run_id)
        if run is None:
            raise ValueError(f"ReadingRun {run_id} not found")
        valid = {"CREATED", "SNAPSHOTTED", "READING", "EXTRACTING",
                 "CANDIDATING", "VERIFYING", "REVIEWING", "FROZEN", "FAILED"}
        if new_status not in valid:
            raise ValueError(f"Invalid status: {new_status}")
        run.status = new_status
        return run

    # ── Stage 5: extract evidence ────────────────────────────────────────────
    def extract_evidence(self, reading_run_id: str, source_version_id: str,
                         page_number: int, locator: Dict,
                         content_span: str,
                         extractor_version: str = "p1-v1",
                         evidence_id: Optional[str] = None) -> ReadingEvidence:
        run = self.store.reading_runs.get(reading_run_id)
        if run is None:
            raise ValueError(f"ReadingRun {reading_run_id} not found")
        if not content_span:
            raise ValueError("content_span cannot be empty")
        if page_number is None or page_number < 1:
            raise ValueError("page_number must be >= 1")
        ev = ReadingEvidence(
            id=evidence_id or _new_id("ev"),
            reading_run_id=reading_run_id,
            source_version_id=source_version_id,
            page_number=page_number,
            locator=locator,
            content_span=content_span,
            extractor_version=extractor_version,
        )
        self.store.evidence[ev.id] = ev
        return ev

    # ── Stage 6: KU candidate ────────────────────────────────────────────────
    def generate_candidate(self, reading_run_id: str, evidence_id: str,
                           content: str, candidate_type: str,
                           confidence: float, source_span: str,
                           candidate_id: Optional[str] = None) -> KUCandidate:
        run = self.store.reading_runs.get(reading_run_id)
        if run is None:
            raise ValueError(f"ReadingRun {reading_run_id} not found")
        ev = self.store.evidence.get(evidence_id)
        if ev is None:
            raise ValueError(f"Evidence {evidence_id} not found")
        if not source_span:
            raise ValueError("source_span cannot be empty")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        kc = KUCandidate(
            id=candidate_id or _new_id("kc"),
            reading_run_id=reading_run_id,
            evidence_id=evidence_id,
            content=content,
            candidate_type=candidate_type,
            confidence=confidence,
            source_span=source_span,
        )
        self.store.ku_candidates[kc.id] = kc
        return kc

    # ── Quality gates ────────────────────────────────────────────────────────
    def verify_evidence_provenance(self, evidence_id: str) -> bool:
        ev = self.store.evidence.get(evidence_id)
        if ev is None:
            return False
        return all([
            ev.source_version_id,
            ev.reading_run_id,
            ev.page_number is not None and ev.page_number >= 1,
            ev.locator,
            ev.content_span,
            ev.extractor_version,
        ])

    def verify_ku_trace(self, candidate_id: str) -> bool:
        kc = self.store.ku_candidates.get(candidate_id)
        if kc is None:
            return False
        ev = self.store.evidence.get(kc.evidence_id)
        if ev is None:
            return False
        return all([
            kc.evidence_id,
            kc.source_span,
            kc.confidence is not None,
        ])

    # ── Evidence immutability (A仓 authority) ────────────────────────────────
    def overwrite_evidence(self, evidence_id: str, **changes) -> None:
        """FORBIDDEN in A仓. Original book evidence is never mutated."""
        raise AuthorityViolation(
            f"A仓 forbids overwriting evidence {evidence_id}; "
            "original book evidence is immutable."
        )

    def overwrite_candidate(self, candidate_id: str, **changes) -> None:
        """FORBIDDEN in A仓. Candidates are never overwritten or auto-merged."""
        raise AuthorityViolation(
            f"A仓 forbids overwriting candidate {candidate_id}; "
            "candidates are append-only, never merged."
        )

    def auto_merge_candidates(self, *candidate_ids: str) -> None:
        """FORBIDDEN in A仓. No automatic Knowledge Unit merging."""
        raise AuthorityViolation(
            "A仓 forbids automatic candidate merging; "
            "dedup/merge belongs to B仓, not A仓."
        )

    # ── Replay / idempotency ─────────────────────────────────────────────────
    def evidence_fingerprint(self, reading_run_id: str) -> set:
        """Stable fingerprint of persisted evidence for replay comparison."""
        return {
            (ev.page_number, ev.content_span)
            for ev in self.store.evidence.values()
            if ev.reading_run_id == reading_run_id
        }

    def has_evidence(self, reading_run_id: str, page_number: int,
                     content_span: str) -> bool:
        for ev in self.store.evidence.values():
            if (ev.reading_run_id == reading_run_id
                    and ev.page_number == page_number
                    and ev.content_span == content_span):
                return True
        return False

    def has_candidate(self, reading_run_id: str, evidence_id: str,
                      source_span: str) -> bool:
        for kc in self.store.ku_candidates.values():
            if (kc.reading_run_id == reading_run_id
                    and kc.evidence_id == evidence_id
                    and kc.source_span == source_span):
                return True
        return False

    def evidence_count(self, reading_run_id: str) -> int:
        return sum(1 for ev in self.store.evidence.values()
                   if ev.reading_run_id == reading_run_id)

    def candidate_count(self, reading_run_id: str) -> int:
        return sum(1 for kc in self.store.ku_candidates.values()
                   if kc.reading_run_id == reading_run_id)

    def orphan_evidence(self) -> List[str]:
        """Evidence whose reading_run or source_version no longer exists."""
        orphans = []
        for ev in self.store.evidence.values():
            if ev.reading_run_id not in self.store.reading_runs:
                orphans.append(ev.id)
            elif ev.source_version_id not in self.store.source_versions:
                orphans.append(ev.id)
        return orphans

    def orphan_candidates(self) -> List[str]:
        """Candidates whose evidence no longer exists."""
        return [kc.id for kc in self.store.ku_candidates.values()
                if kc.evidence_id not in self.store.evidence]

    def page_coverage(self, reading_run_id: str,
                      total_pages: int) -> Dict:
        pages = set()
        for ev in self.store.evidence.values():
            if ev.reading_run_id == reading_run_id:
                pages.add(ev.page_number)
        covered = len(pages)
        return {
            "total_pages": total_pages,
            "covered_pages": covered,
            "coverage_pct": (covered / total_pages * 100) if total_pages else 0.0,
            "missing_pages": sorted(set(range(1, total_pages + 1)) - pages),
        }
