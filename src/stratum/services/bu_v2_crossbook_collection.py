"""P14: Cross-Book Collection Management.

Defines and manages collections of independently understood books for cross-book analysis.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BookSynthesis,
    CrossBookCollection,
)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


@dataclass
class CollectionValidation:
    """Result of validating a cross-book collection."""

    valid: bool
    book_understandings: list[BookUnderstandingV2]
    book_syntheses: list[BookSynthesis]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BU2CrossBookCollectionManager:
    """Manages cross-book collections and validates book inputs."""

    def __init__(self, db_read_func=None):
        self.db_read = db_read_func
        self._bu_cache: dict[str, BookUnderstandingV2] = {}
        self._synthesis_cache: dict[str, BookSynthesis] = {}

    def _get_book_understanding(self, book_id: str) -> BookUnderstandingV2 | None:
        """Load BookUnderstandingV2 for a book_id (substrate_id)."""
        if book_id in self._bu_cache:
            return self._bu_cache[book_id]

        if self.db_read:
            # Find the latest verified BU for this book
            rows = self.db_read(
                "book_understandings_v2",
                {"substrate_id": book_id, "status": "VERIFIED"},
            )
            if rows:
                # Get the highest version
                latest = max(rows, key=lambda r: r.get("version", 0))
                bu = BookUnderstandingV2(**latest)
                self._bu_cache[book_id] = bu
                return bu

        return None

    def _get_book_synthesis(self, book_id: str) -> BookSynthesis | None:
        """Load BookSynthesis for a book_id."""
        if book_id in self._synthesis_cache:
            return self._synthesis_cache[book_id]

        if self.db_read:
            # Find synthesis for this book
            rows = self.db_read(
                "book_syntheses",
                {"book_id": book_id},
            )
            if rows:
                latest = max(rows, key=lambda r: r.get("created_at", ""))
                synth = BookSynthesis(**latest)
                self._synthesis_cache[book_id] = synth
                return synth

        return None

    def create_collection(
        self,
        name: str,
        description: str,
        book_ids: list[str],
    ) -> CrossBookCollection:
        """Create a new cross-book collection.

        Args:
            name: Human-readable collection name
            description: Description of the collection's purpose
            book_ids: List of substrate_ids (book identifiers)

        Returns:
            CrossBookCollection with generated ID
        """
        if len(book_ids) < 2:
            raise ValueError("Collection requires at least 2 books")

        collection_id = _stable_id("coll", *sorted(book_ids), name)
        return CrossBookCollection(
            collection_id=collection_id,
            name=name,
            description=description,
            book_ids=book_ids,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            version=1,
        )

    def validate_collection(self, collection: CrossBookCollection) -> CollectionValidation:
        """Validate that all books in the collection have valid P13 outputs.

        Returns:
            CollectionValidation with loaded BUs and syntheses, or errors.
        """
        errors = []
        warnings = []
        book_understandings = []
        book_syntheses = []

        for book_id in collection.book_ids:
            bu = self._get_book_understanding(book_id)
            if not bu:
                errors.append(f"Book {book_id}: no BookUnderstandingV2 found")
                continue
            if bu.status.value != "VERIFIED":
                warnings.append(f"Book {book_id}: BU status is {bu.status.value}, not VERIFIED")
            book_understandings.append(bu)

            synth = self._get_book_synthesis(book_id)
            if not synth:
                warnings.append(f"Book {book_id}: no BookSynthesis found")
            else:
                book_syntheses.append(synth)

        # Check for duplicate BU objects (same run_id)
        run_ids = [bu.run_id for bu in book_understandings]
        if len(run_ids) != len(set(run_ids)):
            errors.append("Duplicate BU run_ids detected — each book must have independent understanding")

        valid = len(errors) == 0 and len(book_understandings) >= 2

        return CollectionValidation(
            valid=valid,
            book_understandings=book_understandings,
            book_syntheses=book_syntheses,
            errors=errors,
            warnings=warnings,
        )

    def get_collection_books(self, collection: CrossBookCollection) -> list[dict[str, Any]]:
        """Get detailed info about books in a collection."""
        books = []
        for book_id in collection.book_ids:
            bu = self._get_book_understanding(book_id)
            synth = self._get_book_synthesis(book_id)
            books.append({
                "book_id": book_id,
                "bu_id": bu.id if bu else None,
                "bu_status": bu.status.value if bu else None,
                "synthesis_id": synth.id if synth else None,
                "core_thesis": synth.thesis.core_thesis.statement if synth and synth.thesis.core_thesis else None,
                "concept_count": sum(len(getattr(synth.concept_system, role, [])) for role in
                    ["foundational", "core", "derived", "bridging", "application", "terminal"]) if synth else 0,
                "argument_count": sum(len(getattr(synth.argument_system, attr, [])) for attr in
                    ["thesis_arguments", "major_arguments", "sub_arguments"]) if synth else 0,
                "mechanism_count": len(synth.mechanism_system.mechanisms) if synth else 0,
            })
        return books


import time