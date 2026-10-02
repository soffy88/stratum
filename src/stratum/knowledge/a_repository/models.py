"""A Repository — ORM-aligned domain models (migration 070)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .types import (
    CandidateType,
    EvidenceType,
    KUCandidateStatus,
    ReadingRunStatus,
)


class BookSource(BaseModel):
    """真实书籍身份 (stratum.book_source)."""

    id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SourceVersion(BaseModel):
    """版本固定 (stratum.source_version)."""

    id: str
    book_source_id: str
    version: str
    file_hash: str
    storage_uri: Optional[str] = None
    created_at: Optional[str] = None


class ReadingRun(BaseModel):
    """A仓阅读运行 (stratum.reading_run)."""

    id: str
    source_version_id: str
    status: ReadingRunStatus = ReadingRunStatus.CREATED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReadingEvidence(BaseModel):
    """A仓核心证据 (stratum.reading_evidence)."""

    id: str
    reading_run_id: str
    page_number: Optional[int] = None
    location: Dict[str, Any] = Field(default_factory=dict)
    content: Optional[str] = None
    evidence_type: Optional[EvidenceType] = None
    created_at: Optional[str] = None


class KUCandidate(BaseModel):
    """KU 候选 (stratum.ku_candidate). KU Candidate != B仓 KU."""

    id: str
    reading_run_id: str
    evidence_id: str
    content: Optional[str] = None
    candidate_type: Optional[CandidateType] = None
    confidence: Optional[float] = None
    created_at: Optional[str] = None
    status: KUCandidateStatus = KUCandidateStatus.EXTRACTED
