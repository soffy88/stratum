"""Book expression — spec §13.

Six sections, each answering a specific question about the book. The spec asks
for expression rather than summary, and the difference is that a summary
restates content while an expression answers a question about the whole.

Two design decisions matter:

**Expression is not persisted.** §13 wants an artifact, and giving it a table
would create a second authority for what a book says — a second thing to keep in
sync with ``book_understandings_v2``, and a second thing that could disagree
with it. So expression is computed from the BU on demand, and the BU stays the
only stored account. This mirrors how P7 of A仓 stores a projection as JSON
specifically to avoid a second authority.

**The BU is the only input.** §13.6 asks what the book contributes relative to
existing knowledge. Answering that well would require reading the literature,
which is out of scope and would be unverifiable, so this section states the
book's own novel commitments and names explicitly when the relative claim cannot
be supported from the book alone. An honest "not determinable from this book" is
better than a fabricated novelty claim, which is the same failure the
verification gate exists to prevent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import BookUnderstandingV2


@dataclass
class BookExpression:
    """§13's six sections. The whole deliverable, and nothing more."""

    book_id: str
    run_id: str
    essence: str = ""
    world_model: str = ""
    core_mechanisms: list[str] = field(default_factory=list)
    logical_architecture: str = ""
    boundary: str = ""
    contribution: str = ""
    # Provenance, so an expression can be traced back rather than trusted.
    source_bu_id: str = ""
    grounded_section_count: int = 0
    ungrounded_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        """Human-readable form. Used by the CLI and the acceptance report."""
        lines = [
            "=" * 72,
            "BOOK EXPRESSION",
            f"book_id={self.book_id}  run_id={self.run_id}  bu={self.source_bu_id}",
            "=" * 72,
            "",
            "BOOK ESSENCE — what problem does this book try to solve?",
            f"  {self.essence or '(none recorded)'}",
            "",
            "WORLD MODEL — how does the author explain the world?",
            f"  {self.world_model or '(none recorded)'}",
            "",
            "CORE MECHANISMS — what are the causal mechanisms?",
        ]
        lines += [f"  - {m}" for m in self.core_mechanisms] or ["  (none recorded)"]
        lines += [
            "",
            "LOGICAL ARCHITECTURE — how is the thought organised?",
            f"  {self.logical_architecture or '(none recorded)'}",
            "",
            "BOUNDARY — where does it hold, where does it fail?",
            f"  {self.boundary or '(none recorded)'}",
            "",
            "CONTRIBUTION — what does it add?",
            f"  {self.contribution or '(none recorded)'}",
        ]
        if self.ungrounded_sections:
            lines += [
                "",
                "NOT GROUNDED IN THIS BOOK (stated, not inferred):",
            ] + [f"  - {s}" for s in self.ungrounded_sections]
        return "\n".join(lines)


class BUExpressionGenerator:
    """Derive a book expression from a verified or draft BU.

    Pure function of its input: the same BU always yields the same expression.
    That is what lets the acceptance gate compare a re-run's output byte for
    byte instead of asking whether it "looks similar".
    """

    def generate(self, bu: BookUnderstandingV2) -> BookExpression:
        exp = BookExpression(
            book_id=bu.book_id,
            run_id=bu.run_id,
            source_bu_id=bu.id,
        )

        # §13.1 essence — from the questions the book says it answers.
        if bu.governing_questions:
            exp.essence = (
                "This book sets out to answer: "
                + "; ".join(q.rstrip(".") for q in bu.governing_questions[:3])
                + "."
            )
            exp.grounded_section_count += 1
        else:
            exp.ungrounded_sections.append("essence: the book records no governing question")

        # §13.2 world model — the author's framing, as recorded at integration.
        world = bu.concept_system.get("mental_model") if isinstance(bu.concept_system, dict) else None
        if world:
            exp.world_model = str(world)
            exp.grounded_section_count += 1
        elif bu.central_theses:
            exp.world_model = (
                "The author's account can be reconstructed from the theses the book defends: "
                + "; ".join(t.rstrip(".") for t in bu.central_theses[:3])
                + "."
            )
            exp.grounded_section_count += 1
        else:
            exp.ungrounded_sections.append("world model: neither a mental model nor theses were recorded")

        # §13.3 core mechanisms. The BU does not carry a mechanism list of its
        # own — mechanisms are recorded per chapter — so they are collected from
        # the chapter understandings at integration time. When that collection
        # is empty the section says so rather than substituting a summary.
        mechanisms = bu.concept_system.get("mechanisms", []) if isinstance(bu.concept_system, dict) else []
        exp.core_mechanisms = _dedupe([m for m in mechanisms if isinstance(m, str)])[:12]
        if exp.core_mechanisms:
            exp.grounded_section_count += 1
        else:
            exp.ungrounded_sections.append(
                "core mechanisms: chapters recorded mechanisms that could not be carried to the book level"
            )

        # §13.4 logical architecture — from the derived dependency graph, which
        # is structure rather than prose.
        edges = getattr(bu.chapter_dependency_graph, "dependencies", []) or []
        if edges:
            chain = " -> ".join(
                sorted({d.source_chapter for d in edges})
                + [max((d.target_chapter for d in edges), key=lambda c: _num(c))]
            )
            exp.logical_architecture = (
                f"The book is organised as a dependency chain of {len(edges)} "
                f"prerequisite relations across {len(bu.concept_system.get('concepts', {}))} concepts; "
                f"the derived order runs {chain}."
            )
            exp.grounded_section_count += 1
        else:
            exp.logical_architecture = (
                "No prerequisite structure was derived: chapters recorded no dependencies "
                "on concepts introduced earlier."
            )
            exp.ungrounded_sections.append("logical architecture: no dependency edges derived")

        # §13.5 boundary — from recorded limitations and open problems.
        nk = bu.negative_knowledge
        parts: list[str] = []
        if nk.limitations:
            parts.append("Stated limits: " + "; ".join(nk.limitations[:3]))
        if nk.open_problems:
            parts.append("Open problems: " + "; ".join(nk.open_problems[:3]))
        if nk.unresolved_conflicts:
            parts.append("Unresolved: " + "; ".join(nk.unresolved_conflicts[:3]))
        if parts:
            exp.boundary = " | ".join(parts)
            exp.grounded_section_count += 1
        else:
            exp.ungrounded_sections.append("boundary: the book records no limitations")

        # §13.6 contribution — only what the book itself can support.
        novel = [s for s in (bu.concept_evolution or []) if getattr(s, "evolution_type", "") == "REFINE"]
        if novel:
            exp.contribution = (
                f"Within the book, {len(novel)} concept(s) are refined after first "
                f"definition; the book advances its own subject by "
                + "; ".join(f"redefining {n.concept_ref}" for n in novel[:3])
                + ". Novelty relative to the existing literature cannot be "
                "determined from this book alone and is not claimed here."
            )
            exp.grounded_section_count += 1
        else:
            exp.contribution = (
                "Not determinable from this book alone. A contribution claim is "
                "relative to prior work, and this BU records no comparison against it."
            )
            exp.ungrounded_sections.append("contribution: no cross-book comparison is available")

        return exp


def _num(s: str) -> int:
    d = "".join(c for c in (s or "") if c.isdigit())
    return int(d) if d else 0


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out