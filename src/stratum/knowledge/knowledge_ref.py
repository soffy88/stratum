"""Canonical KnowledgeRef identity contract across A/B/C warehouses.

KnowledgeRef is the sole identity contract for knowledge objects across the
three warehouses:

    A = aii_kg       (ontology + service layer: stratum.*, aii.*)
    B = aii_refined  (refined knowledge: rf.*)
    C = aii_context  (learning/situational memory: cx.*)

Identity is (repository, object_type, object_id).  ``source_version`` is an
optional pin for reads but is NOT part of identity.  Text fields
(point_name, title, content, quotes) are NEVER part of identity — no text
matching is permitted anywhere in the system.
"""

from __future__ import annotations

from dataclasses import dataclass

REPOSITORY_A = "A"
REPOSITORY_B = "B"
REPOSITORY_C = "C"

REPOSITORIES = frozenset({REPOSITORY_A, REPOSITORY_B, REPOSITORY_C})

OBJECT_TYPES = frozenset(
    {
        "source",
        "fragment",
        "evidence",
        "claim",
        "concept",
        "relation",
        "note",
        "annotation",
        "learning_object",
        "skill",
        "ku",
        "kc",
        "substrate",
        "flashcard",
        "cornell_note",
        "learning_point",
    }
)


@dataclass(frozen=True)
class KnowledgeRef:
    """Canonical identity for a knowledge object across A/B/C warehouses.

    Identity = (repository, object_type, object_id).  ``source_version`` is
    an optional pin for reads but is NOT part of identity.  Text fields
    (point_name, title, content) are NEVER part of identity.
    """

    repository: str
    object_type: str
    object_id: str
    source_version: str | None = None

    def __post_init__(self) -> None:
        if self.repository not in REPOSITORIES:
            raise ValueError(
                f"repository must be one of {sorted(REPOSITORIES)}, got {self.repository!r}"
            )
        if not self.object_type:
            raise ValueError("object_type must not be empty")
        if not self.object_id:
            raise ValueError("object_id must not be empty")

    @property
    def identity(self) -> tuple[str, str, str]:
        """Identity tuple — source_version excluded."""
        return (self.repository, self.object_type, self.object_id)

    def to_dict(self) -> dict[str, str | None]:
        return {
            "repository": self.repository,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "source_version": self.source_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> KnowledgeRef:
        return cls(
            repository=d["repository"],
            object_type=d["object_type"],
            object_id=d["object_id"],
            source_version=d.get("source_version"),
        )

    def to_string(self) -> str:
        """Canonical string form: ``repository:object_type:object_id[@source_version]``."""
        base = f"{self.repository}:{self.object_type}:{self.object_id}"
        if self.source_version:
            base += f"@{self.source_version}"
        return base

    @classmethod
    def from_string(cls, s: str) -> KnowledgeRef:
        if "@" in s:
            base, version = s.rsplit("@", 1)
        else:
            base, version = s, None
        parts = base.split(":")
        if len(parts) != 3:
            raise ValueError(f"invalid KnowledgeRef string: {s!r}")
        return cls(
            repository=parts[0],
            object_type=parts[1],
            object_id=parts[2],
            source_version=version,
        )
