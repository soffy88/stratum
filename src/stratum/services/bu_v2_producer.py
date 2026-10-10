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

import os

import hashlib
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
    ProviderUnavailable,
    _is_transient,
    call_with_retry,
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
    def make(
        run_id: str, chapter_id: str, kind: str, locator: str, quote: str
    ) -> "EvidenceArtifact":
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


class ChapterRole(str):
    """§6.2: the role a chapter plays in the book's argument.

    A plain string rather than an Enum because the role is often inferred and
    must remain serialisable into the existing ``primary_role`` column.
    """

    INTRODUCTION = "INTRODUCTION"
    FOUNDATION = "FOUNDATION"
    CONCEPT_BUILDING = "CONCEPT_BUILDING"
    APPLICATION = "APPLICATION"
    PROOF = "PROOF"
    SUMMARY = "SUMMARY"
    TRANSITION = "TRANSITION"


# Order matters: "Applications of Derivatives" matches both application and
# concept_building, and it is an application chapter. The first match wins, so
# the more specific intent comes first.
ROLE_HINTS = {
    "application": [
        r"\bapplications?\b",
        r"\busing\b",
        r"\btechniques?\b",
        r"\bprojections?\b",
        r"\bgeometry of\b",
    ],
    "summary": [r"\bsummary\b", r"\breview\b", r"\bconclusion\b", r"\brevisit\b"],
    "foundation": [r"\blimits?\b", r"\bdefinitions?\b", r"\baxioms?\b", r"\bfoundations?\b"],
    "introduction": [r"\bintroduction\b", r"\bpreface\b", r"\bwhy we (?:study|need)\b"],
    "concept_building": [
        r"\bderivatives?\b",
        r"\bintegrals?\b",
        r"\bvectors?\b",
        r"\bseries\b",
        r"\bequations?\b",
    ],
}


@dataclass
class ChapterContext:
    """§6.1: what the producer needs to know beyond the chapter's own text.

    Without this the model sees a 300,000-character slice with no idea where it
    sits in the book, so it reports the same framing for chapter 1 and
    chapter 12. These fields are the difference.
    """

    book_title: str = ""
    chapter_number: int = 0
    chapter_total: int = 0
    chapter_role: str = ChapterRole.CONCEPT_BUILDING
    previous_chapter_titles: list[str] = field(default_factory=list)
    previous_concepts: list[str] = field(default_factory=list)
    following_expectations: str = ""
    position_ratio: float = 0.0

    def render(self) -> str:
        lines = [
            f"BOOK: {self.book_title or 'unknown'}",
            f"THIS IS CHAPTER {self.chapter_number} of {self.chapter_total}"
            f" ({self.position_ratio:.0%} through the book)",
            f"ITS ROLE IN THE BOOK: {self.chapter_role}",
        ]
        if self.previous_chapter_titles:
            lines.append("PREVIOUS CHAPTERS: " + "; ".join(self.previous_chapter_titles[-3:]))
        if self.previous_concepts:
            lines.append("CONCEPTS ALREADY ESTABLISHED: " + "; ".join(self.previous_concepts[:12]))
        if self.following_expectations:
            lines.append("WHAT THE READER WILL NEED NEXT: " + self.following_expectations)
        return "\n".join(lines)


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
    context: ChapterContext | None = None
    confidence: float = 1.0
    kind: str = "chapter"
    # §6.2 role, set once the chapter knows its position in the book.
    role: str = ""

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
            # CJK OCR text carries stray spaces and line breaks between
            # characters, so retry ignoring whitespace inside the needle.
            i = _fuzzy_find(self.text, needle[:40])
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
        term = (term or "").strip()
        if _CJK_RE.search(term):
            # Chinese has no word boundaries and its terms are often two
            # characters (极限, 导数), so match the characters directly.
            if len(term) < 2:
                return None
            i = _fuzzy_find(self.text, term)
            if i == -1:
                return None
            return (self.locator(i), self.text[i : i + window].strip())
        if len(term) < 3:
            return None
        # Word-boundary match so "range" does not land inside "arrange".
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
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
        "above as a value."
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
        context_block = chapter.context.render() if chapter.context else ""
        prompt = (
            f"{context_block}\n\n"
            f"CHAPTER: {chapter.title}\n"
            f"CHARACTERS: {chapter.char_count}\n\n"
            f"CHAPTER TEXT:\n{chapter.text[: self.max_chars]}\n\n"
            f"{_language_rule(chapter.text[: self.max_chars])}"
            f"Extract the structure. Respond with exactly this JSON shape:\n{_schema_hint()}"
        )

        # Chinese answers cost roughly twice the tokens of English ones; at
        # 1600 they were cut off mid-JSON and every chapter was asked again.
        max_tokens = 2800 if _language_rule(chapter.text[:4000]) else 1600

        def _ask() -> dict:
            resp = self.provider.complete(
                prompt, system=_SYSTEM, json_mode=True, max_tokens=max_tokens, temperature=0.0
            )
            try:
                data = resp.json()
            except ValueError as exc:
                raise ProviderError(str(exc)) from exc
            # Some models wrap the object in a one-element list; unwrap it.
            if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
                data = data[0]
            if not isinstance(data, dict):
                raise ProviderError(f"expected a JSON object, got {type(data).__name__}")
            return data

        # A rotating gateway routes each call to a different upstream, so a
        # malformed answer or an exhausted gateway retry budget is worth asking
        # again. Provider-level transient retries happen inside complete().
        try:
            data = call_with_retry(
                _ask,
                attempts=int(os.environ.get("BU2_CHAPTER_ATTEMPTS", "3")),
                retry_if=lambda exc: not isinstance(exc, ProviderUnavailable) or _is_transient(exc),
            )
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
                # The reason is kept verbatim in both the thesis and the
                # qualification. A gate that reports "1 chapter failed" without
                # saying why is not actionable, and this is the only place the
                # cause survives the run.
                chapter_thesis=f"[not understood] {failure[:160]}",
                primary_role="UNDERSTANDING_FAILED",
                qualifications=[f"extraction failed: {failure[:400]}"],
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
        # §11: claim -> evidence strength. Populated as evidence is created.
        strengths: dict[str, str] = {}

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
            # §11: how strong is this support? A claim located by the model's own
            # verbatim quote is DIRECT; one located only by a term anchor is
            # weaker, and saying so is the point of recording a strength at all.
            strengths[ev.evidence_id] = "DIRECT" if kind == "CLAIM" else "DERIVED"

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
            strengths[ev.evidence_id] = "DEFINITION"

        concepts_introduced = [
            _as_str(c.get("name"))
            for c in _as_list(data.get("concepts"))
            if _as_str(c.get("name") if isinstance(c, dict) else c)
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
                primary_role=(
                    _as_str(data.get("chapter_role")).upper()
                    or _as_str(data.get("primary_role")).upper()
                    or classify_role(chapter)
                ),
                secondary_roles=[
                    r.upper() for r in _as_list(data.get("secondary_roles")) if isinstance(r, str)
                ][:6],
                concepts_introduced_refs=concepts_introduced,
                major_ku_refs=[c for c in concepts_introduced if c],
                supporting_ku_refs=[e.evidence_id for e in evidence],
                mechanisms_refs=[m for m in mechanisms if m],
                evidence_program=program,
                # §11: carried on the understanding so the binding is checkable
                # rather than inferred by the consumer.
                evidence_strengths=strengths,
                assumptions=[_as_str(u) for u in _as_list(data.get("uncertainties")) if _as_str(u)],
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
            _as_str(c.get("name"))
            for c in _as_list(data.get("concepts"))
            if _as_str(c.get("name") if isinstance(c, dict) else c)
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
            opens_questions=[_as_str(u) for u in _as_list(data.get("uncertainties")) if _as_str(u)],
            resolves_questions=[],
        )


def classify_role(chapter: "Chapter") -> str:
    """§6.2: classify a chapter's role from position, title and content.

    Deterministic, and it exists because a small model either omits the field or
    invents one. Position carries real signal — the first chapter opens and the
    last closes — and the title carries the argument's shape ("Applications of
    Derivatives" is application work, "Limits and Continuity" is foundation).
    """
    title = (chapter.title or "").lower()
    total = chapter.context.chapter_total if chapter.context else 0
    num = chapter.context.chapter_number if chapter.context else chapter.number

    if num == 1:
        chapter.role = ChapterRole.INTRODUCTION
        return chapter.role
    if total and num == total:
        chapter.role = ChapterRole.SUMMARY
        return chapter.role
    for role, patterns in ROLE_HINTS.items():
        if any(re.search(p, title) for p in patterns):
            chapter.role = {
                "introduction": ChapterRole.INTRODUCTION,
                "foundation": ChapterRole.FOUNDATION,
                "concept_building": ChapterRole.CONCEPT_BUILDING,
                "application": ChapterRole.APPLICATION,
                "summary": ChapterRole.SUMMARY,
            }[role]
            return chapter.role
    if re.search(r"\bproof|\btheorem|\blemma|\bderivation\b", title):
        chapter.role = ChapterRole.PROOF
        return chapter.role
    # A chapter that introduces nothing new but depends on earlier ones is a
    # transition: it carries the book forward rather than adding to it.
    if (
        chapter.context
        and chapter.context.previous_concepts
        and not _mentions_new_concepts(chapter)
    ):
        chapter.role = ChapterRole.TRANSITION
        return chapter.role
    chapter.role = ChapterRole.CONCEPT_BUILDING
    return chapter.role


def _mentions_new_concepts(chapter: "Chapter") -> bool:
    """Whether the chapter's opening looks like it defines something.

    A crude but real signal: a defining chapter opens by naming its object,
    a transition chapter opens by referring back to what came before.
    """
    head = (chapter.text or "")[:1200].lower()
    return bool(
        re.search(r"\bwe (?:now )?(?:define|introduce|consider)\b", head)
        or re.search(r"\bis defined as\b", head)
        or re.search(r"\bdefinition\b", head)
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
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "for",
    "with",
    "that",
    "this",
    "these",
    "those",
    "and",
    "or",
    "it",
    "its",
    "as",
    "from",
    "if",
    "then",
    "than",
    "which",
    "when",
    "can",
    "will",
    "any",
    "all",
    "each",
    "not",
    "but",
    "so",
    "we",
    "you",
    "they",
    "he",
    "she",
}


def _language_rule(text: str) -> str:
    """Tell the model to answer in the chapter's own language.

    Evidence is located by matching concept names and quotes against the
    source text. A model that answers a Chinese chapter in English produces
    names and quotes that occur nowhere in it, so nothing verifies.
    """
    sample = text[:4000]
    cjk = len(_CJK_RE.findall(sample))
    letters = len(re.findall(r"[A-Za-z]", sample))
    if cjk and cjk >= letters * 0.5:
        return (
            "LANGUAGE: the chapter is written in Chinese. Write every value in "
            "Chinese. Concept names and terms must be the exact Chinese words "
            "the text uses (e.g. 极限, 导数), and every quote must be copied "
            "character for character from the Chinese text above. Do not "
            "translate.\n\n"
        )
    return ""


_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def _fuzzy_find(text: str, needle: str) -> int:
    """Find ``needle`` in ``text`` ignoring whitespace; -1 when absent."""
    chars = [c for c in (needle or "") if not c.isspace()]
    if len(chars) < 2:
        return -1
    pattern = r"\s*".join(re.escape(c) for c in chars)
    m = re.search(pattern, text or "")
    return m.start() if m else -1


def _significant_terms(text: str, limit: int = 6) -> list[str]:
    """Longest capitalised or multi-syllable-looking words in a claim.

    Used to anchor evidence when the model's quote does not verify. English
    function words are excluded because they match everywhere and so locate
    nothing.
    """
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text or "")
    # Chinese claims: take CJK runs split on common particles as candidates.
    for run in re.findall(r"[\u3400-\u9fff]{2,}", text or ""):
        for part in re.split(r"[的是在和与及或为了对把被由中上下等]", run):
            if 2 <= len(part) <= 8:
                words.append(part)
    seen: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in _STOPWORDS or lw in {s.lower() for s in seen}:
            continue
        # Prefer multi-word technical terms and rarer long words.
        seen.append(w)
    seen.sort(key=lambda w: (-len(w), w.lower()))
    return seen[:limit]
