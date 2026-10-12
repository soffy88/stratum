"""Cross-chapter dependency graph — spec §6.

§6 forbids the model from asserting "chapter A depends on chapter B" without a
reason and evidence. So this module does not ask a model for chapter relations at
all. It finds relations that are already written in the book.

The signal, measured on the trial text:

    "Here we state the general version of the rule, but postpone its proof
     until Chapter 7."                              ch3 -> ch7
    "We encountered another type of vector field in Chapter 13."   ch16 -> ch13

66 distinct explicit cross-chapter references, each a verbatim string at a known
character offset. An author's explicit forward or backward reference *is* the
reason and the evidence, which is exactly what §6 asks to be present.

P11 asked a 7B model what depends on what and got one edge. That result is the
justification for this approach, not a coincidence of wording.

Three edge kinds are produced, in descending strength:

  REFERENCE   the text says "Chapter N"                     DIRECT
  CONCEPT_USE an earlier chapter's own concept recurs     DERIVED
  SEQUENCE    neither signal fired, but ordering implies
              a chapter follows what precedes it          DERIVED, low confidence

SEQUENCE exists because §13 requires dependency ≥ chapter_count/2 and a book with
no explicit cross-references should still get a graph. Those edges are marked
DERIVED at low confidence and counted separately, so they cannot masquerade as
author-stated relations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import ChapterDependency, ChapterUnderstanding
from stratum.services.bu_v2_reasoning_graph import (
    BookReasoningGraph,
    ReasoningEdge,
    ReasoningNode,
    UnresolvedRelation,
    node_id,
)

# "Chapter 7", "chapter seven" is not attempted; numerals are what textbooks use
# for cross-references and what the parser index provides.
_CHAPTER_REF = re.compile(r"\b[Cc]hapter\s+(\d{1,2})\b")

# Contexts that mean "I am relying on chapter N", which are stronger evidence
# than a bare mention of the string.
# Measured against how authors actually write: "defer X until Chapter 3",
# "postpone its proof until Chapter 7", "we return to this in Chapter 2". The
# first two drafts missed "defer" and "return to", which are among the commonest.
_DEPENDENCY_CONTEXT = re.compile(
    r"(postpone|defer|return to|revisit|come back to|as (?:we|shown|before)"
    r"|we (?:saw|have seen|introduced|defined|encountered|used|applied)"
    r"|requires?|depends?|assume[sd]?|previously|earlier|before|build(?:s|ing)? on"
    r"|general(?:isation|ization) of|extends?|generalizes?|rel(?:y|ies|ied) on"
    r"|follows? from|consequence of|based on)",
    re.I,
)

_SUPPORT_CONTEXT = re.compile(r"\bsummar(?:y|ies|ise|izes)|in summary|therefore|thus\b", re.I)

# A window for the reference: close enough that the clause describes the
# reference, far enough to carry the verb.
_REF_WINDOW_BEFORE = 160
_REF_WINDOW_AFTER = 120


@dataclass
class DependencyBuildResult:
    """§6 output plus the §15 record of what was not established."""

    graph: BookReasoningGraph
    dependencies: list[ChapterDependency] = field(default_factory=list)
    explicit_edges: list[ReasoningEdge] = field(default_factory=list)
    derived_edges: list[ReasoningEdge] = field(default_factory=list)
    sequence_edges: list[ReasoningEdge] = field(default_factory=list)
    unresolved: list[UnresolvedRelation] = field(default_factory=list)

    @property
    def cross_chapter_count(self) -> int:
        return len([e for e in self.graph.edges if self._is_cross_chapter(e)])

    @property
    def asserted_cross_chapter_count(self) -> int:
        """Cross-chapter relations the author stated or the text demonstrates.

        The sequence fallback (document order, confidence 0.21, uncertain) is
        deliberately excluded: it is reported in the graph but must not clear
        §13's threshold, which asks for *effective* relations. Same rule as
        Q10's density; kept here so the gate and the dimension cannot disagree.
        """
        return len(
            [e for e in self.graph.edges if self._is_cross_chapter(e) and e.status == "asserted"]
        )

    def _is_cross_chapter(self, edge: ReasoningEdge) -> bool:
        s = self.graph.nodes.get(edge.source_node_id)
        t = self.graph.nodes.get(edge.target_node_id)
        return bool(s and t and s.chapter_id and t.chapter_id and s.chapter_id != t.chapter_id)

    def stats(self) -> dict[str, Any]:
        return {
            "dependency_count": len(self.dependencies),
            "cross_chapter_count": self.cross_chapter_count,
            "explicit_reference_edges": len(self.explicit_edges),
            "concept_use_edges": len(self.derived_edges),
            "sequence_edges": len(self.sequence_edges),
            "unresolved_count": len(self.unresolved),
            "chapter_count": len(self.graph.nodes_of_type("CHAPTER")),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats": self.stats(),
            "dependencies": [
                {
                    "source_chapter": d.source_chapter,
                    "target_chapter": d.target_chapter,
                    "relation": d.relation,
                }
                for d in self.dependencies
            ],
            "unresolved": [u.to_dict() for u in self.unresolved],
        }


class DependencyBuilder:
    """§6: ChapterUnderstanding[] in, a dependency graph out."""

    def build(
        self,
        chapters: list[ChapterUnderstanding],
        *,
        run_id: str,
        book_id: str,
        chapter_text: dict[str, str] | None = None,
        allow_sequence_fallback: bool = True,
    ) -> DependencyBuildResult:
        """Build cross-chapter dependencies.

        ``chapter_text`` is required for reference and concept signals. Without
        it only the sequence fallback is available, and every edge says so — a
        graph built from ordering alone is honestly labelled rather than
        presented as if the author had stated the relation.
        """
        graph = BookReasoningGraph(
            graph_id=node_id("graph", run_id, book_id, "reasoning"), run_id=run_id, book_id=book_id
        )

        # Chapter nodes first: an edge without endpoints cannot be recorded, and
        # §15 wants that recorded rather than silently skipped.
        by_number: dict[int, str] = {}
        for cu in chapters:
            if _num(cu.chapter_id) > 100:  # back matter section, not a numbered chapter
                continue
            nid = node_id("n", run_id, cu.chapter_id)
            graph.add_node(
                ReasoningNode(
                    node_id=nid,
                    node_type="CHAPTER",
                    label=cu.chapter_id,
                    chapter_id=cu.chapter_id,
                    source_ref=cu.chapter_id,
                    confidence=1.0,
                    metadata={"thesis": cu.chapter_thesis[:200]},
                )
            )
            by_number[_num(cu.chapter_id)] = nid

        result = DependencyBuildResult(graph=graph)

        if chapter_text:
            self._add_reference_edges(result, by_number, chapter_text)
            self._add_concept_use_edges(result, by_number, chapters, chapter_text)

        if allow_sequence_fallback:
            self._add_sequence_edges(result, by_number)

        result.dependencies = [
            ChapterDependency(
                source_chapter=graph.nodes[e.source_node_id].chapter_id,
                target_chapter=graph.nodes[e.target_node_id].chapter_id,
                relation=e.relation_type,
            )
            for e in graph.edges
            if result._is_cross_chapter(e)
        ]
        result.unresolved = list(graph.unresolved)
        return result

    # ── explicit author references ─────────────────────────────────────────

    def _add_reference_edges(
        self,
        result: DependencyBuildResult,
        by_number: dict[int, str],
        chapter_text: dict[str, str],
    ) -> None:
        """Edges the author stated outright, each quoting the text."""
        for chapter_id, text in chapter_text.items():
            src_num = _num(chapter_id)
            src = by_number.get(src_num)
            if not src or not text:
                continue
            seen: set[int] = set()
            for m in _CHAPTER_REF.finditer(text):
                tgt_num = int(m.group(1))
                if tgt_num == src_num or tgt_num not in by_number or tgt_num in seen:
                    continue
                # Only a forward or backward reference that actually points
                # somewhere real in this book.
                seen.add(tgt_num)
                before = text[max(0, m.start() - _REF_WINDOW_BEFORE) : m.start()]
                after = text[m.end() : m.end() + _REF_WINDOW_AFTER]
                quote = text[max(0, m.start() - 90) : m.end() + 60].strip().replace("\n", " ")
                locator = f"char:{m.start()} in {chapter_id}"

                dependency = bool(
                    _DEPENDENCY_CONTEXT.search(before) or _DEPENDENCY_CONTEXT.search(after)
                )
                support = bool(_SUPPORT_CONTEXT.search(before) or _SUPPORT_CONTEXT.search(after))

                if dependency:
                    edge = self._edge(
                        result,
                        src,
                        by_number[tgt_num],
                        "DEPENDS_ON",
                        reason=f"{chapter_id} states a dependence on chapter {tgt_num}: ...{quote[:160]}",
                        evidence=[locator],
                        evidence_type="DIRECT",
                        confidence=0.92,
                    )
                    result.explicit_edges.append(edge)
                elif support:
                    edge = self._edge(
                        result,
                        src,
                        by_number[tgt_num],
                        "SUPPORTS",
                        reason=f"{chapter_id} draws on chapter {tgt_num}: ...{quote[:160]}",
                        evidence=[locator],
                        evidence_type="DIRECT",
                        confidence=0.85,
                    )
                    result.explicit_edges.append(edge)
                else:
                    # The reference exists but the surrounding clause does not
                    # say why. §15: keep it, marked uncertain, rather than
                    # asserting a dependence the author did not state.
                    graph = result.graph
                    graph.record_unresolved(
                        UnresolvedRelation(
                            kind="reference",
                            subject=f"{chapter_id} -> ch{tgt_num}",
                            reason=(
                                f"text references chapter {tgt_num} at {locator} but the "
                                "surrounding clause states no dependence"
                            ),
                            source="text_reference",
                            confidence=0.35,
                            fallback="recorded as an explicit mention; no relation asserted",
                        )
                    )

    # ── concept recurrence ─────────────────────────────────────────────────

    def _add_concept_use_edges(
        self,
        result: DependencyBuildResult,
        by_number: dict[int, str],
        chapters: list[ChapterUnderstanding],
        chapter_text: dict[str, str],
    ) -> None:
        """A concept introduced in one chapter and used in a later one.

        Weaker than an explicit reference, so it is DERIVED and lower confidence.
        The count is capped per target chapter: a concept mentioned 328 times
        is one relation, not 328, and inflating the count would let §13's
        dependency threshold be met by repetition rather than structure.
        """
        intro: dict[str, int] = {}
        for cu in chapters:
            for concept in cu.concepts_introduced_refs:
                key = _norm(concept)
                if key and len(key) >= 4 and key not in intro:
                    intro[key] = _num(cu.chapter_id)

        per_target: dict[int, int] = {}
        MAX_PER_TARGET = 4

        for cu in chapters:
            src_num = _num(cu.chapter_id)
            src = by_number.get(src_num)
            body = (chapter_text.get(cu.chapter_id) or "").lower()
            if not src or not body:
                continue
            # Every concept earlier chapters introduced, checked against this
            # chapter's text. Iterating this chapter's own introduced concepts
            # instead — which is what this did first — guarantees owner >= src_num
            # and so produces no edge at all.
            for term, owner in sorted(intro.items()):
                if owner >= src_num:
                    continue
                concept = term
                if len(term) < 4:
                    continue
                occurrences = len(re.findall(r"\b" + re.escape(term.lower()) + r"\b", body))
                if occurrences < 3:
                    continue
                if per_target.get(owner, 0) >= MAX_PER_TARGET:
                    continue
                per_target[owner] = per_target.get(owner, 0) + 1
                edge = self._edge(
                    result,
                    src,
                    by_number[owner],
                    "DEPENDS_ON",
                    reason=(
                        f"{cu.chapter_id} uses '{term}', introduced in chapter {owner}, "
                        f"{occurrences} times"
                    ),
                    evidence=[f"concept:{term}@ch{owner}"],
                    evidence_type="DERIVED",
                    confidence=0.55,
                )
                result.derived_edges.append(edge)

    # ── ordering fallback ──────────────────────────────────────────────────

    def _add_sequence_edges(self, result: DependencyBuildResult, by_number: dict[int, str]) -> None:
        """The weakest signal: a chapter follows another.

        Present so a book with no explicit cross-references still yields a graph
        rather than an empty one. Every such edge is DERIVED at low confidence,
        so a reader can tell it from an author-stated relation, and §13's count
        can be reported separately.
        """
        ordered = sorted(by_number.items())
        for (num_a, node_a), (num_b, node_b) in zip(ordered, ordered[1:]):
            edge = self._edge(
                result,
                node_b,
                node_a,
                "DEPENDS_ON",
                reason=(
                    f"chapter {num_b} follows chapter {num_a} in the book; no explicit "
                    "reference or concept recurrence was found"
                ),
                evidence=[f"order:{node_a}->{node_b}"],
                evidence_type="DERIVED",
                # Deliberately low. This is document order, not a claim about
                # the author's reasoning.
                confidence=0.21,
                status="uncertain",
            )
            result.sequence_edges.append(edge)

    @staticmethod
    def _edge(
        result: DependencyBuildResult,
        source: str,
        target: str,
        relation: str,
        *,
        reason: str,
        evidence: list[str],
        evidence_type: str,
        confidence: float,
        status: str = "asserted",
    ) -> ReasoningEdge:
        """Construct and attach an edge.

        The graph is threaded through ``result`` rather than held on the builder:
        one builder is reused across books in the test suite, and instance state
        would leak between them.
        """
        edge = ReasoningEdge(
            edge_id=node_id("e", source, target, relation),
            source_node_id=source,
            target_node_id=target,
            relation_type=relation,  # type: ignore[arg-type]
            reason=reason,
            evidence_refs=evidence,
            evidence_type=evidence_type,  # type: ignore[arg-type]
            confidence=confidence,
            status=status,  # type: ignore[arg-type]
        )
        added = result.graph.add_edge(edge)
        return added if added is not None else edge


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum() or c.isspace()).strip()


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0
