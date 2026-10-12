"""P13: Query API.

Read-only query interface for BookSynthesis components.
All queries read from BookUnderstandingV2 and P13 component tables.
"""

from __future__ import annotations

from typing import Any, Optional

from stratum.knowledge.bu_v2_models import (
    BookAuthorModel,
    BookSynthesis,
    BookThesisModel,
)
from stratum.db import read, query


class BU2Query:
    """Read-only query API for P13 synthesis components."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._bu_cache: Optional[dict] = None
        self._synthesis_cache: Optional[BookSynthesis] = None

    def _get_bu(self) -> Optional[dict]:
        if self._bu_cache is None:
            rows = query(
                "SELECT * FROM book_understandings_v2 WHERE run_id = %(run_id)s ORDER BY version DESC LIMIT 1",
                {"run_id": self.run_id},
            )
            self._bu_cache = rows[0] if rows else None
        return self._bu_cache

    def _get_synthesis(self) -> Optional[BookSynthesis]:
        if self._synthesis_cache is None:
            row = read("book_syntheses", self.run_id)
            if row:
                self._synthesis_cache = BookSynthesis(**row)
        return self._synthesis_cache

    def get_book_thesis(self) -> Optional[BookThesisModel]:
        """Get the book's thesis model."""
        synth = self._get_synthesis()
        if synth:
            return synth.thesis
        return None

    def get_core_concepts(self, role: str | None = None) -> list[dict]:
        """Get core concepts, optionally filtered by role."""
        synth = self._get_synthesis()
        if not synth:
            return []
        concepts: list[Any] = []
        if role:
            role_attr = role.lower()
            if hasattr(synth.concept_system, role_attr):
                concepts = getattr(synth.concept_system, role_attr, [])
        else:
            concepts = synth.concept_system.all_concepts()
        return [c.model_dump() for c in concepts]

    def get_argument_map(self) -> list[dict]:
        """Get the complete argument map."""
        synth = self._get_synthesis()
        if not synth:
            return []
        args = []
        for a in synth.argument_system.thesis_arguments:
            args.append({"level": "thesis", **a.model_dump()})
        for a in synth.argument_system.major_arguments:
            args.append({"level": "major", **a.model_dump()})
        for a in synth.argument_system.sub_arguments:
            args.append({"level": "sub", **a.model_dump()})
        return args

    def get_mechanisms(self) -> list[dict]:
        """Get all extracted mechanisms."""
        synth = self._get_synthesis()
        if not synth:
            return []
        return [m.model_dump() for m in synth.mechanism_system.mechanisms]

    def get_evidence_for_claim(self, claim_id: str) -> Optional[dict]:
        """Get evidence linked to a specific claim."""
        synth = self._get_synthesis()
        if not synth:
            return None
        for entry in synth.evidence_map.entries:
            if entry.claim_id == claim_id:
                return entry.model_dump()
        return None

    def get_chapter_role(self, chapter_id: str) -> Optional[dict]:
        """Get the role assignment for a chapter."""
        synth = self._get_synthesis()
        if not synth:
            return None
        for assignment in synth.chapter_roles.assignments:
            if assignment.chapter_id == chapter_id:
                return assignment.model_dump()
        return None

    def get_contradictions(self) -> list[dict]:
        """Get all detected contradictions."""
        synth = self._get_synthesis()
        if not synth:
            return []
        return [c.model_dump() for c in synth.contradictions.contradictions]

    def get_unresolved_questions(self) -> list[str]:
        """Get all unresolved questions."""
        synth = self._get_synthesis()
        if not synth:
            return []
        return synth.unresolved_questions

    def get_book_synthesis(self) -> Optional[BookSynthesis]:
        """Get the complete book synthesis."""
        return self._get_synthesis()

    def get_learning_guide(self) -> list[dict]:
        """Task E: the dependency-ordered learning path for this run.

        Derived from the persisted reasoning graph and the run's chapters, so it
        is recomputed on demand rather than stored — the BU stays the authority.
        """
        from stratum.services.bu_v2_learning_guide import LearningGuideBuilder
        from stratum.services.bu_v2_repositories import (
            ChapterUnderstandingRepository,
        )

        bu = self._get_bu()
        if not bu:
            return []
        chapters = ChapterUnderstandingRepository.load_for_run(self.run_id)
        graph = None
        graph_id = bu.get("reasoning_graph_id")
        if graph_id:
            try:
                from stratum.services.bu_v2_reasoning_graph import load_graph

                graph = load_graph(graph_id)
            except Exception:
                graph = None
        guide = LearningGuideBuilder().build(
            run_id=self.run_id,
            book_id=bu.get("book_id") or bu.get("substrate_id") or "",
            graph=graph,
            chapters=chapters,
        )
        return [s.to_dict() for s in guide.steps]

    def get_author_model(self) -> Optional[BookAuthorModel]:
        """Get the author model."""
        synth = self._get_synthesis()
        if not synth:
            return None
        return synth.author_model

    def get_evidence_coverage(self) -> float:
        """Get the evidence coverage metric."""
        synth = self._get_synthesis()
        if not synth:
            return 0.0
        return synth.evidence_map.evidence_coverage

    def get_unsupported_claims(self) -> list[dict]:
        """Get claims without evidence support."""
        synth = self._get_synthesis()
        if not synth:
            return []
        return [e.model_dump() for e in synth.evidence_map.entries if not e.is_supported]

    def get_model_inference_claims(self) -> list[dict]:
        """Get claims primarily supported by model inference."""
        synth = self._get_synthesis()
        if not synth:
            return []
        result = []
        for e in synth.evidence_map.entries:
            if any(s.value == "MODEL_INFERENCE" for s in e.evidence_strengths.values()):
                result.append(e.model_dump())
        return result
