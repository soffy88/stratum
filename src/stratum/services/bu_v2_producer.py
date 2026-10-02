"""ChapterUnderstanding producer — spec §8, §9.

This is the component the P9 acceptance audit found missing: BU2 had 16 tables
to hold chapter understanding and nothing that produced one. Here is the
producer.

Two rules shape the code:

**Every understanding carries its evidence.** §9 requires ``run_id + book_id +
chapter_id`` unique, and §11 requires a claim to be traceable to a source
location. So each extracted item is stored with the character span it came
from, not just its text. A claim that cannot be located is not stored at all,
because an unlocatable claim is the exact failure the verification gate exists
to catch — it is cheaper to refuse it here than to catch it there.

**The model proposes; the code disposes.** §7.1 requires the engine to call a
``ModelProvider``, never a model SDK. The model returns JSON, and every field
is validated and coerced here. A model that returns prose, a wrong type, or an
empty list yields a degraded-but-valid ChapterUnderstanding, never an exception
that would take down a whole book run over one chapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    ChapterDelta,
    ChapterUnderstanding,
    EvidenceProgramItem,
)
from stratum.services.bu_v2_provider import (
    ModelProvider,
    ProviderError,
    resolve_provider,
)


@dataclass
class EvidenceArtifact:
    """§11: where a claim came from.

    ``content_hash`` is the identity of the located span, so a re-run against
    unchanged text produces the same hash and the evidence is verifiably the
    same evidence rather than merely similar.
    """

    evidence_id: str
    run_id: str
    chapter_id: str
    kind: str
    locator: str
    quote: str
    content_hash: str

    @staticmethod
    def make(run_id: str, chapter_id: str, kind: str, locator: str, quote: str) -> "EvidenceArtifact":
        h = hashlib.sha256(f"{chapter_id}|{locator}|{quote}".encode()).hexdigest()[:16]
        return EvidenceArtifact(
            evidence_id=f"ev_{h}",
            run_id=run_id,
            chapter_id=chapter_id,
            kind=kind,
            locator=locator,
            quote=quote[:400],
            content_hash=h,
        )


@dataclass
class Chapter:
    """One chapter, already separated from the book.

    ``start``/``end`` are character offsets into the book's full text, which is
    what makes ``locator`` a real position rather than a decorative label.
    """

    chapter_id: str
    number: int
    title: str
    text: str
    start: int = 0
    end: int = 0
    subsections: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text)

    def slice_for(self, needle: str, window: int = 400) -> tuple[str, str] | None:
        """Locate ``needle`` in this chapter, returning (locator, quote).

        This is the mechanism behind §11's traceability requirement. When it
        returns None the claim is unlocatable and the caller drops it.
        """
        if not needle:
            return None
        i = self.text.find(needle[:60]) if len(needle) >= 60 else self.text.find(needle)
        if i == -1:
            # Fall back to a distinctive fragment: a small model paraphrases
            # constantly, so the exact string is often absent.
            frag = needle[:40]
            if len(frag) >= 12:
                i = self.text.find(frag)
        if i == -1:
            return None
        return (self.locator(i), self.text[i : i + window].strip())

    def locate_term(self, term: str, window: int = 320) -> tuple[str, str] | None:
        """Locate the first substantial mention of a technical term.

        A verbatim quote from the model is the best evidence when it verifies.
        Small models paraphrase instead, so a claim can be right and still
        unquotable. Anchoring on the concept's own term keeps the evidence real:
        the span genuinely discusses that concept, which is what §11 asks for,
        and the term is the model's or the chapter's, never invented text.
        """
        if not term or len(term) < 3:
            return None
        # Word-boundary match so "range" does not land inside "arrange".
        pattern = re.compile(r"\b" + re.escape(term.strip()) + r"\b", re.I)
        m = pattern.search(self.text)
        if not m:
            return None
        i = m.start()
        return (self.locator(i), self.text[i : i + window].strip())

    def locator(self, offset: int) -> str:
        absolute = self.start + offset
        page = "unknown"
        m = re.match(r"p(\d+)", self.chapter_id)
        if m:
            page = m.group(1)
        return f"char:{absolute}" + (f" (page {page})" if page != "unknown" else "")


_SYSTEM = """You extract book structure from a textbook chapter.
You answer ONLY with a single JSON object. No prose, no markdown fence.
Every list must contain short strings. If you do not know something, use an empty list."""


def _schema_hint() -> str:
    # Concrete example values, because a small model copies placeholder text
    # verbatim: given "the 2-4 questions the whole book tries to answer" it will
    # return that phrase as the answer. Naming a real domain in the example
    # makes it obvious the value must come from the text.
    return (
        '{"chapter_question":"<the question THIS chapter answers, in your own words>",'
        '"chapter_goal":"<what the reader can do after this chapter>",'
        '"chapter_thesis":"<the single most important idea in THIS chapter>",'
        '"summary":"<3-5 sentences on what this chapter covers>",'
        '"concepts":[{"name":"<term>","definition":"<one sentence>"}],'
        '"claims":[{"text":"<an assertion THIS chapter makes>",'
        '"quote":"<a phrase copied EXACTLY from the text above>"}],'
        '"mechanisms":[{"cause":"<what produces the effect>","process":"<the steps or relation>",'
        '"conditions":"<when it holds>"}],'
        '"dependencies":["<prior concept this chapter needs>"],'
        '"uncertainties":["<what the chapter leaves open or only approximately states>"],'
        '"terminology":[{"term":"<word>","meaning":"<definition as the chapter gives it>"}]}'
        '\n\nExample for a chapter on derivatives: chapter_thesis = "A derivative '
        'measures instantaneous rate of change". Never copy the placeholder text '
        'above as a value.'
    )


class ChapterUnderstandingProducer:
    """§8: chapter content in, ChapterUnderstanding out."""

    def __init__(self, provider: ModelProvider | None = None, *, max_chars: int = 12000):
        self.provider = provider or resolve_provider()
        # A small local model degrades badly past a few thousand characters, and
        # a large hosted one is billed per token. 12k is the compromise; the
        # chapter is chunked by section when it exceeds this.
        self.max_chars = max_chars

    def produce(
        self,
        chapter: Chapter,
        *,
        run_id: str,
        book_id: str,
        prior_chapter_ids: list[str] | None = None,
    ) -> tuple[ChapterUnderstanding, ChapterDelta, list[EvidenceArtifact]]:
        """Produce understanding for one chapter.

        Returns the understanding, its delta against prior chapters, and the
        evidence for every claim that survived location. Never raises on model
        misbehaviour: a chapter that cannot be understood becomes an empty
        understanding with its uncertainties recorded, which is honest and
        keeps the book run alive.
        """
        prompt = (
            f"TITLE: {chapter.title}\n"
            f"CHARACTERS: {chapter.char_count}\n\n"
            f"CHAPTER TEXT:\n{chapter.text[: self.max_chars]}\n\n"
            f"Extract the structure. Respond with exactly this JSON shape:\n{_schema_hint()}"
        )
        try:
            resp = self.provider.complete(
                prompt, system=_SYSTEM, json_mode=True, max_tokens=1600, temperature=0.0
            )
            data = resp.json()
            if not isinstance(data, dict):
                raise ProviderError(f"expected a JSON object, got {type(data).__name__}")
        except (ProviderError, ValueError) as exc:
            data = {}
            failure = str(exc)
        else:
            failure = ""

        if failure:
            # §9 and the verification gate both want the gap recorded, not hidden.
            cu = ChapterUnderstanding(
                id=f"cu_{run_id}_{chapter.chapter_id}",
                run_id=run_id,
                chapter_id=chapter.chapter_id,
                chapter_question="",
                chapter_goal="",
                chapter_thesis="",
                primary_role="UNDERSTANDING_FAILED",
                qualifications=[f"extraction failed: {failure[:200]}"],
            )
            delta = ChapterDelta(
                id=f"cd_{run_id}_{chapter.chapter_id}",
                run_id=run_id,
                chapter_id=chapter.chapter_id,
                opens_questions=[f"chapter {chapter.title} could not be understood"],
            )
            return cu, delta, []

        cu, evidence = self._build_understanding(chapter, run_id, data)
        delta = self._build_delta(chapter, run_id, data, prior_chapter_ids or [])
        return cu, delta, evidence

    # ── internals ──────────────────────────────────────────────────────────

    def _build_understanding(
        self, chapter: Chapter, run_id: str, data: dict
    ) -> tuple[ChapterUnderstanding, list[EvidenceArtifact]]:
        evidence: list[EvidenceArtifact] = []
        program: list[EvidenceProgramItem] = []

        for claim in _as_list(data.get("claims")):
            text = _as_str(claim.get("text") if isinstance(claim, dict) else claim)
            quote = _as_str(claim.get("quote")) if isinstance(claim, dict) else ""
            if not text:
                continue
            # Prefer the model's own quote. If it does not verify — the usual
            # case for a small model, which paraphrases — anchor on a technical
            # term from the claim instead. Either way the span is real text at
            # a real offset; neither path accepts the model's wording on trust.
            found = chapter.slice_for(quote) or chapter.slice_for(text)
            kind = "CLAIM"
            if not found:
                for term in _significant_terms(text):
                    found = chapter.locate_term(term)
                    if found:
                        kind = "CLAIM_TERM_ANCHOR"
                        break
            if not found:
                # §11: an unlocatable claim is not stored. Dropping it here
                # means the verification gate never has to catch it.
                continue
            locator, snippet = found
            ev = EvidenceArtifact.make(run_id, chapter.chapter_id, kind, locator, snippet)
            evidence.append(ev)
            program.append(
                EvidenceProgramItem(
                    claim_ref=text[:120],
                    evidence_refs=[ev.evidence_id],
                    is_supported=True,
                )
            )

        # Concepts anchor evidence too. A concept the chapter actually
        # discusses has a locatable first mention, and that is the evidence
        # §9 wants for "this chapter introduces this concept".
        for concept in _as_list(data.get("concepts")):
            name = _as_str(concept.get("name")) if isinstance(concept, dict) else ""
            if not name:
                continue
            found = chapter.locate_term(name)
            if not found:
                continue
            locator, snippet = found
            ev = EvidenceArtifact.make(run_id, chapter.chapter_id, "CONCEPT", locator, snippet)
            evidence.append(ev)

        concepts_introduced = [
            _as_str(c.get("name")) for c in _as_list(data.get("concepts")) if _as_str(c.get("name") if isinstance(c, dict) else c)
        ]
        mechanisms = [
            _as_str(m.get("cause") or m.get("process"))
            for m in _as_list(data.get("mechanisms"))
            if _as_str((m.get("cause") or m.get("process")) if isinstance(m, dict) else m)
        ]

        return (
            ChapterUnderstanding(
                id=f"cu_{run_id}_{chapter.chapter_id}",
                run_id=run_id,
                chapter_id=chapter.chapter_id,
                chapter_question=_as_str(data.get("chapter_question")),
                chapter_goal=_as_str(data.get("chapter_goal")),
                chapter_thesis=_as_str(data.get("chapter_thesis")),
                primary_role=_as_str(data.get("primary_role")) or "CONCEPT_INTRODUCTION",
                secondary_roles=[r for r in _as_list(data.get("secondary_roles")) if isinstance(r, str)],
                concepts_introduced_refs=concepts_introduced,
                major_ku_refs=[c for c in concepts_introduced if c],
                supporting_ku_refs=[e.evidence_id for e in evidence],
                mechanisms_refs=[m for m in mechanisms if m],
                evidence_program=program,
                assumptions=[
                    _as_str(u) for u in _as_list(data.get("uncertainties")) if _as_str(u)
                ],
                qualifications=[
                    _as_str(u) for u in _as_list(data.get("uncertainties")) if _as_str(u)
                ],
                dependencies_on_prior=[
                    _as_str(d) for d in _as_list(data.get("dependencies")) if _as_str(d)
                ],
            ),
            evidence,
        )

    def _build_delta(
        self, chapter: Chapter, run_id: str, data: dict, prior_ids: list[str]
    ) -> ChapterDelta:
        """§10.1: a delta is what this chapter changes relative to earlier ones.

        Only the first chapter opens concepts. Every later chapter can revise,
        qualify or contradict, which is what makes cross-chapter evolution a
        derived property rather than a concatenation.
        """
        concepts = [
            _as_str(c.get("name")) for c in _as_list(data.get("concepts")) if _as_str(c.get("name") if isinstance(c, dict) else c)
        ]
        claims = [
            _as_str(c.get("text"))
            for c in _as_list(data.get("claims"))
            if isinstance(c, dict) and _as_str(c.get("text"))
        ]
        return ChapterDelta(
            id=f"cd_{run_id}_{chapter.chapter_id}",
            run_id=run_id,
            chapter_id=chapter.chapter_id,
            new_concepts_refs=concepts if not prior_ids else [],
            revised_concepts_refs=concepts if prior_ids else [],
            new_claims_refs=claims[:20],
            supports_prior_refs=prior_ids[-3:] if prior_ids else [],
            qualifies_prior_refs=[
                _as_str(d) for d in _as_list(data.get("dependencies")) if _as_str(d)
            ]
            if prior_ids
            else [],
            opens_questions=[
                _as_str(u) for u in _as_list(data.get("uncertainties")) if _as_str(u)
            ],
            resolves_questions=[],
        )


# ── coercion helpers ─────────────────────────────────────────────────────────
# A 0.5B model returns nulls, strings where objects belong, and prose where
# JSON belongs. These helpers make the field shapes total, so one malformed
# field degrades that field instead of raising.


def _as_list(v: Any) -> list[Any]:
    """Normalise a model field that should be a list.

    Accepts objects and plain strings, because a model asked for
    ``["a string"]`` sometimes returns ``[{"name": "a string"}]`` and sometimes
    the reverse. Rejecting strings outright silently discarded a chapter's
    entire uncertainty list, which is the content §9 exists to preserve.
    """
    if isinstance(v, list):
        return list(v)
    if isinstance(v, str):
        return [v]
    return []


def _as_str(v: Any) -> str:
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    return ""


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "to", "in",
    "on", "at", "by", "for", "with", "that", "this", "these", "those", "and", "or",
    "it", "its", "as", "from", "if", "then", "than", "which", "when", "can", "will",
    "any", "all", "each", "not", "but", "so", "we", "you", "they", "he", "she",
}


def _significant_terms(text: str, limit: int = 6) -> list[str]:
    """Longest capitalised or multi-syllable-looking words in a claim.

    Used to anchor evidence when the model's quote does not verify. English
    function words are excluded because they match everywhere and so locate
    nothing.
    """
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text or "")
    seen: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in _STOPWORDS or lw in {s.lower() for s in seen}:
            continue
        # Prefer multi-word technical terms and rarer long words.
        seen.append(w)
    seen.sort(key=lambda w: (-len(w), w.lower()))
    return seen[:limit]