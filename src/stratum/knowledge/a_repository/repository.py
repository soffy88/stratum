"""A Repository — repository authority layer.

No direct SQL from service layer: all persistence goes through these
repositories. A仓 does no concept deduplication and no automatic merging.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from .models import BookSource, KUCandidate, ReadingEvidence, ReadingRun, SourceVersion


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class BookSourceRepository:
    """BookSource persistence authority."""

    @staticmethod
    def create(title: str, author: Optional[str] = None,
               publisher: Optional[str] = None, isbn: Optional[str] = None,
               language: Optional[str] = None,
               metadata: Optional[dict] = None) -> BookSource:
        return BookSource(
            id=_new_id("bs"),
            title=title,
            author=author,
            publisher=publisher,
            isbn=isbn,
            language=language,
            metadata=metadata or {},
        )

    @staticmethod
    def get(book_source_id: str) -> Optional[BookSource]:
        raise NotImplementedError("DB binding required")


class SourceVersionRepository:
    """SourceVersion persistence authority."""

    @staticmethod
    def create(book_source_id: str, version: str, file_hash: str,
               storage_uri: Optional[str] = None) -> SourceVersion:
        return SourceVersion(
            id=_new_id("sv"),
            book_source_id=book_source_id,
            version=version,
            file_hash=file_hash,
            storage_uri=storage_uri,
        )

    @staticmethod
    def get_by_file_hash(file_hash: str) -> Optional[SourceVersion]:
        raise NotImplementedError("DB binding required")


class ReadingRunRepository:
    """ReadingRun persistence authority."""

    @staticmethod
    def create(source_version_id: str,
               metadata: Optional[dict] = None) -> ReadingRun:
        return ReadingRun(
            id=_new_id("arr"),
            source_version_id=source_version_id,
            metadata=metadata or {},
        )

    @staticmethod
    def get(run_id: str) -> Optional[ReadingRun]:
        raise NotImplementedError("DB binding required")

    @staticmethod
    def update_status(run_id: str, status: str) -> None:
        raise NotImplementedError("DB binding required")


class EvidenceRepository:
    """ReadingEvidence persistence authority. Evidence is immutable."""

    @staticmethod
    def create(reading_run_id: str, page_number: Optional[int] = None,
               location: Optional[dict] = None, content: Optional[str] = None,
               evidence_type: Optional[str] = None) -> ReadingEvidence:
        return ReadingEvidence(
            id=_new_id("ev"),
            reading_run_id=reading_run_id,
            page_number=page_number,
            location=location or {},
            content=content,
            evidence_type=evidence_type,
        )

    @staticmethod
    def list_for_run(reading_run_id: str) -> List[ReadingEvidence]:
        raise NotImplementedError("DB binding required")


class KUCandidateRepository:
    """KUCandidate persistence authority. No dedup, no auto-merge."""

    @staticmethod
    def create(reading_run_id: str, evidence_id: str, content: Optional[str] = None,
               candidate_type: Optional[str] = None,
               confidence: Optional[float] = None) -> KUCandidate:
        return KUCandidate(
            id=_new_id("kc"),
            reading_run_id=reading_run_id,
            evidence_id=evidence_id,
            content=content,
            candidate_type=candidate_type,
            confidence=confidence,
        )

    @staticmethod
    def list_for_run(reading_run_id: str) -> List[KUCandidate]:
        raise NotImplementedError("DB binding required")

    @staticmethod
    def update_status(candidate_id: str, status: str) -> None:
        raise NotImplementedError("DB binding required")
