"""Claim verification: every claim a chapter asserts is checked against the
passage it is anchored to before the understanding is published.

A model paraphrases and sometimes over-reaches. Recording every extracted claim
as ``is_supported=True`` (what BU2 did before) made the evidence program a list
of assertions rather than a list of supported claims. Here each claim is put to
a strict YES/NO judge together with its anchored source passage; a claim the
passage does not support keeps its row but is marked ``is_supported=False`` and
its evidence strength is downgraded to MODEL_INFERENCE, so nothing downstream
can present it as the book's own statement (§11, §15).

The judge never sees the model's own quote as ground truth: it sees the span of
the book the claim was located at.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

STRICT_PROMPT = (
    "You verify a reading of a textbook.\n"
    "SOURCE is a passage from the book. CLAIM is a statement someone attributes to "
    "this part of the book.\n"
    "Answer YES only if the SOURCE states the claim or it follows directly from what "
    "the SOURCE says (a faithful paraphrase is fine). Answer NO if the claim adds "
    "facts the SOURCE does not contain, contradicts it, or the SOURCE is about "
    "something else.\n\n"
    "SOURCE: {quote}\n\nCLAIM: {claim}\n\n"
    "Reply with one word: YES or NO."
)

_YES_NO = re.compile(r"\b(YES|NO)\b")


def parse_verdict(text: str) -> bool | None:
    """First YES/NO token in the reply (thinking models may prefix reasoning)."""
    m = _YES_NO.search((text or "").upper())
    if not m:
        return None
    return m.group(1) == "YES"


def make_provider_judge(provider: Any, *, max_tokens: int = 512) -> Callable[[str], str] | None:
    """A ``(prompt) -> reply`` callable over a ModelProvider, or None."""
    if provider is None:
        return None

    def _judge(prompt: str) -> str:
        try:
            resp = provider.complete(prompt, max_tokens=max_tokens, temperature=0.0)
            return getattr(resp, "text", "") or ""
        except Exception:
            return ""

    return _judge


@dataclass
class ClaimVerification:
    checked: int = 0
    supported: int = 0
    rejected: int = 0
    undecided: int = 0
    reanchored: int = 0
    rejected_examples: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "supported": self.supported,
            "rejected": self.rejected,
            "undecided": self.undecided,
            "reanchored": self.reanchored,
            "rejected_examples": self.rejected_examples[:10],
        }


class ClaimVerifier:
    def __init__(self, judge: Callable[[str], str] | None, *, workers: int | None = None):
        self.judge = judge
        self.workers = workers or int(os.environ.get("BU2_VERIFY_WORKERS", "8"))

    def verify(
        self,
        chapters: list[Any],
        evidence: list[Any],
        texts: dict[str, Any] | None = None,
    ) -> ClaimVerification:
        """Judge every claim; when its anchor fails, try the chapter's next-best
        supporting passages (``texts``: chapter_id -> Chapter) before marking it
        unsupported. A re-anchored claim gets a new evidence artifact."""
        out = ClaimVerification()
        if self.judge is None:
            return out
        ev_by_id = {e.evidence_id: e for e in evidence}
        jobs: list[tuple[Any, Any, Any]] = []  # (chapter, program item, evidence)
        for cu in chapters:
            for ep in cu.evidence_program:
                if not ep.evidence_refs:
                    continue
                ev = ev_by_id.get(ep.evidence_refs[0])
                if ev is None or not (getattr(ev, "quote", "") or "").strip():
                    continue
                jobs.append((cu, ep, ev))

        def _ask(quote: str, claim: str) -> bool | None:
            prompt = STRICT_PROMPT.format(quote=quote[:900], claim=claim[:600])
            verdict = parse_verdict(self.judge(prompt))  # type: ignore[misc]
            if verdict is None:  # one retry: a rotating gateway may return empty
                verdict = parse_verdict(self.judge(prompt))  # type: ignore[misc]
            return verdict

        texts = texts or {}

        def _one(job: tuple[Any, Any, Any]) -> tuple[bool | None, Any]:
            cu, ep, ev = job
            verdict = _ask(ev.quote, ep.claim_ref)
            if verdict is not False:
                return verdict, None
            chapter = texts.get(cu.chapter_id)
            if chapter is None or not hasattr(chapter, "best_passages"):
                return verdict, None
            for locator, snippet in chapter.best_passages(ep.claim_ref, k=4):
                if snippet[:200] == ev.quote[:200]:
                    continue
                if _ask(snippet, ep.claim_ref):
                    from stratum.services.bu_v2_producer import EvidenceArtifact

                    new_ev = EvidenceArtifact.make(
                        ev.run_id, cu.chapter_id, "CLAIM_PASSAGE", locator, snippet
                    )
                    return True, new_ev
            return False, None

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            outcomes = list(pool.map(_one, jobs))

        for (cu, ep, ev), (verdict, new_ev) in zip(jobs, outcomes):
            if new_ev is not None:
                new_ev.verified = True
                evidence.append(new_ev)
                ep.evidence_refs = [new_ev.evidence_id] + [
                    r for r in ep.evidence_refs if r != ev.evidence_id
                ]
                strengths = getattr(cu, "evidence_strengths", None)
                if isinstance(strengths, dict):
                    strengths[new_ev.evidence_id] = "DERIVED"
                cu.supporting_ku_refs = list(cu.supporting_ku_refs) + [new_ev.evidence_id]
                out.reanchored += 1
                ev = new_ev
            out.checked += 1
            if verdict is None:
                out.undecided += 1
                continue
            setattr(ev, "verified", verdict)
            if verdict:
                out.supported += 1
                continue
            out.rejected += 1
            ep.is_supported = False
            strengths = getattr(cu, "evidence_strengths", None)
            if isinstance(strengths, dict):
                strengths[ev.evidence_id] = "MODEL_INFERENCE"
            out.rejected_examples.append(
                {"chapter": cu.chapter_id, "claim": ep.claim_ref[:200], "quote": ev.quote[:200]}
            )
        return out
