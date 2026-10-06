"""Concept evolution — spec §7.

§7.1 states the problem plainly: concepts are not static. A textbook introduces
`limit`, then `derivative`, then `integral`, and each later concept is defined in
terms of the earlier ones. P11 recorded 45 concept-evolution steps but only as a
count on the BU; it never said *which* concept changed, *how*, or *into what*.

This module makes a concept's life in one book explicit as a
``ConceptTrajectory``:

    concept, introduced_at, definitions, changes, applications, final_state

Four event kinds, per §7.3:

  INTRODUCTION  the concept first appears
  REFINEMENT    its definition changes
  EXPANSION     its scope of application widens
  CONNECTION    it is tied to another concept

§2.1 applies throughout: a trajectory is scoped to one run and one book. A
concept label here means "this concept, in this book". There is no canonical
concept identity and no cross-book key, so this cannot become the B warehouse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from stratum.knowledge.bu_v2_models import ChapterDelta, ChapterUnderstanding
from stratum.services.bu_v2_reasoning_graph import UnresolvedRelation, node_id

EventType = Literal["INTRODUCTION", "REFINEMENT", "EXPANSION", "CONNECTION"]

EVENT_TYPES: frozenset[str] = frozenset(
    {"INTRODUCTION", "REFINEMENT", "EXPANSION", "CONNECTION"}
)

# Words that signal a definition being restated rather than merely mentioned.
_DEFINITION_CUE = re.compile(
    r"(is defined as|we define|define[sd]?|definition|can be thought of as|"
    r"that is,|in other words|refined|more precisely|recall)",
    re.I,
)
# Words that signal a wider scope.
_EXPANSION_CUE = re.compile(
    r"(generaliz|general is|applies to|we use .{0,40} to|in the case of|"
    r"this allows us to|can also be used)",
    re.I,
)


@dataclass
class TrajectoryEvent:
    """One moment in a concept's life."""

    event_type: EventType
    chapter_id: str
    detail: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    sequence: int = 0

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError(
                f"unknown event {self.event_type!r}; §7.3 allows {sorted(EVENT_TYPES)}"
            )
        self.confidence = max(0.0, min(1.0, round(float(self.confidence), 4)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "chapter_id": self.chapter_id,
            "detail": self.detail,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence,
            "sequence": self.sequence,
        }


@dataclass
class ConceptTrajectory:
    """§7.2."""

    concept: str
    introduced_at: str = ""
    definitions: list[str] = field(default_factory=list)
    changes: list[TrajectoryEvent] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    final_state: str = ""
    events: list[TrajectoryEvent] = field(default_factory=list)
    confidence: float = 0.0
    unresolved: list[UnresolvedRelation] = field(default_factory=list)

    @property
    def trajectory_id(self) -> str:
        return node_id("traj", self.concept)

    @property
    def event_kinds(self) -> set[str]:
        return {e.event_type for e in self.events}

    @property
    def is_evolving(self) -> bool:
        """A concept that is introduced and later refined.

        The weaker of §13's two readings. `is_fully_evolving` adds application;
        both are reported because the two can disagree by a lot on a real book,
        and picking one silently would decide the gate by assertion.
        """
        return {"INTRODUCTION", "REFINEMENT"} <= self.event_kinds

    @property
    def is_fully_evolving(self) -> bool:
        """§13 as written: introduced, refined *and* applied.

        "Applied" means the concept did work somewhere else — an expansion or a
        connection to other concepts — rather than merely being restated.
        """
        return (
            {"INTRODUCTION", "REFINEMENT"} <= self.event_kinds
            and bool(self.event_kinds & {"EXPANSION", "CONNECTION"})
        )

    def kind_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.events:
            out[e.event_type] = out.get(e.event_type, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "introduced_at": self.introduced_at,
            "definitions": self.definitions[:10],
            "changes": [c.to_dict() for c in self.changes[:10]],
            "applications": self.applications[:10],
            "final_state": self.final_state,
            "event_counts": self.kind_counts(),
            "confidence": round(self.confidence, 4),
            "is_evolving": self.is_evolving,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class EvolutionResult:
    trajectories: list[ConceptTrajectory] = field(default_factory=list)
    unresolved: list[UnresolvedRelation] = field(default_factory=list)

    @property
    def evolving_count(self) -> int:
        return sum(1 for t in self.trajectories if t.is_evolving)

    @property
    def fully_evolving_count(self) -> int:
        """Introduced, refined and applied — §13's wording taken literally."""
        return sum(1 for t in self.trajectories if t.is_fully_evolving)

    def stats(self) -> dict[str, Any]:
        return {
            "trajectory_count": len(self.trajectories),
            "evolving_count": self.evolving_count,
            "fully_evolving_count": self.fully_evolving_count,
            "unresolved_count": len(self.unresolved),
            "with_refinement": sum(
                1 for t in self.trajectories if "REFINEMENT" in t.kind_counts()
            ),
            "with_expansion": sum(
                1 for t in self.trajectories if "EXPANSION" in t.kind_counts()
            ),
            "with_connection": sum(
                1 for t in self.trajectories if "CONNECTION" in t.kind_counts()
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats": self.stats(),
            "trajectories": [t.to_dict() for t in self.trajectories],
            "unresolved": [u.to_dict() for u in self.unresolved],
        }


class ConceptEvolutionBuilder:
    """§7: track a concept's life across the whole book, in document order."""

    def build(
        self,
        chapters: list[ChapterUnderstanding],
        *,
        run_id: str,
        book_id: str,
        deltas: list[ChapterDelta] | None = None,
        chapter_text: dict[str, str] | None = None,
    ) -> EvolutionResult:
        deltas = deltas or []
        result = EvolutionResult()

        # A delta may restate a concept explicitly; §7 wants those refinements
        # recorded even when no chapter claims to redefine it.
        refined_by: dict[str, list[tuple[int, str]]] = {}
        for d in deltas:
            for concept in d.revised_concepts_refs:
                refined_by.setdefault(concept, []).append((_num(d.chapter_id), d.chapter_id))

        ordered = sorted(chapters, key=lambda c: _num(c.chapter_id))
        seen: dict[str, ConceptTrajectory] = {}
        seq = 0

        for cu in ordered:
            chapter_num = _num(cu.chapter_id)
            body = (chapter_text or {}).get(cu.chapter_id, "")

            for concept in cu.concepts_introduced_refs:
                if not concept or len(concept.strip()) < 3:
                    continue
                traj = seen.get(concept)
                if traj is None:
                    traj = ConceptTrajectory(concept=concept, introduced_at=cu.chapter_id)
                    seen[concept] = traj
                    traj.events.append(
                        TrajectoryEvent(
                            event_type="INTRODUCTION",
                            chapter_id=cu.chapter_id,
                            detail=f"introduced in {cu.chapter_id}",
                            evidence_refs=[f"chapter:{cu.chapter_id}"],
                            confidence=0.9,
                            sequence=seq,
                        )
                    )
                    seq += 1
                    if cu.chapter_thesis:
                        traj.definitions.append(cu.chapter_thesis[:200])

            # Refinement: the chapter redefines something, or a delta says so.
            for concept in cu.concepts_redefined_refs:
                traj = seen.get(concept)
                if traj is None:
                    # §15: a refinement of a concept never introduced is a real
                    # gap in the record, not something to paper over.
                    result.unresolved.append(
                        UnresolvedRelation(
                            kind="refinement",
                            subject=f"{concept} in {cu.chapter_id}",
                            reason="concept is redefined but was never recorded as introduced",
                            source="producer",
                            confidence=0.4,
                            fallback="refinement recorded as an introduction",
                        )
                    )
                    traj = ConceptTrajectory(concept=concept, introduced_at=cu.chapter_id)
                    seen[concept] = traj
                    traj.events.append(
                        TrajectoryEvent(
                            event_type="INTRODUCTION",
                            chapter_id=cu.chapter_id,
                            detail=f"first recorded appearance, as a redefinition",
                            evidence_refs=[f"chapter:{cu.chapter_id}"],
                            confidence=0.5,
                            sequence=seq,
                        )
                    )
                    seq += 1

                locator = _definition_locator(body, concept)
                traj.changes.append(
                    TrajectoryEvent(
                        event_type="REFINEMENT",
                        chapter_id=cu.chapter_id,
                        detail=f"redefined in {cu.chapter_id}",
                        evidence_refs=[locator] if locator else [f"chapter:{cu.chapter_id}"],
                        confidence=0.7 if locator else 0.5,
                        sequence=seq,
                    )
                )
                traj.events.append(
                    TrajectoryEvent(
                        event_type="REFINEMENT",
                        chapter_id=cu.chapter_id,
                        detail=f"redefined in {cu.chapter_id}",
                        evidence_refs=[locator] if locator else [f"chapter:{cu.chapter_id}"],
                        confidence=0.7 if locator else 0.5,
                        sequence=seq,
                    )
                )
                seq += 1

            for concept, entries in refined_by.items():
                if not any(c == cu.chapter_id for _n, c in entries):
                    continue
                traj = seen.get(concept)
                if traj is None or "REFINEMENT" in {
                    e.event_type for e in traj.events if e.chapter_id == cu.chapter_id
                }:
                    continue
                traj.events.append(
                    TrajectoryEvent(
                        event_type="REFINEMENT",
                        chapter_id=cu.chapter_id,
                        detail=f"delta records a revision in {cu.chapter_id}",
                        evidence_refs=[f"delta:{cu.chapter_id}"],
                        confidence=0.65,
                        sequence=seq,
                    )
                )
                seq += 1

            # Expansion and connection, read from the text when it is available.
            if body:
                for concept, traj in seen.items():
                    if len(concept) < 4:
                        continue
                    pattern = r"\b" + re.escape(concept.lower()) + r"\b"
                    if not re.search(pattern, body.lower()):
                        continue
                    head = body[:4000]
                    if re.search(pattern, head.lower()) and _EXPANSION_CUE.search(head):
                        traj.applications.append(f"{cu.chapter_id}: applied")
                        traj.events.append(
                            TrajectoryEvent(
                                event_type="EXPANSION",
                                chapter_id=cu.chapter_id,
                                detail=f"applied in {cu.chapter_id}",
                                evidence_refs=[f"chapter:{cu.chapter_id}"],
                                confidence=0.6,
                                sequence=seq,
                            )
                        )
                        seq += 1
                        break

            # Connection: the chapter's dependencies tie concepts together.
            for dep in cu.dependencies_on_prior:
                if dep not in seen:
                    continue
                traj = seen[dep]
                for concept in cu.concepts_introduced_refs:
                    if concept and concept in seen and concept != dep:
                        traj.events.append(
                            TrajectoryEvent(
                                event_type="CONNECTION",
                                chapter_id=cu.chapter_id,
                                detail=f"connected to '{concept}' via {cu.chapter_id}'s stated dependency on '{dep}'",
                                evidence_refs=[f"dependency:{cu.chapter_id}->{dep}"],
                                confidence=0.55,
                                sequence=seq,
                            )
                        )
                        seq += 1
                        break

        for traj in seen.values():
            ordered_events = sorted(traj.events, key=lambda e: (e.sequence, _num(e.chapter_id)))
            traj.events = ordered_events
            traj.changes = [e for e in ordered_events if e.event_type in ("REFINEMENT", "EXPANSION")]
            traj.final_state = ordered_events[-1].detail if ordered_events else ""
            counts = traj.kind_counts()
            total = len(ordered_events)
            # A weighted mean over the event kinds present, divided by the total
            # event count so a long trajectory is not automatically confident.
            # The parenthesisation matters: only the last term was being divided
            # before, which let confidence reach 1.6 and violate the CHECK.
            strength = (
                0.9 * (1 if counts.get("INTRODUCTION") else 0)
                + 0.7 * min(1, counts.get("REFINEMENT", 0))
                + 0.5 * min(1, counts.get("EXPANSION", 0))
                + 0.4 * min(1, counts.get("CONNECTION", 0))
            )
            traj.confidence = round(min(1.0, max(0.0, strength / max(1, total))), 4)
            traj.unresolved = list(result.unresolved)

        result.trajectories = sorted(
            seen.values(), key=lambda t: (-t.confidence, t.concept)
        )
        return result


def _definition_locator(body: str, concept: str) -> str | None:
    """Locate where a chapter defines a concept, for evidence on a refinement."""
    if not body or not concept:
        return None
    pattern = re.compile(re.escape(concept.lower()))
    for m in pattern.finditer(body.lower()):
        window = body[max(0, m.start() - 120) : m.start() + 160]
        if _DEFINITION_CUE.search(window):
            return f"char:{m.start()} in {concept}"
    return None


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0
