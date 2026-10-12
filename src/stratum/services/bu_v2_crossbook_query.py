"""P14: Cross-Book Query API.

Provides query interface for cross-book intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from stratum.knowledge.bu_v2_models import (
    CrossBookCollection,
    CrossBookConcept,
    CrossBookConceptRelation,
    CrossBookContradiction,
    CrossBookKnowledgeGap,
    CrossBookProblem,
    CrossBookSynthesis,
    CrossBookThesis,
    CrossBookUnderstanding,
)


@dataclass
class QueryResult:
    """Result of a cross-book query."""

    items: list[Any] = field(default_factory=list)
    total: int = 0
    query: str = ""
    traceability: dict[str, list[str]] = field(default_factory=dict)


class BU2CrossBookQuery:
    """Query interface for cross-book intelligence."""

    def __init__(self, understanding: CrossBookUnderstanding):
        self.understanding = understanding

    def compare_books(
        self,
        book_a_id: str,
        book_b_id: str,
    ) -> QueryResult:
        """Get comparison between two specific books."""
        for comp in self.understanding.comparisons:
            if (comp.book_a_id == book_a_id and comp.book_b_id == book_b_id) or \
               (comp.book_a_id == book_b_id and comp.book_b_id == book_a_id):
                return QueryResult(
                    items=[comp],
                    total=1,
                    query=f"compare({book_a_id}, {book_b_id})",
                    traceability=comp.__dict__.get("traceability", {}),
                )
        return QueryResult(items=[], total=0, query=f"compare({book_a_id}, {book_b_id})")

    def find_shared_concepts(self, relation_filter: str | None = None) -> QueryResult:
        """Find concepts shared across books."""
        items = []
        for rel in self.understanding.concept_relations:
            if relation_filter is None or rel.relation.value == relation_filter:
                items.append(rel)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"shared_concepts({relation_filter or 'all'})",
            traceability=self._collect_traceability(items),
        )

    def find_concept_differences(self, relation_filter: str | None = None) -> QueryResult:
        """Find concept differences (same term, different meaning)."""
        items = []
        for rel in self.understanding.concept_relations:
            if rel.relation.value in ("SAME_TERM_DIFFERENT_MEANING", "RELATED_CONCEPT"):
                if relation_filter is None or rel.relation.value == relation_filter:
                    items.append(rel)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"concept_differences({relation_filter or 'all'})",
            traceability=self._collect_traceability(items),
        )

    def find_thesis_conflicts(self) -> QueryResult:
        """Find thesis conflicts across books."""
        items = []
        for rel in self.understanding.thesis_relations:
            if rel.relation.value in ("CONTRADICTS", "ALTERNATIVE"):
                items.append(rel)

        return QueryResult(
            items=items,
            total=len(items),
            query="thesis_conflicts",
            traceability=self._collect_traceability(items),
        )

    def find_supporting_books(self, thesis_statement: str) -> QueryResult:
        """Find books whose theses support a given statement."""
        items = []
        # Would need semantic matching - for now return supporting relations
        for rel in self.understanding.thesis_relations:
            if rel.relation.value == "SUPPORTS":
                items.append(rel)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"supporting_books('{thesis_statement[:50]}...')",
            traceability=self._collect_traceability(items),
        )

    def find_contradictions(self, type_filter: str | None = None) -> QueryResult:
        """Find all contradictions across books."""
        items = []
        for c in self.understanding.contradictions:
            if type_filter is None or c.type.value == type_filter:
                items.append(c)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"contradictions({type_filter or 'all'})",
            traceability=self._collect_traceability(items),
        )

    def find_crossbook_arguments(self, relation_filter: str | None = None) -> QueryResult:
        """Find cross-book argument relations."""
        items = []
        for rel in self.understanding.argument_relations:
            if relation_filter is None or rel.relation.value == relation_filter:
                items.append(rel)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"crossbook_arguments({relation_filter or 'all'})",
            traceability=self._collect_traceability(items),
        )

    def find_knowledge_gaps(self, type_filter: str | None = None) -> QueryResult:
        """Find knowledge gaps across the collection."""
        items = []
        for gap in self.understanding.knowledge_gaps:
            if type_filter is None or gap.type.value == type_filter:
                items.append(gap)

        return QueryResult(
            items=items,
            total=len(items),
            query=f"knowledge_gaps({type_filter or 'all'})",
            traceability=self._collect_traceability(items),
        )

    def get_crossbook_synthesis(self) -> QueryResult:
        """Get the full cross-book synthesis."""
        return QueryResult(
            items=[self.understanding.synthesis] if self.understanding.synthesis else [],
            total=1 if self.understanding.synthesis else 0,
            query="crossbook_synthesis",
            traceability=self.understanding.synthesis.traceability if self.understanding.synthesis else {},
        )

    def _collect_traceability(self, items: list[Any]) -> dict[str, list[str]]:
        """Collect traceability from a list of items."""
        traceability = {}
        for item in items:
            if hasattr(item, 'relation_id'):
                traceability[item.relation_id] = getattr(item, 'traceability', [])
            elif hasattr(item, 'gap_id'):
                traceability[item.gap_id] = getattr(item, 'affected_books', [])
            elif hasattr(item, 'contradiction_id'):
                traceability[item.contradiction_id] = [getattr(item, 'book_a_id', ''), getattr(item, 'book_b_id', '')]
        return traceability


class BU2CrossBookQueryBuilder:
    """Builder for creating query objects from understanding."""

    def __init__(self, understanding: CrossBookUnderstanding):
        self.understanding = understanding

    def query(self) -> BU2CrossBookQuery:
        return BU2CrossBookQuery(self.understanding)