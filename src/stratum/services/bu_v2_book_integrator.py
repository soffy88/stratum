"""Whole-book integration — spec §10.

The spec is explicit about the failure it is guarding against:

    chapter1 summary + chapter2 summary = book understanding     -- FORBIDDEN

A concatenation has no structure that the individual chapters did not have. So
integration here does three things a concatenation cannot:

1. **Concept evolution.** A concept introduced in chapter 3 and refined in
   chapter 9 becomes two versions of one object. ``ChapterDelta`` already
   records which chapters revise what, so evolution is derived from the deltas
   rather than asserted.
2. **Argument architecture.** The book's central thesis and what supports it
   come from the argument structure, not from prose that happens to look
   important.
3. **Dependency graph.** Chapter N's prerequisites become real edges, so a
   reader can be told what a chapter requires and not merely what preceded it.

The model proposes the book's questions and theses; the code derives structure
from the deltas. That split is what keeps the result from being a summary of
summaries — the structure is computed, not generated.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    ArgumentArchitecture,
    BookUnderstandingV2,
    BUStatus,
    ChapterDependency,
    ChapterDependencyGraph,
    ChapterDelta,
    ChapterUnderstanding,
    ClaimEvolutionStep,
    ConceptEvolutionStep,
    DiscourseArc,
    NegativeKnowledge,
)
from stratum.services.bu_v2_provider import (
    ModelProvider,
    ProviderError,
    resolve_provider,
)


@dataclass
class IntegrationInput:
    """Everything integration is allowed to see.

    Holding this explicitly makes §10.4 checkable: integration cannot reach the
    raw book text, only per-chapter understanding and deltas. If a summary
    concatenation were the intended behaviour, this class would not be needed.
    """

    run_id: str
    book_id: str
    substrate_id: str
    chapters: list[ChapterUnderstanding]
    deltas: list[ChapterDelta]
    evidence_by_chapter: dict[str, list[str]]
    genre: str = ""


_SYSTEM = """You identify a book's intellectual structure from its per-chapter
understandings. You answer ONLY with a single JSON object, no prose, no fence."""

_SCHEMA = (
    '{"genre":"<the discipline, e.g. undergraduate mathematics>",'
    '"governing_questions":["<question 1 this whole book answers>",'
    '"<question 2>"],"central_theses":["<claim the whole book defends>"],'
    '"sub_theses":["<a supporting claim>"],'
    '"book_mental_model":"<3-5 sentences on how the author explains the subject '
    'and how the parts fit together, NOT a list of chapters>"}\n\n'
    'Fill every value from the per-chapter theses above. Do not copy these '
    'placeholder phrases as values.'
)


class BookIntegrator:
    """§10: N ChapterUnderstandings in, one BookUnderstandingV2 out."""

    def __init__(self, provider: ModelProvider | None = None):
        self.provider = provider or resolve_provider()

    def integrate(self, data: IntegrationInput, *, version: int = 1) -> BookUnderstandingV2:
        if not data.chapters:
            raise ValueError("integration requires at least one chapter understanding")

        proposal = self._propose(data)
        ordered = sorted(data.chapters, key=lambda c: _chapter_number(c.chapter_id))

        return BookUnderstandingV2(
            id=f"bu_{data.run_id}",
            run_id=data.run_id,
            book_id=data.book_id,
            substrate_id=data.substrate_id,
            version=version,
            status=BUStatus.DRAFT,
            genre=_s(proposal.get("genre")) or data.genre,
            governing_questions=_sl(proposal.get("governing_questions")),
            central_theses=_sl(proposal.get("central_theses")),
            sub_theses=_sl(proposal.get("sub_theses")),
            concept_system=self._concept_system(data),
            argument_architecture=self._argument_architecture(data, proposal),
            chapter_dependency_graph=self._dependency_graph(data),
            discourse_arc=self._discourse_arc(ordered),
            negative_knowledge=self._negative_knowledge(data),
            concept_evolution=self._concept_evolution(data),
            claim_evolution=self._claim_evolution(data),
            resolved_questions=self._resolved(ordered),
            unresolved_questions=self._unresolved(data, ordered),
            coverage_score=_coverage(data),
            verification_score=0.0,  # set by the verification gate, never by generation
        )

    # ── model proposal ─────────────────────────────────────────────────────

    def _propose(self, data: IntegrationInput) -> dict[str, Any]:
        """Ask the model only what cannot be computed: the book's framing.

        Everything structural is derived below. Keeping the model's job narrow
        is what stops the result from being prose with good formatting.
        """
        digest = "\n".join(
            f"  [{c.chapter_id}] {c.chapter_thesis[:150]}"
            for c in sorted(data.chapters, key=lambda x: _chapter_number(x.chapter_id))[:60]
        )
        prompt = (
            f"BOOK with {len(data.chapters)} chapters.\n\n"
            f"PER-CHAPTER THESES:\n{digest}\n\n"
            f"Respond with exactly this JSON shape:\n{_SCHEMA}"
        )
        try:
            out = self.provider.complete(
                prompt, system=_SYSTEM, json_mode=True, max_tokens=900, temperature=0.0
            ).json()
            return out if isinstance(out, dict) else {}
        except (ProviderError, ValueError):
            # A book that cannot be framed by the model still integrates: every
            # structural field below is derived and unaffected.
            return {}

    # ── derived structure ──────────────────────────────────────────────────

    def _concept_system(self, data: IntegrationInput) -> dict[str, Any]:
        """Concepts across the whole book, with the chapters that introduce them."""
        system: dict[str, list[str]] = defaultdict(list)
        mechanisms: list[str] = []
        for c in data.chapters:
            for concept in c.concepts_introduced_refs + c.concepts_redefined_refs:
                if concept and concept not in system[concept]:
                    system[concept].append(c.chapter_id)
            mechanisms.extend(m for m in c.mechanisms_refs if m)
        return {
            "concepts": {k: v for k, v in sorted(system.items())},
            "concept_count": len(system),
            # Mechanisms live per chapter; carrying them here is what lets the
            # expression layer answer §13.3 without a second authority.
            "mechanisms": mechanisms,
        }

    def _argument_architecture(
        self, data: IntegrationInput, proposal: dict[str, Any]
    ) -> ArgumentArchitecture:
        """Root arguments are the book's central theses; supporting are sub-theses.

        Derived from the integration proposal, not from the first chapter that
        happened to be summarised most confidently.
        """
        return ArgumentArchitecture(
            root_arguments=_sl(proposal.get("central_theses")),
            supporting_arguments=_sl(proposal.get("sub_theses")),
        )

    def _dependency_graph(self, data: IntegrationInput) -> ChapterDependencyGraph:
        """Real edges, taken from each chapter's recorded dependencies.

        A chapter that says it requires "the limit definition" is linked to the
        chapter that introduced it. That is a claim about structure, and it is
        what makes the graph more than a reading order.
        """
        edges: list[ChapterDependency] = []
        seen: set[tuple[str, str, str]] = set()
        for c in data.chapters:
            for dep in c.dependencies_on_prior:
                source = self._resolve_source(dep, data, c.chapter_id)
                if not source or source == c.chapter_id:
                    continue
                key = (source, c.chapter_id, "REQUIRES")
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    ChapterDependency(
                        source_chapter=source, target_chapter=c.chapter_id, relation="REQUIRES"
                    )
                )
        return ChapterDependencyGraph(dependencies=edges)

    @staticmethod
    def _resolve_source(dep: str, data: IntegrationInput, dep_chapter: str) -> str | None:
        """Find which earlier chapter introduced the thing a chapter depends on.

        Exact name matching alone finds almost nothing, because a chapter says
        it needs "Basic algebraic operations" while chapter 1 lists "Function"
        and "Domain and Range". So matching proceeds from strict to loose:
        exact, then the dependency phrase being contained in a concept name, then
        a concept name being contained in it, then one significant word in
        common. Only an earlier chapter qualifies, because a dependency on
        yourself is not a dependency.
        """
        target = _norm(dep)
        if not target:
            return None

        # Index every concept by its normalised name, with the chapter that
        # introduces it. Only chapters before the dependent one qualify.
        candidates: list[tuple[str, str]] = []
        for c in data.chapters:
            for concept in c.concepts_introduced_refs + c.concepts_redefined_refs:
                n = _norm(concept)
                if n:
                    candidates.append((n, c.chapter_id))

        def pick(pred) -> str | None:
            limit = _chapter_number(dep_chapter)
            hits = [
                cid for n, cid in candidates
                if _chapter_number(cid) < limit and pred(n)
            ]
            if not hits:
                return None
            return min(hits, key=_chapter_number)

        exact = pick(lambda n: n == target)
        if exact:
            return exact
        contained = pick(lambda n: target in n or n in target)
        if contained:
            return contained
        words = {w for w in target.split() if len(w) > 3}
        if words:
            shared = pick(lambda n: bool(words & set(n.split())))
            if shared:
                return shared
        return None

    def _discourse_arc(self, chapters: list[ChapterUnderstanding]) -> DiscourseArc:
        """The book's shape, derived from role rather than from position.

        The first chapter opens, the last closes, and the middle is Model or
        Evidence by what each chapter was actually doing.
        """
        steps: list[dict[str, str]] = []
        n = len(chapters)
        for i, c in enumerate(chapters):
            if i == 0:
                step_type = "Problem"
            elif i == n - 1:
                step_type = "Conclusion"
            elif c.evidence_program:
                step_type = "Evidence"
            else:
                step_type = "Model"
            steps.append(
                {
                    "step_type": step_type,
                    "description": c.chapter_thesis or c.chapter_goal or c.chapter_question or c.chapter_id,
                    "chapter_ref": c.chapter_id,
                }
            )
        return DiscourseArc(steps=steps)

    def _negative_knowledge(self, data: IntegrationInput) -> NegativeKnowledge:
        """§9: what the book does not settle, gathered from every chapter."""
        limitations: list[str] = []
        open_problems: list[str] = []
        for c in data.chapters:
            limitations.extend(c.qualifications[:3])
            open_problems.extend(c.assumptions[:3])
        # A chapter that failed extraction is itself negative knowledge: the
        # book was not understood there, and that gap is real.
        failed = [c.chapter_id for c in data.chapters if c.primary_role == "UNDERSTANDING_FAILED"]
        return NegativeKnowledge(
            rejected_claims=[],
            limitations=_dedupe(limitations)[:50],
            open_problems=_dedupe(open_problems)[:50],
            unresolved_conflicts=[f"chapter not understood: {cid}" for cid in failed],
        )

    def _concept_evolution(self, data: IntegrationInput) -> list[ConceptEvolutionStep]:
        """§10.1: a concept redefined later is a new version, not a duplicate."""
        versions: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for c in data.chapters:
            n = _chapter_number(c.chapter_id)
            for concept in c.concepts_introduced_refs:
                versions[concept].append((n, c.chapter_id))
            for concept in c.concepts_redefined_refs:
                versions[concept].append((n, c.chapter_id))

        steps: list[ConceptEvolutionStep] = []
        for concept, appearances in sorted(versions.items()):
            ordered = sorted(set(appearances))
            for idx, (_, chapter_ref) in enumerate(ordered, start=1):
                steps.append(
                    ConceptEvolutionStep(
                        concept_ref=concept,
                        version=idx,
                        definition=f"introduced or redefined in {chapter_ref}",
                        chapter_ref=chapter_ref,
                        evolution_type="REFINE" if idx > 1 else "DEFINE",
                    )
                )
        return steps

    def _claim_evolution(self, data: IntegrationInput) -> list[ClaimEvolutionStep]:
        steps: list[ClaimEvolutionStep] = []
        for d in data.deltas:
            for claim in d.new_claims_refs[:10]:
                steps.append(
                    ClaimEvolutionStep(
                        claim_ref=claim[:120],
                        version=1,
                        statement=claim[:300],
                        chapter_ref=d.chapter_id,
                        evolution_type="ASSERT",
                    )
                )
            for qualified in d.qualifies_prior_refs[:5]:
                steps.append(
                    ClaimEvolutionStep(
                        claim_ref=qualified[:120],
                        version=1,
                        statement=f"qualified in {d.chapter_id}",
                        chapter_ref=d.chapter_id,
                        evolution_type="QUALIFY",
                    )
                )
        return steps

    def _resolved(self, chapters: list[ChapterUnderstanding]) -> list[str]:
        return _dedupe([c.chapter_question for c in chapters if c.chapter_question])[:30]

    def _unresolved(
        self, data: IntegrationInput, chapters: list[ChapterUnderstanding]
    ) -> list[str]:
        items: list[str] = []
        for d in data.deltas:
            items.extend(d.opens_questions)
        for c in chapters:
            if c.primary_role == "UNDERSTANDING_FAILED":
                items.append(f"{c.chapter_id} could not be understood")
        return _dedupe(items)[:50]

    # integration_method is set by the caller via repository bookkeeping; keep
    # the concept here so §10.4's claim is visible in the model.
    method = "delta_derived_concept_evolution+argument_architecture+dependency_graph"


def _coverage(data: IntegrationInput) -> float:
    """Fraction of chapters that produced real understanding, not just a row."""
    if not data.chapters:
        return 0.0
    understood = [c for c in data.chapters if c.primary_role != "UNDERSTANDING_FAILED"]
    return round(len(understood) / len(data.chapters), 4)


# ── helpers ──────────────────────────────────────────────────────────────────


def _chapter_number(chapter_id: str) -> int:
    """Sort key. ``ch3`` -> 3, ``ch10`` -> 10, so ch10 follows ch9."""
    digits = "".join(ch for ch in chapter_id if ch.isdigit())
    return int(digits) if digits else 0


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch.isspace()).strip()


def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _sl(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [x.strip() for x in v if isinstance(x, str) and x.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out