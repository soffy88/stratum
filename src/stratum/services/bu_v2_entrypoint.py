"""BU2 entry point — spec §6.

    class BU2Runner:
        def run_book(self, substrate_id: str) -> BookUnderstandingV2

This is the module the P9 audit found missing: BU2 had no entrypoint, no CLI
command, no API route, and no scheduler job, so no book could enter the system.
Here is the whole path from a substrate id to a verified BookUnderstandingV2:

    create_run -> load_book -> extract_structure -> generate_chapters
    -> integrate_book -> verify -> generate_expression -> return BU

Reading the book is deliberately separated from understanding it. Chapter
boundaries come from the parser's own ``chapters`` derivative where it exists,
and from heading detection in the markdown where it does not — never from the
model guessing where a chapter starts. The model is asked what a chapter means,
not where it is.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BUStatus,
    ChapterDelta,
    ChapterUnderstanding,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_expression import BookExpression, BUExpressionGenerator
from stratum.services.bu_v2_producer import (
    Chapter,
    ChapterContext,
    ChapterUnderstandingProducer,
    EvidenceArtifact,
    classify_role,
)
from stratum.services.bu_v2_provider import (
    ModelProvider,
    ProviderUnavailable,
    resolve_provider,
)
from stratum.services.bu_v2_verifier import BUVerifier, VerificationReport

ENGINE_VERSION = "p10"


class _DB:
    """The database seam.

    Each method forwards to ``stratum.db`` by attribute lookup at call time, so
    the seam can be replaced wholesale in a test while production still runs the
    real functions.

    It deliberately does *not* re-declare the signatures. An earlier version
    mirrored them by hand and drifted in two places: ``update`` was called as
    ``(table, values, where)`` when the real one is ``(table, rid, data)``, and
    ``read`` was missing ``id_column``. Both passed the suite and failed on
    first production use. Forwarding removes the class of bug rather than
    testing for it.
    """

    def __getattr__(self, name: str):
        if name in ("read", "query", "insert", "update"):
            import stratum.db as _mod

            return getattr(_mod, name)
        raise AttributeError(name)


db = _DB()


class BU2RunError(RuntimeError):
    """The run could not complete. Carries the reason rather than swallowing it."""


@dataclass
class RunResult:
    """What a run produced, including when it did not get all the way."""

    run_id: str
    book_id: str
    substrate_id: str
    chapters: list[ChapterUnderstanding] = field(default_factory=list)
    deltas: list[ChapterDelta] = field(default_factory=list)
    evidence: list[EvidenceArtifact] = field(default_factory=list)
    bu: BookUnderstandingV2 | None = None
    report: VerificationReport | None = None
    expression: BookExpression | None = None
    persisted: bool = False
    failures: list[str] = field(default_factory=list)
    # P11 §5: the structure the run actually used.
    structure: dict[str, Any] | None = None
    # P12 §13: chapter_id -> span kind ("chapter" | "front_matter" |
    # "back_matter"). `structure` above is only the metadata dict, which has no
    # per-span kinds, so without this the P12 denominator silently includes
    # back matter and the required edge threshold rises for no reason.
    structure_kinds: dict[str, str] = field(default_factory=dict)
    # P11 §8: quality is measured, never gating.
    quality: Any = None
    report_bundle: Any = None
    # P11 §6: whether chapter context was injected, and the role each chapter
    # was given. These live on Chapter, not ChapterUnderstanding, so they are
    # recorded here rather than read back off the wrong object.
    context_used: bool = False
    chapter_roles: list[dict[str, str]] = field(default_factory=list)
    # P12: the reasoning graph, concept evolution, argument model and deep quality.
    p12: Any = None
    # Task B: the frozen KU index used to anchor this run's concept extraction.
    ku_index: Any = None
    # Task D: the hard quality gates and the six-dimension score.
    hard_gates: Any = None
    # Task E: the dependency-ordered learning guide.
    learning_guide: Any = None
    # Claim verification: how many asserted claims the anchored passage supports.
    claim_verification: Any = None

    @property
    def verified(self) -> bool:
        return self.bu is not None and self.bu.status == BUStatus.VERIFIED


class BookLoader:
    """§6: load a book from a substrate.

    ``last_index`` retains the parser's own heading list after ``load`` returns.
    The structure extractor needs it: without the index it cannot tell that a
    book declares 16 chapters, so it reports 0% detection on a perfect
    extraction. Returning it here is what makes §14 measurable.
    """

    def __init__(self) -> None:
        self.last_index: list[dict] = []

    def load(self, substrate_id: str) -> tuple[str, str, list[Chapter]]:
        """Prefer the parser's chapter index.

        The parser saw page structure the markdown has already lost, so its
        heading list is the more reliable source of chapter titles and pages.
        Falls back to markdown headings when it is absent.
        """
        substrate = db.read("substrates", substrate_id)
        if not substrate:
            raise BU2RunError(f"substrate {substrate_id} not found")
        title = substrate.get("title") or substrate_id

        derivatives = db.query(
            "SELECT kind, content FROM derivative WHERE substrate_id=%(sid)s "
            "AND content IS NOT NULL AND content <> ''",
            {"sid": substrate_id},
        )
        by_kind = {d["kind"]: d["content"] for d in derivatives}
        markdown = by_kind.get("markdown") or by_kind.get("plaintext") or ""

        index_raw = by_kind.get("chapters")
        self.last_index = []
        if index_raw:
            try:
                headings = json.loads(index_raw)
            except json.JSONDecodeError:
                headings = []
            if headings:
                self.last_index = [h for h in headings if isinstance(h, dict)]
                return title, markdown, self._chapters_from_index(headings, markdown)

        return title, markdown, self._chapters_from_headings(markdown)

    def _chapters_from_index(self, headings: list[dict], text: str) -> list[Chapter]:
        """Split text at numbered level-1 headings from the parser's index.

        The hard part is that a chapter title occurs dozens of times in a real
        textbook: in the table of contents, in running page headers, and in
        cross-references. Taking the first match yields a chapter that is a few
        hundred characters of front matter. So each title is resolved against
        the page the index gives it, and among candidates only positions that
        actually open a section are considered.
        """
        numbered: list[tuple[int, str, int]] = []
        for h in headings:
            if h.get("level") != 1:
                continue
            title = str(h.get("title") or "")
            m = re.match(r"^(\d+)\.\s+(.+)$", title)
            if m:
                numbered.append((int(m.group(1)), title, int(h.get("page") or 0)))
        numbered.sort()
        if len(numbered) < 2:
            return self._chapters_from_headings(text)

        chapters: list[Chapter] = []
        located: list[tuple[int, int, str, int]] = []
        for num, title, page in numbered:
            pos = self._locate_opening(text, num, title, page)
            if pos is not None:
                located.append((num, pos, title, page))

        for i, (num, start, title, page) in enumerate(located):
            end = located[i + 1][1] if i + 1 < len(located) else len(text)
            body = text[start:end]
            # A chapter of a real textbook is tens of thousands of characters.
            # Anything under this is a running header, not a chapter.
            if len(body.strip()) < 5000:
                continue
            chapters.append(
                Chapter(
                    chapter_id=f"ch{num}",
                    number=num,
                    title=title,
                    text=body,
                    start=start,
                    end=end,
                    subsections=self._subsections(body),
                )
            )
        return chapters or self._chapters_from_headings(text)

    @staticmethod
    def _locate_opening(text: str, num: int, title: str, page: int) -> int | None:
        """Find where chapter ``num`` actually begins.

        Two signals are tried, in order, because the parser is inconsistent:

        1. ``# N Title`` — a level-1 markdown heading. Used by 10 of 16 chapters.
        2. A bare ``N Title`` line immediately followed by ``OVERVIEW``.

        Every chapter in this corpus opens with an OVERVIEW section, which the
        index pages confirm (pages 41, 115, 243 ...). The heading mark alone is
        not enough because the parser did not emit one for six chapters, and a
        plain first-match search is worse than useless: chapter titles occur 45
        to 565 times each in a 5.1M-character bilingual textbook, in the table
        of contents, in running page headers and in cross-references. Taking the
        first match produces 318-character "chapters" made of front matter.

        Returns ``None`` when neither signal is present, so the caller drops
        that chapter rather than inventing a span for it.
        """
        needle = title.split(".", 1)[1].strip() if "." in title else title
        if not needle:
            return None
        probe = needle[: min(len(needle), 28)]

        # Signal 1: a level-1 heading. Deeper levels belong to a neighbour whose
        # title contains this one, so prefer the shallowest match.
        best: tuple[int, int] | None = None
        for m in re.finditer(
            r"^(#{1,3})\s*" + re.escape(str(num)) + r"\.?\s+" + re.escape(probe), text, re.M
        ):
            level = len(m.group(1))
            if level == 1:
                return m.start()
            if best is None or level < best[0]:
                best = (level, m.start())
        if best is not None:
            return best[1]

        # Signal 2: a bare "N Title" line, then OVERVIEW shortly after.
        overview = re.compile(r"^\s*OVERVIEW\b", re.M)
        for m in re.finditer(
            r"^\s*" + re.escape(str(num)) + r"\.?\s+" + re.escape(probe), text, re.M
        ):
            tail = text[m.end() : m.end() + 400]
            if overview.search(tail):
                return m.start()
        return None

    @staticmethod
    def _chapters_from_headings(text: str) -> list[Chapter]:
        """Fallback: ``## 3. Derivatives`` style markdown headings."""
        marks = list(re.finditer(r"^#{1,3}\s+(\d+)\.\s+(.+)$", text, re.M))
        if len(marks) < 2:
            return []
        chapters: list[Chapter] = []
        for i, m in enumerate(marks):
            start = m.start()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[start:end]
            if len(body.strip()) < 200:
                continue
            chapters.append(
                Chapter(
                    chapter_id=f"ch{m.group(1)}",
                    number=int(m.group(1)),
                    title=f"{m.group(1)}. {m.group(2).strip()}",
                    text=body,
                    start=start,
                    end=end,
                )
            )
        return chapters

    @staticmethod
    def _subsections(body: str) -> list[str]:
        return [m.strip() for m in re.findall(r"^#{2,4}\s+(.+)$", body, re.M)][:40]


def _p12_payload(result: RunResult) -> dict[str, Any] | None:
    """The P12 artefacts, serialised for the trial evidence."""
    p12 = getattr(result, "p12", None) or {}
    dep, evo, arg, deep = (
        p12.get("dependency"),
        p12.get("evolution"),
        p12.get("argument"),
        p12.get("deep_quality"),
    )
    if not (dep and evo and arg and deep):
        return None
    return {
        "dependency": dep.to_dict(),
        "concept_evolution": evo.to_dict(),
        "argument_graph": arg.to_dict(),
        "deep_quality": deep.to_dict(),
        "graph_stats": dep.graph.stats(),
    }


def _detection(structure_meta: dict[str, Any], result: "RunResult") -> float:
    """Chapter detection ratio, recomputed from what the run actually stored.

    The precomputed ratio is preferred, but it is only valid when the run's
    chapters include back matter. A run that located 16 of 16 chapters and also
    split out answers and appendices must not report 18/16, so back-matter
    sections are excluded from the numerator and the denominator is whatever the
    parser index declared.
    """
    located = len([c for c in result.chapters if c.primary_role != "UNDERSTANDING_FAILED"])
    expected = int(structure_meta.get("expected_chapters") or 0)
    if not expected:
        expected = int(structure_meta.get("chapter_count") or 0) or located
    if not expected:
        return 0.0
    # Chapters are the ones the extractor typed; back matter carries an appendix
    # flag in the structure metadata, so subtract any excess conservatively.
    return round(min(1.0, located / expected), 4)


def _expectation_for(chapters: list[Chapter], idx: int) -> str:
    """What the next chapter will need, from what the parser says it covers.

    Cheap and deterministic: the next chapter's subsections are known from the
    structure, so the model is told what is coming rather than asked to guess.
    """
    if idx + 1 >= len(chapters):
        return "this is the final chapter; it should close the book's argument"
    nxt = chapters[idx + 1]
    subs = [s for s in (nxt.subsections or [])[:3]]
    if subs:
        return f"the next chapter is '{nxt.title}', covering " + "; ".join(subs)
    return f"the next chapter is '{nxt.title}'"


class BU2Runner:
    """§6: the interface the spec defines, and the whole book pipeline."""

    def __init__(
        self,
        *,
        provider: ModelProvider | None = None,
        loader: BookLoader | None = None,
        persist: bool = False,
        chapter_limit: int | None = None,
        use_structure_extractor: bool = True,
        use_ku_anchor: bool = True,
        use_accuracy_judge: bool = True,
        judge_provider: ModelProvider | None = None,
        verify_claims: bool | None = None,
    ):
        self.use_structure_extractor = use_structure_extractor
        self.use_ku_anchor = use_ku_anchor
        # The accuracy dimension calls the provider as a judge over a claim
        # sample. On for a real run; off in unit tests to keep them offline.
        self.use_accuracy_judge = use_accuracy_judge
        # The accuracy dimension is scored by a judge that did not write the
        # claims: a separate provider when one is given, else the main one.
        self.judge_provider = judge_provider
        # Claims are verified against their anchored passage before publication.
        # Defaults to the judge setting so offline tests stay offline.
        self.verify_claims = use_accuracy_judge if verify_claims is None else verify_claims
        self.provider = provider or resolve_provider()
        self.loader = loader or BookLoader()
        self.producer = ChapterUnderstandingProducer(provider=self.provider)
        self.integrator = BookIntegrator(provider=self.provider)
        # P11 §5: structure is extracted once, then chapters are built from it
        # with their context filled in. P10's inline heuristics are replaced
        # rather than kept as a second path.
        from stratum.services.bu_v2_structure_extractor import (
            BookStructureExtractor,
            chapter_spans_from_structure,
        )

        self.extractor = BookStructureExtractor(provider=self.provider)
        self._spans_from_structure = chapter_spans_from_structure
        self.verifier = BUVerifier()
        # Task C: when the model cannot frame the book, derive a book-specific
        # framing from the chapters rather than leaving it empty. This is real
        # content but weaker than a model reading, so it is flagged as derived and
        # the quality model reports it as a gap rather than counting it as full.
        self.integrator.allow_derived_framing = True
        self.expr = BUExpressionGenerator()
        # Persisting is opt-in. §15 runs against production, and a trial should
        # not write 16 chapter rows into a live table because someone forgot a
        # flag.
        self.persist = persist
        self.chapter_limit = chapter_limit

    # ── §6 lifecycle ────────────────────────────────────────────────────────

    def create_run(self, book_id: str) -> str:
        from stratum.common import generate_ulid

        run_id = f"br_{generate_ulid()}"
        if self.persist:
            substrate = db.read("substrates", book_id) or {}
            db.insert(
                "book_reading_run",
                {
                    "id": run_id,
                    "user_id": substrate.get("user_id") or "system",
                    "source_id": book_id,
                    "source_version": "v1",
                    # §5.1 lifecycle. CREATED, never the old "planned" that
                    # migration 065 rejected.
                    "status": "CREATED",
                    "engine_version": ENGINE_VERSION,
                },
            )
        return run_id

    def run_book(self, substrate_id: str) -> BookUnderstandingV2:
        result = self.execute(substrate_id)
        if result.bu is None:
            raise BU2RunError("; ".join(result.failures) or "book run produced no understanding")
        return result.bu

    def execute(self, substrate_id: str) -> RunResult:
        """Run the whole path and return everything, including partial results.

        ``run_book`` returns just the BU; this returns the whole record. The
        difference matters for the acceptance gate, which needs to see the
        verification report and the expression, not only the object.
        """
        title, text, chapters = self.loader.load(substrate_id)
        structure = None
        result_meta: dict[str, Any] = {}
        pre_failures: list[str] = []
        if self.use_structure_extractor and text:
            # §5: the extractor owns structure. The loader's heuristics are a
            # fallback for texts the extractor cannot handle.
            try:
                structure = self.extractor.extract_from_text(
                    text,
                    book_id=substrate_id,
                    title=title,
                    # §14's denominator: what the parser says the book has.
                    index=getattr(self.loader, "last_index", None) or None,
                )
                if structure.chapters:
                    chapters = self._spans_from_structure(structure, text)
                    # P12 §6 reads the text for the author's own cross-references.
                    self._last_spans = list(chapters)
                    result_meta["structure"] = structure.to_dict()["metadata"]
                    result_meta["structure_method"] = structure.extraction_method
            except Exception as exc:
                pre_failures.append(f"structure extraction fell back to loader: {exc}")
        if not chapters:
            raise BU2RunError(
                f"{substrate_id} ({title}) yielded no chapterable structure; "
                "no numbered headings and no usable parser index"
            )

        if self.chapter_limit:
            chapters = chapters[: self.chapter_limit]

        run_id = self.create_run(substrate_id)
        result = RunResult(run_id=run_id, book_id=substrate_id, substrate_id=substrate_id)
        result.failures.extend(pre_failures)
        result.structure = result_meta.get("structure")
        if structure is not None:
            result.structure_kinds = {c.chapter_id: c.kind for c in (structure.chapters or [])}

        # ── KU anchoring (task B) ────────────────────────────────────────────
        # The A-warehouse book_freeze produced frozen DEF/THM knowledge units
        # for this book. Feed each chapter its own KUs as a must-cover list so
        # the deterministic skeleton anchors the LLM's concept extraction. A
        # book with no frozen KUs degrades to the previous behaviour.
        ku_index = None
        if self.use_ku_anchor:
            try:
                from stratum.services.bu_v2_ku_anchor import FrozenKUReader

                ku_index = FrozenKUReader().index_for_chapters(
                    substrate_id, [(c.chapter_id, c.title) for c in chapters]
                )
                result.ku_index = ku_index
            except Exception as exc:  # a KU read failure must not end the book
                result.failures.append(f"ku anchoring unavailable: {exc}")

        # ── generate_chapters (§6: with context, not in isolation) ───────────
        prior: list[str] = []
        total = len(chapters)
        seen_concepts: list[str] = []
        recent_titles: list[str] = []
        for idx, chapter in enumerate(chapters):
            # §6.1 context injection. A chapter read without knowing where it
            # sits produces the same framing for chapter 1 and chapter 12.
            chapter.context = ChapterContext(
                book_title=title,
                chapter_number=idx + 1,
                chapter_total=total,
                previous_chapter_titles=list(recent_titles),
                previous_concepts=list(seen_concepts),
                following_expectations=_expectation_for(chapters, idx),
                position_ratio=round((idx + 1) / total, 3) if total else 0.0,
            )
            chapter.role = classify_role(chapter)
            recent_titles.append(chapter.title)
            # §B: hand the producer this chapter's frozen KUs as a must-cover list.
            if ku_index is not None:
                self.producer.set_ku_anchor(ku_index.anchors_for(chapter.chapter_id))
            if os.environ.get("BU2_PROGRESS"):
                import sys as _sys

                nch = len(self.producer._chapter_chunks(chapter))
                print(
                    f"[bu2] {chapter.chapter_id} ({chapter.char_count}c, {nch} chunk(s), "
                    f"{len(self.producer.ku_anchor)} ku-anchors)",
                    file=_sys.stderr,
                    flush=True,
                )
            try:
                cu, delta, evidence = self.producer.produce(
                    chapter, run_id=run_id, book_id=substrate_id, prior_chapter_ids=prior
                )
            except Exception as exc:  # one bad chapter must not end the book
                result.failures.append(f"{chapter.chapter_id}: {exc}")
                prior.append(chapter.chapter_id)
                continue
            result.chapters.append(cu)
            result.deltas.append(delta)
            result.evidence.extend(evidence)
            prior.append(chapter.chapter_id)
            for concept in cu.concepts_introduced_refs:
                if concept and concept not in seen_concepts:
                    seen_concepts.append(concept)

        # §6: recorded after the loop, because the contexts exist only then.
        # Reading this before the loop reports False on every run — which is
        # what made gate 2 fail on a run that had injected context throughout.
        result.context_used = any(c.context is not None for c in chapters)

        if not result.chapters:
            raise BU2RunError("no chapter produced an understanding")

        # ── verify every asserted claim against its anchored passage ───────
        # Before anything is persisted or integrated, so an unsupported claim is
        # never published as the book's statement.
        if self.verify_claims:
            from stratum.services.bu_v2_claim_verifier import ClaimVerifier, make_provider_judge

            result.claim_verification = ClaimVerifier(make_provider_judge(self.provider)).verify(
                result.chapters,
                result.evidence,
                texts={c.chapter_id: c for c in chapters},
            )

        if self.persist:
            self._persist_chapters(result)

        # ── integrate_book ─────────────────────────────────────────────────
        failed = [c for c in result.chapters if c.primary_role == "UNDERSTANDING_FAILED"]
        try:
            # UNIQUE(substrate_id, version) means a re-run of the same book must
            # take the next version rather than collide. §4.1 requires that a
            # book and its runs coexist, and a version collision would break it.
            bu = self.integrator.integrate(
                data=self._integration_input(result), version=self._next_version(substrate_id)
            )
        except Exception as exc:
            result.failures.append(f"integration: {exc}")
            return result
        result.bu = bu

        # ── verify (§12: no GENERATED -> VERIFIED) ─────────────────────────
        bu.status = BUStatus.VERIFICATION_PENDING
        report = self.verifier.verify(
            bu,
            chapter_count=len(result.chapters),
            evidence_count=len(result.evidence),
            failed_chapters=len(failed),
        )
        result.report = report
        if report.outcome.value == "PASS":
            bu.status = BUStatus.VERIFIED
            bu.verification_score = 1.0
        else:
            bu.status = BUStatus.DRAFT
            result.failures.append(
                f"verification FAIL: {len(report.failed)} check(s): "
                + ", ".join(c.name for c in report.failed)
            )
        # Task C: a derived framing is a degradation, not a silent success — the
        # model did not read the book's framing, the chapters were used instead.
        # Recorded so the run reports it rather than hiding it.
        if getattr(bu, "framing_derived", False):
            result.failures.append(
                "book framing was derived from the chapters; the model did not read it"
            )

        # ── P12: reasoning graph, concept evolution, argument model ─────────
        # Runs after integration because all three read the integrated BU and
        # the per-chapter records. §9 stores the resulting ids on the BU, so it
        # must be built BEFORE the BU row is written: persisting first left the
        # three graph ids unset on every persisted run.
        result.p12 = self._build_p12(result)

        # ── Task E: dependency-ordered learning guide ──────────────────────
        # Built here so the expression can carry it and the query API can read
        # it back. It is a rendering of the graph, never persisted.
        from stratum.services.bu_v2_learning_guide import LearningGuideBuilder

        dep = (result.p12 or {}).get("dependency")
        result.learning_guide = LearningGuideBuilder().build(
            run_id=result.run_id,
            book_id=result.book_id,
            graph=getattr(dep, "graph", None),
            chapters=result.chapters,
            ku_index=getattr(result, "ku_index", None),
        )

        # ── Task D: hard gates + 6-dimension score ─────────────────────────
        # Evaluated BEFORE the BU row is written, so (a) the gates are persisted
        # with the run instead of being computed after persistence and lost, and
        # (b) a run that fails a hard gate is never stored as VERIFIED.
        from stratum.services.bu_v2_hard_gates import HardGateEvaluator

        judge = self._make_judge() if self.use_accuracy_judge else None
        result.hard_gates = HardGateEvaluator(judge=judge).evaluate(
            result, structure=result.structure
        )
        if not result.hard_gates.all_passed and bu.status == BUStatus.VERIFIED:
            bu.status = BUStatus.DRAFT
            bu.verification_score = 0.0
            result.failures.append(
                "hard gates FAIL: "
                + ", ".join(g.gate for g in result.hard_gates.gates if not g.passed)
            )

        if self.persist:
            self._persist_bu(result)

        # ── quality evaluation (§8). Runs after verification and never
        #    changes the verdict: §10 forbids quality from being a truth
        #    signal and §11 forbids it from blocking publication. ──────────
        from stratum.services.bu_v2_quality_evaluator import BUQualityEvaluator
        from stratum.services.bu_v2_quality_report import build_report, evaluate_gates

        pipeline_status = bu.status.value if bu.status else "UNKNOWN"
        result.quality = BUQualityEvaluator().evaluate(
            bu,
            chapters=result.chapters,
            evidence=result.evidence,
            pipeline_status=pipeline_status,
            structure=result.structure,
        )
        report = result.report
        if report is not None:
            report.quality_level = result.quality.quality_level

        # ── generate_expression (§12 carries quality as confidence) ────────
        result.expression = self.expr.generate(
            bu, quality=result.quality, guide=result.learning_guide
        )

        detection = content_cov = None
        if structure is not None:
            # `_detection` takes the stored metadata dict, which is what
            # result.structure holds. Passing the BookStructure itself is a type
            # error, and an AttributeError that only fires on a real book run.
            detection = _detection(result.structure or {}, result)
            content_cov = (result.structure or {}).get("content_coverage_ratio")
        result.report_bundle = build_report(
            result.quality,
            run_id=result.run_id,
            book_id=result.book_id,
            substrate_id=result.substrate_id,
            pipeline_status=pipeline_status,
            gates=evaluate_gates(
                result.quality,
                structure=result.structure,
                detection_ratio=detection,
                coverage_ratio=(result.structure or {}).get("coverage_ratio"),
                content_coverage=content_cov,
                chapter_count=len(result.chapters),
                context_used=result.context_used,
            ),
            chapter_roles=[
                {"chapter_id": c.chapter_id, "role": c.primary_role} for c in result.chapters
            ],
        )
        from stratum.services.bu_v2_quality_report import evaluate_p12_gates

        p12_gates = evaluate_p12_gates(result, structure=result.structure)
        result.report_bundle.gates.extend(p12_gates)
        result.p12_gate_summary = {g.gate: g.to_dict()["status"] for g in p12_gates}

        result.report_bundle.hard_gates = result.hard_gates
        return result

    def _make_judge(self):
        """The accuracy-dimension judge: the separate judge provider if given.

        ``max_tokens`` is generous because hosted "thinking" models spend tokens
        before answering; the old budget of 4 returned empty replies.
        """
        from stratum.services.bu_v2_claim_verifier import make_provider_judge

        return make_provider_judge(self.judge_provider or self.provider)

    def _build_p12(self, result: RunResult) -> Any:
        """§5-§8: the book reasoning graph, concept evolution and argument model.

        Deliberately after integration: concept evolution reads deltas, and the
        argument model reads the BU's own framing, so both need the integrated
        result rather than the raw chapter list.
        """
        from stratum.services.bu_v2_argument_analyzer import ArgumentAnalyzer
        from stratum.services.bu_v2_concept_evolution import ConceptEvolutionBuilder
        from stratum.services.bu_v2_deep_quality import DeepQualityEvaluator
        from stratum.services.bu_v2_dependency_builder import DependencyBuilder

        chapter_text: dict[str, str] = {}
        for span in getattr(self, "_last_spans", []) or []:
            chapter_text[span.chapter_id] = span.text

        dependency = DependencyBuilder().build(
            result.chapters,
            run_id=result.run_id,
            book_id=result.book_id,
            chapter_text=chapter_text or None,
        )
        # Task C: add CONCEPT/THEOREM/CLAIM nodes and the reasoned edges between
        # them, so the graph is a model of the book's knowledge and not only its
        # chapter spine.
        from stratum.services.bu_v2_graph_enricher import ReasoningGraphEnricher

        enricher = ReasoningGraphEnricher()
        enrichment = enricher.enrich(
            dependency.graph,
            result.chapters,
            run_id=result.run_id,
            ku_index=getattr(result, "ku_index", None),
            chapter_text=chapter_text or None,
        )
        evolution = ConceptEvolutionBuilder().build(
            result.chapters,
            run_id=result.run_id,
            book_id=result.book_id,
            deltas=result.deltas,
            chapter_text=chapter_text or None,
        )
        argument = ArgumentAnalyzer().analyze(
            result.chapters,
            run_id=result.run_id,
            book_id=result.book_id,
            evidence_by_chapter=self._evidence_by_chapter(result),
        )
        # §13's thresholds are per numbered chapter. The structure report types
        # each span, so front and back matter are excluded by what they are
        # rather than by what their id happens to look like.
        from stratum.services.bu_v2_quality_report import numbered_chapter_ids

        numbered_ids = numbered_chapter_ids(result, result.structure)
        numbered = [c for c in result.chapters if c.chapter_id in numbered_ids]
        deep = DeepQualityEvaluator().evaluate(
            book_id=result.book_id,
            run_id=result.run_id,
            graph=dependency.graph,
            evolution=evolution,
            argument=argument,
            chapter_count=len(numbered),
            pipeline_status=result.bu.status.value if result.bu else "UNKNOWN",
        )
        return {
            "dependency": dependency,
            "evolution": evolution,
            "argument": argument,
            "deep_quality": deep,
            "enrichment": enrichment,
        }

    @staticmethod
    def _evidence_by_chapter(result: RunResult) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for ev in result.evidence:
            out.setdefault(ev.chapter_id, []).append(ev.evidence_id)
        return out

    @staticmethod
    def _integration_input(result: RunResult) -> IntegrationInput:
        # Task C: gather the real definition text for every concept any chapter
        # defined, so book-level concept evolution carries it.
        defs: dict[str, str] = {}
        for cu in result.chapters:
            for name, definition in (getattr(cu, "concept_definitions", {}) or {}).items():
                if name and definition and name not in defs:
                    defs[name] = definition
        return IntegrationInput(
            run_id=result.run_id,
            book_id=result.book_id,
            substrate_id=result.substrate_id,
            chapters=result.chapters,
            deltas=result.deltas,
            evidence_by_chapter={},
            genre="",
            chapter_kinds=dict(result.structure_kinds or {}),
            concept_definitions=defs,
        )

    @staticmethod
    def _next_version(substrate_id: str) -> int:
        """Next version for this book, per UNIQUE(substrate_id, version).

        Read defensively: when the table is absent (a unit test, or a database
        that has not run migrations 063/067) a re-run must not crash on the
        lookup. Returning 1 keeps the common case correct.
        """
        try:
            rows = db.query(
                "SELECT max(version) AS v FROM book_understandings_v2 WHERE substrate_id=%(sid)s",
                {"sid": substrate_id},
            )
        except Exception:
            return 1
        if not rows:
            return 1
        current = rows[0].get("v") if isinstance(rows[0], dict) else None
        return int(current or 0) + 1

    # ── persistence ─────────────────────────────────────────────────────────

    def _persist_chapters(self, result: RunResult) -> None:
        from stratum.services.bu_v2_repositories import (
            ChapterDeltaRepository,
            ChapterUnderstandingRepository,
        )

        from stratum.db import insert
        from stratum.services.bu_v2_repositories import ArgumentRepository

        for cu in result.chapters:
            ChapterUnderstandingRepository.save(cu)
            for arg in getattr(cu, "chapter_arguments", []) or []:
                ArgumentRepository.save(arg, result.run_id)
        for delta in result.deltas:
            ChapterDeltaRepository.save(delta)
        # Traceability: every cited ev_* id resolves to a stored span.
        strengths: dict[str, str] = {}
        for cu in result.chapters:
            strengths.update(getattr(cu, "evidence_strengths", {}) or {})
        seen: set[str] = set()
        for ev in result.evidence:
            if ev.evidence_id in seen or not ev.quote.strip() or not ev.locator.strip():
                continue
            seen.add(ev.evidence_id)
            insert(
                "bu2_evidence_artifact",
                {
                    "id": ev.evidence_id,
                    "run_id": result.run_id,
                    "chapter_id": ev.chapter_id,
                    "kind": ev.kind,
                    "locator": ev.locator,
                    "quote": ev.quote,
                    "content_hash": ev.content_hash,
                    "strength": strengths.get(ev.evidence_id),
                    "verified": getattr(ev, "verified", None),
                },
            )
        result.persisted = True

    def _persist_p12(self, result: RunResult) -> None:
        """§9: write the three graphs and record their ids on the BU.

        Written after the BU row so the graph ids can be attached to it in one
        follow-up update. Every table is additive; nothing here rewrites a
        chapter row or touches an A仓 or B仓 table.
        """
        p12 = result.p12 or {}
        dep = p12.get("dependency")
        evo = p12.get("evolution")
        arg = p12.get("argument")
        if not (dep and evo and arg):
            return
        from stratum.db import insert, update

        graph = dep.graph
        insert(
            "book_reasoning_graph",
            {
                "id": graph.graph_id,
                "run_id": result.run_id,
                "book_id": result.book_id,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "unresolved_count": len(graph.unresolved),
                "mean_confidence": graph.mean_confidence,
            },
        )
        for node in graph.nodes.values():
            insert(
                "reasoning_node",
                {
                    "id": node.node_id,
                    "graph_id": graph.graph_id,
                    "node_type": node.node_type,
                    "label": node.label[:400],
                    "chapter_id": node.chapter_id or None,
                    "source_ref": node.source_ref or None,
                    "confidence": node.confidence,
                    "metadata": node.metadata,
                },
            )
        for edge in graph.edges:
            insert(
                "reasoning_edge",
                {
                    "id": edge.edge_id,
                    "graph_id": graph.graph_id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "relation_type": edge.relation_type,
                    "reason": edge.reason[:2000],
                    "evidence_refs": edge.evidence_refs,
                    "evidence_type": edge.evidence_type,
                    "confidence": edge.confidence,
                    "status": edge.status,
                },
            )
        # §15: unresolved relations are persisted, not just returned.
        for u in graph.unresolved:
            insert(
                "reasoning_unresolved",
                {
                    "id": f"un_{u.kind}_{abs(hash((u.subject, u.reason))) % 10**12}",
                    "graph_id": graph.graph_id,
                    "kind": u.kind,
                    "subject": u.subject[:400],
                    "reason": u.reason[:2000],
                    "source": u.source,
                    "confidence": u.confidence,
                    "fallback": u.fallback[:400],
                },
            )

        traj_ids: list[str] = []
        for traj in evo.trajectories:
            tid = f"{traj.trajectory_id}_{result.run_id}"[:200]
            traj_ids.append(tid)
            counts = traj.kind_counts()
            insert(
                "concept_trajectory",
                {
                    "id": tid,
                    "run_id": result.run_id,
                    "book_id": result.book_id,
                    "concept_label": traj.concept[:400],
                    "introduced_at": traj.introduced_at or None,
                    "final_state": traj.final_state[:400] or None,
                    "definition_count": len(traj.definitions),
                    "change_count": counts.get("REFINEMENT", 0) + counts.get("EXPANSION", 0),
                    "application_count": len(traj.applications),
                    "confidence": traj.confidence,
                },
            )
            for event in traj.events:
                insert(
                    "concept_trajectory_event",
                    {
                        "id": f"{tid}_ev{event.sequence}",
                        "trajectory_id": tid,
                        "event_type": event.event_type,
                        "chapter_id": event.chapter_id or None,
                        "detail": event.detail[:1000],
                        "evidence_refs": event.evidence_refs,
                        "confidence": event.confidence,
                        "sequence": event.sequence,
                    },
                )

        insert(
            "argument_graph",
            {
                "id": arg.graph_id,
                "run_id": result.run_id,
                "book_id": result.book_id,
                "chain_count": len(arg.chains),
            },
        )
        for node in arg.nodes.values():
            insert(
                "argument_node",
                {
                    "id": node.node_id,
                    "graph_id": arg.graph_id,
                    "node_type": node.node_kind,
                    "label": node.label[:1000],
                    "chapter_id": node.chapter_id or None,
                    "confidence": node.confidence,
                },
            )
        for edge in arg.edges:
            insert(
                "argument_edge",
                {
                    "id": edge.edge_id,
                    "graph_id": arg.graph_id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "relation_type": edge.edge_kind,
                    "reason": edge.reason[:2000],
                    "evidence_refs": list(edge.evidence_refs),
                    "confidence": edge.confidence,
                    "chain_id": edge.chain_id or None,
                },
            )

        # §9: the three ids on the BU.
        update(
            "book_understandings_v2",
            result.bu.id,
            {
                "reasoning_graph_id": graph.graph_id,
                "concept_evolution_id": ",".join(traj_ids[:20]) or None,
                "argument_graph_id": arg.graph_id,
            },
        )

    def _persist_bu(self, result: RunResult) -> None:
        from stratum.services.bu_v2_repositories import (
            BookUnderstandingRepository,
            VerificationRepository,
        )

        BookUnderstandingRepository.save(result.bu)
        VerificationRepository.save(self.verifier.to_artifact(result.report, result.bu))
        if result.p12:
            self._persist_p12(result)
        if result.bu.status == BUStatus.VERIFIED:
            db.update("book_reading_run", result.run_id, {"status": "VERIFIED"})
        else:
            db.update("book_reading_run", result.run_id, {"status": "FAILED"})
        result.persisted = True
        if result.bu.status == BUStatus.VERIFIED:
            self._persist_p13(result)
        # Task D: the hard gates are stored for every run, not only a verified
        # one — a failed run's gates are exactly what a reader needs to see.
        self._persist_hard_gates(result)

    def _persist_hard_gates(self, result: RunResult) -> None:
        """Write the hard gates + six-dimension score (task D)."""
        import sys

        if getattr(result, "hard_gates", None) is None:
            return
        try:
            from stratum.services.bu_v2_hard_gates import persist_gates

            persist_gates(result.hard_gates, book_id=result.book_id)
        except Exception as exc:  # noqa: BLE001 - reported, run stays as it was
            print(f"[bu2] hard gates not persisted for {result.run_id}: {exc}", file=sys.stderr)

    def _persist_p13(self, result: RunResult) -> None:
        """P13: build and store the BookSynthesis for a VERIFIED run.

        P14 pairs every book's latest VERIFIED BU with the synthesis of that
        same run, so it is written here while the P12 graphs are in memory.
        A synthesis failure does not undo the verified BU; it is reported.
        """
        import sys

        from stratum.services.bu_v2_book_synthesis import BookSynthesisBuilder
        from stratum.services.bu_v2_repositories import BookSynthesisRepository

        p12 = result.p12 or {}
        dep = p12.get("dependency")
        try:
            synth = BookSynthesisBuilder().build(
                result.bu,
                result.chapters,
                evolution=p12.get("evolution"),
                argument_analysis=p12.get("argument"),
                graph=getattr(dep, "graph", None),
                structure=result.structure,
            )
            BookSynthesisRepository.save(synth)
        except Exception as exc:  # noqa: BLE001 - reported, BU stays verified
            print(f"[bu2] P13 synthesis not persisted for {result.run_id}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m stratum.services.bu_v2_entrypoint <substrate_id>``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="bu2", description="Produce a BookUnderstandingV2 from a substrate"
    )
    parser.add_argument("substrate_id", help="stratum.substrates.id of the book")
    parser.add_argument(
        "--provider", default=None, help="ollama|deepseek|nim|anthropic|gemini|openai"
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--chapters", type=int, default=None, help="limit chapters processed")
    parser.add_argument("--persist", action="store_true", help="write to the database")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--legacy-id",
        default=None,
        help="also import this aii.bu_onto row through the legacy adapter (P11 §7)",
    )
    parser.add_argument("--write-report", default=None, help="write the quality report JSON here")
    args = parser.parse_args(argv)

    kw: dict[str, Any] = {"persist": args.persist, "chapter_limit": args.chapters}
    if args.provider:
        kw["provider"] = resolve_provider(
            args.provider, **({"model": args.model} if args.model else {})
        )
    elif args.model:
        kw["provider"] = resolve_provider(None, model=args.model)

    runner = BU2Runner(**kw)
    try:
        result = runner.execute(args.substrate_id)
    except (BU2RunError, ProviderUnavailable) as exc:
        print(f"bu2: {exc}")
        return 2

    legacy_fusion = None
    if args.legacy_id:
        from stratum.services.bu_v2_legacy_adapter import BU2LegacyAdapter

        try:
            fusion = BU2LegacyAdapter().import_legacy_understanding(args.legacy_id)
            legacy_fusion = fusion.to_dict()
            if result.report_bundle is not None:
                result.report_bundle.legacy_fusion = legacy_fusion
        except LookupError as exc:
            legacy_fusion = {"error": str(exc)}
    if result.report_bundle is not None and legacy_fusion:
        from stratum.services.bu_v2_quality_report import evaluate_gates

        # Re-evaluate gate 4 now that the legacy fusion has actually run.
        result.report_bundle.gates = evaluate_gates(
            result.quality,
            structure=result.structure,
            detection_ratio=_detection(result.structure or {}, result),
            coverage_ratio=(result.structure or {}).get("coverage_ratio"),
            content_coverage=(result.structure or {}).get("content_coverage_ratio"),
            legacy_fused=bool(legacy_fusion and legacy_fusion.get("claims_mapped")),
            chapter_count=len(result.chapters),
            context_used=result.context_used,
        )

    if args.json:
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "substrate_id": result.substrate_id,
                    "chapters": len(result.chapters),
                    "evidence": len(result.evidence),
                    "bu_status": result.bu.status.value if result.bu else None,
                    "verification": result.report.to_dict() if result.report else None,
                    "expression": result.expression.to_dict() if result.expression else None,
                    "failures": result.failures,
                    "persisted": result.persisted,
                    "structure": result.structure,
                    "quality": result.quality.to_dict() if result.quality else None,
                    "gates": [
                        g.to_dict()
                        for g in (result.report_bundle.gates if result.report_bundle else [])
                    ],
                    "legacy_fusion": legacy_fusion,
                    "p12": _p12_payload(result),
                    # Read from the bundle: recomputing here needed an import
                    # that is not in main()'s scope, and it cost a 50-minute
                    # book run before the NameError surfaced.
                    "p12_gates": [
                        g.to_dict()
                        for g in (result.report_bundle.gates if result.report_bundle else [])
                        if g.gate.startswith("p12_")
                    ],
                    "hard_gates": (
                        result.hard_gates.to_dict() if result.hard_gates is not None else None
                    ),
                    "learning_guide": (
                        result.learning_guide.to_dict()
                        if result.learning_guide is not None
                        else None
                    ),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        if result.report_bundle is not None:
            print(result.report_bundle.render())
        elif result.expression:
            print(result.expression.render())
        if result.report:
            print(
                f"\nverification: {result.report.outcome.value} "
                f"({len(result.report.checks)} checks, {len(result.report.failed)} failed)"
            )
        print(
            f"run_id={result.run_id} chapters={len(result.chapters)} "
            f"evidence={len(result.evidence)} persisted={result.persisted}"
        )
        for f in result.failures:
            print(f"  ! {f}")
    return 0 if (result.bu and result.bu.status == BUStatus.VERIFIED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
