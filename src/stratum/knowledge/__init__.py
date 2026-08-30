"""AII Knowledge Constitutional layer.

Canonical product name: AII
Canonical store: PostgreSQL + pgvector (stratum + aii schemas in aii_kg)
Projections are rebuildable, never authority.
"""

from stratum.knowledge.contract import (
    CANONICAL_OBJECTS,
    AUTHORITY_MAP,
    WRITER_MAP,
    PROVENANCE_GRAPH,
    OBJECT_CONTRACTS,
)
from stratum.knowledge.provenance import validate_provenance

__all__ = [
    "CANONICAL_OBJECTS",
    "AUTHORITY_MAP",
    "WRITER_MAP",
    "PROVENANCE_GRAPH",
    "OBJECT_CONTRACTS",
    "validate_provenance",
]
