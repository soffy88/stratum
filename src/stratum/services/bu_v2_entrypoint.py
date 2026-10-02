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
    ChapterUnderstandingProducer,
    EvidenceArtifact,
)
from stratum.services.bu_v2_provider import (
    ModelProvider,
    ProviderError,
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

    @property
    def verified(self) -> bool:
        return self.bu is not None and self.bu.status == BUStatus.VERIFIED


class BookLoader:
    """§6: load a book from a substrate.

    Prefers the parser's chapter index, because the parser saw page structure
    the markdown has already lost. Falls back to markdown headings.
    """

    def load(self, substrate_id: str) -> tuple[str, str, list[Chapter]]:
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
        if index_raw:
            try:
                headings = json.loads(index_raw)
            except json.JSONDecodeError:
                headings = []
            if headings:
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
        for m in re.finditer(r"^(#{1,3})\s*" + re.escape(str(num)) + r"\.?\s+" + re.escape(probe), text, re.M):
            level = len(m.group(1))
            if level == 1:
                return m.start()
            if best is None or level < best[0]:
                best = (level, m.start())
        if best is not None:
            return best[1]

        # Signal 2: a bare "N Title" line, then OVERVIEW shortly after.
        overview = re.compile(r"^\s*OVERVIEW\b", re.M)
        for m in re.finditer(r"^\s*" + re.escape(str(num)) + r"\.?\s+" + re.escape(probe), text, re.M):
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


class BU2Runner:
    """§6: the interface the spec defines, and the whole book pipeline."""

    def __init__(
        self,
        *,
        provider: ModelProvider | None = None,
        loader: BookLoader | None = None,
        persist: bool = False,
        chapter_limit: int | None = None,
    ):
        self.provider = provider or resolve_provider()
        self.loader = loader or BookLoader()
        self.producer = ChapterUnderstandingProducer(provider=self.provider)
        self.integrator = BookIntegrator(provider=self.provider)
        self.verifier = BUVerifier()
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
        title, _text, chapters = self.loader.load(substrate_id)
        if not chapters:
            raise BU2RunError(
                f"{substrate_id} ({title}) yielded no chapterable structure; "
                "no numbered headings and no usable parser index"
            )

        if self.chapter_limit:
            chapters = chapters[: self.chapter_limit]

        run_id = self.create_run(substrate_id)
        result = RunResult(run_id=run_id, book_id=substrate_id, substrate_id=substrate_id)

        # ── generate_chapters ──────────────────────────────────────────────
        prior: list[str] = []
        for chapter in chapters:
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

        if not result.chapters:
            raise BU2RunError("no chapter produced an understanding")

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

        if self.persist:
            self._persist_bu(result)

        # ── generate_expression ────────────────────────────────────────────
        result.expression = self.expr.generate(bu)
        return result

    @staticmethod
    def _integration_input(result: RunResult) -> IntegrationInput:
        return IntegrationInput(
            run_id=result.run_id,
            book_id=result.book_id,
            substrate_id=result.substrate_id,
            chapters=result.chapters,
            deltas=result.deltas,
            evidence_by_chapter={},
            genre="",
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

        for cu in result.chapters:
            ChapterUnderstandingRepository.save(cu)
        for delta in result.deltas:
            ChapterDeltaRepository.save(delta)
        result.persisted = True

    def _persist_bu(self, result: RunResult) -> None:
        from stratum.services.bu_v2_repositories import (
            BookUnderstandingRepository,
            VerificationRepository,
        )

        BookUnderstandingRepository.save(result.bu)
        VerificationRepository.save(self.verifier.to_artifact(result.report, result.bu))
        if result.bu.status == BUStatus.VERIFIED:
            db.update("book_reading_run", result.run_id, {"status": "VERIFIED"})
        else:
            db.update("book_reading_run", result.run_id, {"status": "FAILED"})
        result.persisted = True


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m stratum.services.bu_v2_entrypoint <substrate_id>``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="bu2", description="Produce a BookUnderstandingV2 from a substrate"
    )
    parser.add_argument("substrate_id", help="stratum.substrates.id of the book")
    parser.add_argument("--provider", default=None, help="ollama|deepseek|nim|anthropic|gemini|openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--chapters", type=int, default=None, help="limit chapters processed")
    parser.add_argument("--persist", action="store_true", help="write to the database")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    kw: dict[str, Any] = {"persist": args.persist, "chapter_limit": args.chapters}
    if args.provider:
        kw["provider"] = resolve_provider(args.provider, **({"model": args.model} if args.model else {}))
    elif args.model:
        kw["provider"] = resolve_provider(None, model=args.model)

    runner = BU2Runner(**kw)
    try:
        result = runner.execute(args.substrate_id)
    except (BU2RunError, ProviderUnavailable) as exc:
        print(f"bu2: {exc}")
        return 2

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
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        if result.expression:
            print(result.expression.render())
        if result.report:
            print(f"\nverification: {result.report.outcome.value} "
                  f"({len(result.report.checks)} checks, {len(result.report.failed)} failed)")
        print(f"run_id={result.run_id} chapters={len(result.chapters)} "
              f"evidence={len(result.evidence)} persisted={result.persisted}")
        for f in result.failures:
            print(f"  ! {f}")
    return 0 if (result.bu and result.bu.status == BUStatus.VERIFIED) else 1


if __name__ == "__main__":
    raise SystemExit(main())