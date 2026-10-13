"""Dependency-ordered learning guide — task E.

The audit's expression score was 5/10 because the output described the book but
did not help a reader *learn* it: there was no ordered path from the book's
foundations to its results. This module derives one from the reasoning graph and
the concept system.

The guide is a topological ordering of concepts by their ``DEPENDS_ON`` /
``EXTENDS`` edges, grouped under the chapters that introduce them, so a reader
sees "to understand Taylor series you first need sequences, then series, then
polynomials". Concepts with no incoming dependency edge come first; a cycle is
broken deterministically and recorded rather than dropped.

The guide is a rendering of a verified BU — like the expression, it is computed
on demand and never persisted, so it cannot become a second authority for what
the book says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stratum.services.bu_v2_concept_filter import display_label, is_noise_concept


@dataclass
class GuideStep:
    """One concept in the learning path."""

    concept: str
    chapter_id: str
    ku_id: str = ""
    kind: str = "CONCEPT"
    requires: list[str] = field(default_factory=list)
    quote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "chapter_id": self.chapter_id,
            "ku_id": self.ku_id,
            "kind": self.kind,
            "requires": self.requires,
            "quote": self.quote,
        }


@dataclass
class LearningGuide:
    """A dependency-ordered path through a book's concepts."""

    book_id: str
    run_id: str
    steps: list[GuideStep] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)
    # chapter_id -> the concepts it introduces, in guide order.
    by_chapter: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "run_id": self.run_id,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "by_chapter": self.by_chapter,
            "cycles": self.cycles,
        }

    def render(self) -> str:
        lines = [
            "=" * 72,
            "LEARNING GUIDE (dependency-ordered)",
            f"book_id={self.book_id}  run_id={self.run_id}",
            "=" * 72,
            "",
        ]
        if not self.steps:
            lines.append("  (no concepts were ordered; the graph had no concept nodes)")
            return "\n".join(lines)
        current_chapter = None
        for s in self.steps:
            if s.chapter_id != current_chapter:
                current_chapter = s.chapter_id
                lines.append(f"\n[{current_chapter}]")
            req = f"  (after: {', '.join(s.requires[:3])})" if s.requires else ""
            lines.append(f"  - {s.concept}{req}")
        if self.cycles:
            lines += ["", "DEPENDENCY CYCLES (broken deterministically):"]
            lines += [f"  - {c}" for c in self.cycles]
        return "\n".join(lines)


class LearningGuideBuilder:
    """Build a learning guide from a reasoning graph and the run's chapters."""

    def build(
        self,
        *,
        run_id: str,
        book_id: str,
        graph: Any = None,
        chapters: list[Any] | None = None,
        ku_index: Any = None,
    ) -> LearningGuide:
        chapters = chapters or []
        guide = LearningGuide(book_id=book_id, run_id=run_id)

        # Collect concept nodes from the reasoning graph.
        concept_nodes: dict[str, Any] = {}
        requires: dict[str, list[str]] = {}
        if graph is not None:
            for node in graph.nodes.values():
                if node.node_type in ("CONCEPT", "THEOREM") and not is_noise_concept(
                    node.label, (node.metadata or {}).get("kind", "")
                ):
                    concept_nodes[node.node_id] = node
            for edge in graph.edges:
                if edge.relation_type in ("DEPENDS_ON", "EXTENDS", "REFINES", "APPLIES_TO"):
                    if (
                        edge.source_node_id in concept_nodes
                        and edge.target_node_id in concept_nodes
                    ):
                        requires.setdefault(edge.source_node_id, []).append(edge.target_node_id)

        if not concept_nodes:
            # Fall back to the chapter concept lists in document order.
            return self._from_chapters(chapters, guide)

        # Topological order (Kahn), ties broken by chapter order then label.
        order_index = {c.chapter_id: i for i, c in enumerate(chapters)}
        labels = {nid: display_label(node.label) for nid, node in concept_nodes.items()}

        def sort_key(nid: str) -> tuple[int, str]:
            node = concept_nodes[nid]
            return (order_index.get(node.chapter_id, 999), labels[nid].lower())

        # in-degree of X = number of prerequisites X needs (its requires list).
        # A node becomes ready once every prerequisite has been emitted.
        incoming = {nid: 0 for nid in concept_nodes}
        dependents: dict[str, list[str]] = {}
        for src, targets in requires.items():
            for t in targets:
                if t in incoming:
                    incoming[src] += 1
                    dependents.setdefault(t, []).append(src)
        ready = sorted([nid for nid, d in incoming.items() if d == 0], key=sort_key)
        ordered: list[str] = []
        seen: set[str] = set()
        while ready:
            nid = ready.pop(0)
            if nid in seen:
                continue
            seen.add(nid)
            ordered.append(nid)
            for t in dependents.get(nid, []):
                if t in incoming:
                    incoming[t] -= 1
                    if incoming[t] == 0:
                        ready.append(t)
                    ready.sort(key=sort_key)
        # Any node left is in a cycle; record and append deterministically.
        leftover = sorted([n for n in concept_nodes if n not in seen], key=sort_key)
        if leftover:
            guide.cycles.append(
                f"{len(leftover)} concept(s) in a dependency cycle: "
                + ", ".join(labels[n] for n in leftover[:6])
            )
            ordered.extend(leftover)

        for nid in ordered:
            node = concept_nodes[nid]
            step = GuideStep(
                concept=labels[nid],
                chapter_id=node.chapter_id,
                ku_id=(node.metadata or {}).get("ku_id", ""),
                kind=node.node_type,
                requires=[labels[t] for t in requires.get(nid, []) if t in labels][:5],
                quote=(node.metadata or {}).get("quote", ""),
            )
            guide.steps.append(step)
            guide.by_chapter.setdefault(node.chapter_id, []).append(labels[nid])
        return guide

    @staticmethod
    def _from_chapters(chapters: list[Any], guide: LearningGuide) -> LearningGuide:
        for c in chapters:
            for concept in c.concepts_introduced_refs:
                if not concept or is_noise_concept(concept):
                    continue
                guide.steps.append(GuideStep(concept=concept, chapter_id=c.chapter_id))
                guide.by_chapter.setdefault(c.chapter_id, []).append(concept)
        return guide
