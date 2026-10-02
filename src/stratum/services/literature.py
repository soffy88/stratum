"""Acquisition-only provider contract. Candidates are never canonical Sources."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass(frozen=True)
class LiteratureCandidate:
    title: str
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    url: str | None = None
    open_access_url: str | None = None
    license: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

class LiteratureProvider(Protocol):
    def search(self, query: str, *, limit: int = 20) -> list[LiteratureCandidate]: ...
