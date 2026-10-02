"""P4 WorkingBU (§35): BU(t+1) = Apply(BU(t), ChapterDelta(t+1)).

WorkingBU is a derived view folded over persisted ChapterDeltas — no new
table, no second BU authority. The canonical BU remains BookUnderstandingV2;
WorkingBU is the running integration state while chapters stream in.

Hard rule enforced: Apply() accepts only ChapterDelta objects. Merging plain
chapter summaries (``summarize(chapter summaries)``) is rejected at the type
level — a delta must declare what changed.
"""

from __future__ import annotations

from typing import List

from stratum.knowledge.bu_v2_models import ChapterDelta, WorkingBU


def _extend(base: List[str], additions: List[str]) -> List[str]:
    out = list(base)
    for item in additions:
        if item not in out:
            out.append(item)
    return out


def init_working_bu(run_id: str, book_id: str = "",
                    governing_questions: List[str] | None = None) -> WorkingBU:
    return WorkingBU(
        id=f"{run_id}::working",
        run_id=run_id,
        book_id=book_id,
        chapter_index=0,
        version=0,
        governing_questions=list(governing_questions or []),
    )


def apply_chapter_delta(working: WorkingBU, delta: ChapterDelta) -> WorkingBU:
    """Apply one chapter delta. Type gate: only ChapterDelta instances are
    accepted — never a plain summary dict/string."""
    if not isinstance(delta, ChapterDelta):
        raise TypeError(
            "BU(t+1) = Apply(BU(t), ChapterDelta(t+1)): plain summaries are "
            "not deltas (SUMMARY_OF_SUMMARIES=0).")
    if delta.run_id != working.run_id:
        raise ValueError(
            f"Delta {delta.id} belongs to run {delta.run_id}, not {working.run_id}.")
    if delta.id in working.applied_delta_refs:
        raise ValueError(f"Delta {delta.id} already applied (not idempotent-safe).")
    data = working.model_dump()
    data["chapter_index"] = working.chapter_index + 1
    data["version"] = working.version + 1
    data["concept_refs"] = _extend(
        _extend(working.concept_refs, delta.new_concepts_refs),
        delta.revised_concepts_refs)
    data["claim_refs"] = _extend(working.claim_refs, delta.new_claims_refs)
    data["argument_refs"] = _extend(working.argument_refs, delta.new_arguments_refs)
    data["qualified_claims"] = _extend(working.qualified_claims, delta.qualifies_prior_refs)
    data["revised_claims"] = _extend(
        _extend(working.revised_claims, delta.revises_prior_refs),
        delta.revised_concepts_refs)
    data["contradicted_claims"] = _extend(working.contradicted_claims, delta.contradicts_prior_refs)
    data["open_questions"] = _extend(
        [q for q in working.open_questions if q not in delta.resolves_questions],
        delta.opens_questions)
    data["resolved_questions"] = _extend(working.resolved_questions, delta.resolves_questions)
    data["applied_delta_refs"] = working.applied_delta_refs + [delta.id]
    return WorkingBU(**data)


def reconstruct_from_deltas(run_id: str, deltas: List[ChapterDelta],
                            book_id: str = "",
                            governing_questions: List[str] | None = None) -> WorkingBU:
    """Replayable fold: same deltas in chapter order always rebuild the same
    WorkingBU (resumable / incrementally repairable, §18)."""
    working = init_working_bu(run_id, book_id, governing_questions)
    for delta in sorted(deltas, key=lambda d: d.chapter_id):
        working = apply_chapter_delta(working, delta)
    return working
