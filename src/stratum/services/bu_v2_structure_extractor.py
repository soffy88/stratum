"""Book structure extraction — spec §5.

P10 located 11 of 16 chapters in the trial book. The cause was not a bug but a
modelling error: it searched for chapter *titles*, and in a 5.1M-character
bilingual textbook each title occurs 45 to 565 times (table of contents,
running page headers, cross-references, the Chinese translation).

The reliable signal is different, and it was measurable rather than guessed.
Every chapter in this corpus opens with an ``OVERVIEW`` section:

    OVERVIEW count: 16    numbered level-1 chapters in the parser index: 16
    positions strictly increasing: True
    index page order 41,115,243 ... 1949 matches document order

So ``OVERVIEW`` is the anchor, the parser index supplies the titles, and the
title is used to label a span rather than to find one.

Three detection levels, in descending confidence, per §5.5:

  L1  explicit marker   ``# 6 Applications of Definite Integrals``  conf 0.98
  L2  typography signal heading of any depth, or ``N Title`` + OVERVIEW  0.90
  L3  semantic fallback provider is asked whether a span opens a chapter    0.55

§5.6 forbids a low-confidence node overwriting a high-confidence one, so
boundary proposals are resolved by confidence, not by arrival order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

DetectionLevel = Literal["L1_EXPLICIT", "L2_TYPOGRAPHY", "L3_SEMANTIC"]

# A chapter in a real textbook is tens of thousands of characters. Below this a
# "chapter" is a running header, and accepting it would silently fragment the
# book — which is exactly what P10 did before the OVERVIEW anchor was found.
MIN_CHAPTER_CHARS = 5000

# Lines scanned back from an OVERVIEW marker looking for the chapter heading.
# A character window fails on real books: 400 characters above chapter 1 of the
# trial book contained only dedication text.
TITLE_LOOKBACK_LINES = 12

_OVERVIEW = re.compile(r"\bOVERVIEW\b")
# Not anchored to ^: after OCR and markdown reflow a heading is routinely glued
# onto the end of a long paragraph line, and a ^-anchored pattern then never
# matches it. ( ) keeps the capture groups intact; a line longer than
# MAX_HEADING_LINE is not treated as a heading at all, which is what stops this
# from matching a number in the middle of a sentence.
_NUM_TITLE = re.compile(
    r"(?:^|[\s>|])(?:Chapter\s+|CHAPTER\s+)?(\d{1,2})\s*[.:、]\s+(.{3,80}?)\s*$"
)
_H1_NUM_TITLE = re.compile(r"#\s*(\d{1,2})\s*[.:、]?\s+(.{3,80}?)\s*$")

HEADING_TAIL_CHARS = 160
_PAGE_NUM = re.compile(r"\bpage\s+(\d{1,5})\b", re.I)

# Where a chapter's body starts, for books whose index numbers chapters as
# "Chapter 3 Demand and Supply" and whose markdown keeps no level-1 heading.
# An OpenStax-style textbook opens every chapter with a "Chapter Objectives"
# heading, and the marker fires exactly once per chapter. Tried only after the
# heading scan has already failed, and only when the parser index declares more
# chapters than that scan found — so a book that genuinely has few chapters is
# never cut into more pieces than it has.
_CHAPTER_OPENING = re.compile(r"^#{1,6}\s*\*{0,2}(?:Chapter|Learning)\s+Objectives\b", re.M)

# The chapter number in a parser-index title, in the two shapes this corpus
# uses: "3. Demand and Supply" and "Chapter 3 Demand and Supply".
# The third shape is the Chinese one the Tongji textbook uses: "第1章 函数与极限".
_INDEX_CH_NUM = re.compile(
    r"^(?:chapter\s+|第\s*)?(\d{1,2})\s*(?:章|节)?\s*[.:、]?\s+(.+?)\s*$", re.I
)

# Where worked answers, appendices or an index begin. Used to stop the last
# chapter at real content rather than swallowing the back matter.
_BACK_MATTER = re.compile(
    r"ANSWERS TO ODD-NUMBERED EXERCISES"
    r"|^#{0,6}\s*APPENDIX\s+\d"
    r"|^#{1,6}\s*(Applications\s+|General\s+)?Index\b",
    re.M,
)


@dataclass
class ChapterSpan:
    """One detected chapter. §5.4."""

    chapter_id: str
    title: str
    start_offset: int
    end_offset: int
    confidence: float
    detection_level: DetectionLevel = "L2_TYPOGRAPHY"
    kind: Literal["chapter", "back_matter", "front_matter"] = "chapter"
    page: int | None = None
    # True for back matter: worked answers, appendices, index. These are book
    # content but they are not numbered chapters, so they must not inflate the
    # chapter-detection ratio that §14 measures.
    is_appendix: bool = False
    subsections: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return max(0, self.end_offset - self.start_offset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": round(self.confidence, 3),
            "detection_level": self.detection_level,
            "page": self.page,
            "is_appendix": self.is_appendix,
            "kind": self.kind,
            "char_count": self.char_count,
            "subsections": self.subsections[:40],
        }


@dataclass
class BookStructure:
    """§5.4 output."""

    book_id: str
    title: str = ""
    chapters: list[ChapterSpan] = field(default_factory=list)
    front_matter_chars: int = 0
    back_matter_chars: int = 0
    total_chars: int = 0
    extraction_method: str = "overview_anchor"
    version: str = "p11"
    expected_chapters: int = 0

    @property
    def coverage_ratio(self) -> float:
        """Fraction of the document assigned to a section.

        Denominator is the whole document, so front matter and the index count
        as uncovered. §14 asks for ≥99% and this measure is the honest one: a
        figure computed against chapter text alone would read 100% while
        ignoring 198,632 characters of real material.
        """
        if not self.total_chars:
            return 0.0
        return round(sum(c.char_count for c in self.chapters) / self.total_chars, 4)

    @property
    def content_coverage_ratio(self) -> float:
        """Coverage of everything that is neither front matter nor an index.

        The 135,333-character index is a locator and the 63,299-character
        preface is front matter; neither is content a chapter could describe.
        This measure answers "how much of the book's substance did we locate",
        and it is reported alongside ``coverage_ratio`` rather than instead of
        it, so neither number is read alone.
        """
        addressable = self.total_chars - self.front_matter_chars - self.back_matter_chars
        if addressable <= 0:
            return 0.0
        return round(sum(c.char_count for c in self.chapters) / addressable, 4)

    @property
    def chapter_detection_ratio(self) -> float:
        """Located chapters against the chapters the parser index declares."""
        numbered = [c for c in self.chapters if c.kind == "chapter"]
        if not self.expected_chapters:
            return 0.0
        return round(len(numbered) / self.expected_chapters, 4)

    @property
    def confidence_mean(self) -> float:
        real = [c for c in self.chapters if c.kind == "chapter"]
        if not real:
            return 0.0
        return round(sum(c.confidence for c in real) / len(real), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_id": self.book_id,
            "title": self.title,
            "chapters": [c.to_dict() for c in self.chapters],
            "metadata": {
                "extraction_method": self.extraction_method,
                "version": self.version,
                "chapter_count": len([c for c in self.chapters if c.kind == "chapter"]),
                "back_matter_count": len([c for c in self.chapters if c.kind == "back_matter"]),
                # §14 measures detection against what the book declares, not
                # against what the detector happened to find. Carrying the
                # denominator forward is what makes the ratio interpretable
                # after the structure has been serialised.
                "expected_chapters": self.expected_chapters,
                "confidence_mean": self.confidence_mean,
                "coverage_ratio": self.coverage_ratio,
                "content_coverage_ratio": self.content_coverage_ratio,
                "chapter_detection_ratio": self.chapter_detection_ratio,
                "front_matter_chars": self.front_matter_chars,
                "back_matter_chars": self.back_matter_chars,
                "total_chars": self.total_chars,
            },
        }


class BookStructureExtractor:
    """§5.3: substrate id in, BookStructure out."""

    def __init__(self, provider: Any | None = None, *, min_chapter_chars: int = MIN_CHAPTER_CHARS):
        self.provider = provider
        self.min_chapter_chars = min_chapter_chars

    def extract(self, substrate_id: str) -> BookStructure:
        from stratum.services.bu_v2_entrypoint import db

        substrate = db.read("substrates", substrate_id) or {}
        title = substrate.get("title") or substrate_id
        rows = db.query(
            "SELECT kind, content FROM derivative WHERE substrate_id=%(sid)s "
            "AND content IS NOT NULL AND content <> ''",
            {"sid": substrate_id},
        )
        by_kind = {r["kind"]: r["content"] for r in rows}
        text = by_kind.get("markdown") or by_kind.get("plaintext") or ""
        index = _parse_index(by_kind.get("chapters"))
        return self.extract_from_text(text, book_id=substrate_id, title=title, index=index)

    def extract_from_text(
        self,
        text: str,
        *,
        book_id: str,
        title: str = "",
        index: list[dict] | None = None,
    ) -> BookStructure:
        """The testable core. Takes text, not a substrate id.

        Kept separate so the detector can be exercised against synthetic books —
        normal, bilingual, repeated-title and missing-heading — without a
        database or a fixture on disk.
        """
        structure = BookStructure(book_id=book_id, title=title, total_chars=len(text))
        # §14 measures detection against what the book declares it has, so the
        # parser index is the denominator rather than what we happened to find.
        structure.expected_chapters = len(_index_titles(index))
        if not text:
            return structure

        anchors = self._overview_anchors(text)
        if anchors:
            structure.extraction_method = "overview_anchor"
            structure.chapters = self._from_overviews(text, anchors, index)
        else:
            structure.extraction_method = "heading_scan"
            structure.chapters = self._from_headings(text, index)
            # Heading scan keys on level-1/2 markdown headings. Some books (the
            # OpenStax economics texts) carry their chapter numbers only in the
            # parser index ("Chapter 3 Demand and Supply") and open each body
            # with a "Chapter Objectives" heading instead of a numbered one. The
            # scan then finds 2–3 spans and silently drops ~19 chapters. When the
            # index declares far more chapters than the scan found, fall back to
            # locating each chapter by its index title and opening marker. The
            # index is the denominator §14 trusts, so using it here is measured,
            # not guessed.
            # The scan has to be clearly behind the index: it loses when it found
            # at least half of what the index declares. An integer-halved
            # threshold was the original form and it let a 21-chapter book with
            # 1 heading through (1 < 10), while a 3-chapter book with 1 heading
            # and 2 indexed titles was blocked (1 < 1) — the same condition
            # inverted on the two ends of the range.
            if len(structure.chapters) * 2 < len(_index_titles(index)):
                indexed = self._from_index_openings(text, index)
                if len(indexed) > len(structure.chapters):
                    structure.extraction_method = "index_openings"
                    structure.chapters = indexed

        self._resolve_boundaries(structure, text)
        structure.chapters = [
            c for c in structure.chapters if c.char_count >= self.min_chapter_chars
        ]
        self._renumber(structure)
        self._split_back_matter(structure, text)

        first = structure.chapters[0].start_offset if structure.chapters else 0
        structure.front_matter_chars = max(0, first)
        last = structure.chapters[-1].end_offset if structure.chapters else len(text)
        structure.back_matter_chars = max(0, len(text) - last)
        return structure

    def _split_back_matter(self, structure: BookStructure, text: str) -> None:
        """Give worked answers and appendices their own sections.

        Measured on the trial book: after chapter 16 the derivative carries
        1,073,738 characters — 20.9% of the book — of worked answers
        (566,796), appendices (30,510) and an index (135,333). Folding all of
        it into chapter 16 loses three genuinely different kinds of content.

        This does not inflate coverage. It makes existing coverage legible,
        which is what §14 asks to be measured. The index is excluded outright
        because an index is a locator, not content.
        """
        if not structure.chapters:
            return
        last = structure.chapters[-1]
        tail_start = last.end_offset
        # When the last span runs to EOF (the index-openings path leaves it there
        # until this runs) there is no tail to scan, so scan the last chapter
        # itself: the appendices and index live inside it. Without this an
        # OpenStax-style book folded ~340 KB of appendices into chapter 21.
        search_from = tail_start
        if structure.total_chars - tail_start < self.min_chapter_chars:
            search_from = last.start_offset
        if structure.total_chars - search_from < self.min_chapter_chars:
            return

        tail = text[search_from:]
        tail_start = search_from
        marks: list[tuple[str, int, bool]] = []
        for label, pattern, is_appendix in (
            # Worked answers can be a bare line or a "# " heading.
            ("Worked Answers", r"ANSWERS TO ODD-NUMBERED EXERCISES|ANSWERS TO SELECTED", False),
            # Appendices appear both as "# Appendix 1" and as "**Appendix A**",
            # the latter being how the OpenStax economics books mark them.
            (
                "Appendices",
                r"^#{0,6}\s*APPENDIX\s+\d|^#{0,6}\s*APPENDICES\b|\*\*APPENDIX\s+[A-Z]\*\*",
                True,
            ),
            # An index can be a "# Index" heading or the bold "Index 617" line
            # the economics books close on. Either way it is a locator, excluded.
            ("Index", r"^#{1,6}\s*(Applications\s+|General\s+)?Index\b|\*\*Index\b", True),
        ):
            m = re.search(pattern, tail, re.M)
            # A marker at relative offset 0 is expected for the first one: the
            # previous chapter has already been trimmed back to it. Only a
            # marker found inside the tail body needs the size guard, which
            # exists to skip an incidental mention in running prose.
            if m and (m.start() == 0 or m.start() >= self.min_chapter_chars or label == "Index"):
                marks.append((label, tail_start + m.start(), is_appendix))
        marks.sort(key=lambda x: x[1])

        # A trailing index is a locator, not content: excluded rather than
        # counted, so coverage never claims to have understood it.
        excluded_from = structure.total_chars
        while marks and marks[-1][0] == "Index":
            excluded_from = marks[-1][1]
            marks.pop()
        if not marks:
            return

        last.end_offset = marks[0][1]
        limit = excluded_from
        for i, (label, start, is_appendix) in enumerate(marks):
            end = marks[i + 1][1] if i + 1 < len(marks) else limit
            if end - start < self.min_chapter_chars:
                # Too small to be a section. Give it back to the previous one
                # rather than dropping real book content on the floor.
                if structure.chapters:
                    structure.chapters[-1].end_offset = end
                continue
            structure.chapters.append(
                ChapterSpan(
                    # Back matter still needs an identity. An empty chapter_id
                    # made two back-matter sections derive the same
                    # ChapterUnderstanding id, and the write failed on a
                    # duplicate key 50 minutes into a book run.
                    chapter_id=f"bm{i + 1}",
                    title=label,
                    start_offset=start,
                    end_offset=end,
                    confidence=0.85,
                    detection_level="L1_EXPLICIT",
                    is_appendix=is_appendix,
                    kind="back_matter",
                )
            )
        # Anything between the last kept section and the excluded index belongs
        # to that last section, not to nothing.
        if structure.chapters and structure.chapters[-1].end_offset < limit:
            structure.chapters[-1].end_offset = limit

    # ── level 2: the OVERVIEW anchor ────────────────────────────────────────

    @staticmethod
    def _overview_anchors(text: str) -> list[int]:
        return [m.start() for m in _OVERVIEW.finditer(text)]

    def _from_overviews(
        self, text: str, anchors: list[int], index: list[dict] | None
    ) -> list[ChapterSpan]:
        """Pair each OVERVIEW with a title, preferring one found nearby.

        Titles come from two sources, and the order matters: a heading in the
        document beats the parser index, because the index can disagree with
        the body after a re-parse.
        """
        titles = _index_titles(index)
        spans: list[ChapterSpan] = []
        for i, pos in enumerate(anchors):
            end = anchors[i + 1] if i + 1 < len(anchors) else len(text)
            body = text[pos:end]
            title, level, confidence = self._title_near(text, pos, titles.get(i + 1))
            spans.append(
                ChapterSpan(
                    chapter_id=f"ch{i + 1}",
                    title=title or titles.get(i + 1, f"Chapter {i + 1}"),
                    start_offset=pos,
                    end_offset=end,
                    confidence=confidence,
                    detection_level=level,
                    subsections=self._subsections(body),
                )
            )
        return spans

    def _title_near(
        self, text: str, anchor: int, fallback: str | None
    ) -> tuple[str, DetectionLevel, float]:
        """Find the chapter's title in the lines just above its OVERVIEW.

        The search window is measured in **lines, not characters**. A character
        window is the obvious implementation and it is wrong: on the trial book
        a 400-character window above chapter 1 contained nothing but the
        dedication text, because a heading sits above a page of front matter.
        Scanning back a fixed number of lines finds the heading regardless of how
        much prose precedes it.

        Twelve lines is the bound. Measured, every chapter title in the trial
        book sits within six lines above its OVERVIEW; twelve leaves headroom
        for a bilingual heading pair without reaching into the previous chapter.
        """
        start = text.rfind("\n", 0, max(0, anchor - 1))
        window_start = start
        # Count *non-blank* lines back, not raw lines. A chapter heading is
        # routinely preceded by a dozen blank lines in markdown, and walking raw
        # lines stops in the whitespace before reaching the heading at all.
        for _ in range(TITLE_LOOKBACK_LINES):
            if window_start <= 0:
                window_start = 0
                break
            window_start = text.rfind("\n", 0, window_start - 1)
            if window_start <= 0:
                window_start = 0
                break
        lines = [ln.strip() for ln in text[window_start:anchor].split("\n") if ln.strip()]

        # L1: an explicit "# N Title" heading. Highest confidence.
        for line in reversed(lines):
            m = _H1_NUM_TITLE.search(_tail(line))
            if m:
                return f"{m.group(1)}. {m.group(2).strip()}", "L1_EXPLICIT", 0.98

        # L2: a heading of any depth whose text matches the indexed title.
        target = _norm(fallback or "")
        for line in reversed(lines):
            tail = _tail(line)
            if "#" not in tail or _is_noise(tail):
                continue
            body = tail.lstrip("#").split("#")[-1].strip()
            m = _NUM_TITLE.search(body)
            candidate = _norm(f"{m.group(1)} {m.group(2)}" if m else body)
            if target and candidate and (candidate == target or target.startswith(candidate[:20])):
                label = f"{m.group(1)}. {m.group(2).strip()}" if m else body
                return label, "L2_TYPOGRAPHY", 0.92

        # L2: a bare "N Title" line.
        for line in reversed(lines):
            tail = _tail(line)
            if tail.startswith("#") or _is_noise(tail):
                continue
            m = _NUM_TITLE.search(tail)
            if m:
                return f"{m.group(1)}. {m.group(2).strip()}", "L2_TYPOGRAPHY", 0.88

        # The index knows a title the document did not preserve near the marker.
        if fallback:
            return fallback, "L2_TYPOGRAPHY", 0.80
        return "", "L2_TYPOGRAPHY", 0.60

    # ── fallback when a book has no OVERVIEW marker ─────────────────────────

    def _from_headings(self, text: str, index: list[dict] | None) -> list[ChapterSpan]:
        """Level 1/2 detection for books that do not use OVERVIEW."""
        titles = _index_titles(index)
        marks: list[tuple[int, str, DetectionLevel, float]] = []
        for m in re.finditer(r"^(#{1,2})\s*(.+?)\s*$", text, re.M):
            level = len(m.group(1))
            body = m.group(2).strip()
            nm = _H1_NUM_TITLE.match(f"# {body}") if level == 1 else None
            if nm:
                marks.append(
                    (m.start(), f"{nm.group(1)}. {nm.group(2).strip()}", "L1_EXPLICIT", 0.95)
                )
            elif level == 1 and body:
                marks.append((m.start(), body, "L2_TYPOGRAPHY", 0.70))
        if not marks:
            return []
        # Number them by document order; the parser index supplies a title only
        # when the heading itself carries none.
        spans: list[ChapterSpan] = []
        for i, (pos, title, level, conf) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            spans.append(
                ChapterSpan(
                    chapter_id=f"ch{i + 1}",
                    title=title or titles.get(i + 1, f"Chapter {i + 1}"),
                    start_offset=pos,
                    end_offset=end,
                    confidence=conf,
                    detection_level=level,
                )
            )
        return spans

    def _from_index_openings(self, text: str, index: list[dict] | None) -> list[ChapterSpan]:
        """Locate chapters by their parser-index title, using a body marker.

        For books whose markdown has no numbered level-1 heading. The parser
        index still knows the titles and the page each chapter starts on, and the
        body still opens every chapter with the same marker ("Chapter
        Objectives" in the OpenStax economics texts). So the title is matched in
        the text and the span then runs to the next opening.

        Titles must be matched in document order and each used once: chapter
        titles occur in the table of contents, in running page headers and in
        cross-references, so first-match is useless. Requiring the match to
        appear after the previous chapter, and only accepting the one closest to
        the following opening marker, is what makes the walk monotonic.
        """
        openings = [m.start() for m in _CHAPTER_OPENING.finditer(text)]
        if len(openings) < 2:
            return []
        titles = _index_titles(index)
        if not titles:
            return []
        spans: list[ChapterSpan] = []
        used_titles: set[str] = set()
        for i, pos in enumerate(openings):
            end = openings[i + 1] if i + 1 < len(openings) else len(text)
            start, label = self._chapter_above_opening(text, pos, openings[0], titles, used_titles)
            if label is None:
                # Keep the span: it is real content, and dropping it would turn a
                # detected chapter into a hole in the book. An unnamed chapter is
                # better reported than a missing one.
                labels = [t for n, t in titles.items() if t not in used_titles]
                label = labels[0] if labels else f"Chapter {i + 1}"
            used_titles.add(label)
            spans.append(
                ChapterSpan(
                    chapter_id=f"ch{i + 1}",
                    title=label,
                    start_offset=start,
                    end_offset=end,
                    confidence=0.85,
                    detection_level="L2_TYPOGRAPHY",
                    subsections=self._subsections(text[pos:end]),
                )
            )
        return spans

    def _chapter_above_opening(
        self,
        text: str,
        pos: int,
        first_opening: int,
        titles: dict[int, str],
        used: set[str],
    ) -> tuple[int, str | None]:
        """Find the start and label of the chapter whose body opens at ``pos``.

        The chapter's own heading is somewhere above the opening marker but the
        gap is not fixed: an OpenStax chapter puts a figure caption between the
        heading and "Chapter Objectives". So the search goes back line by line
        over a generous window, matching each indexed title in document order,
        and stops at the first (nearest) one found. Matching in order matters
        because chapter titles recur in the table of contents and in running
        page headers, and only the nearest occurrence above the marker is the
        chapter's own heading.
        """
        limit = max(0, first_opening)
        probe = text[limit:pos]
        lines = [ln for ln in probe.split("\n")]
        # Walk backwards over non-blank lines, which is what keeps the search
        # on headings rather than the blank runs markdown inserts.
        start = first_opening
        for ln in reversed(lines):
            if not ln.strip():
                continue
            start = probe.rfind("\n" + ln) if ("\n" + ln) in probe else probe.rfind(ln)
            label = self._match_indexed_title(ln, titles, used)
            if label is not None:
                return start, label
        return self._title_line_start(text, pos), None

    @staticmethod
    def _title_line_start(text: str, anchor: int) -> int:
        """Start of the non-blank line holding the heading above ``anchor``."""
        window_start = text.rfind("\n", 0, max(0, anchor - 1))
        for _ in range(TITLE_LOOKBACK_LINES):
            if window_start <= 0:
                return 0
            window_start = text.rfind("\n", 0, window_start - 1)
            if window_start <= 0:
                return 0
        # A chapter's title is a single line; take the line that begins it.
        line_start = text.rfind("\n", 0, max(0, window_start)) + 1
        # Skip blank lines between the title and the opening marker.
        m = re.search(r"^\S", text[line_start:anchor], re.M)
        return line_start + (m.start() if m else 0)

    @staticmethod
    def _match_indexed_title(line: str, titles: dict[int, str], used: set[str]) -> str | None:
        """The index title ``line`` names, in the ``N. Title`` form.

        Returns the label in the form the rest of the pipeline expects so a
        consumer cannot tell which detection path produced it. Unused only: each
        indexed title is consumed once, in document order.
        """
        for num in sorted(titles):
            label = titles[num]
            if label in used:
                continue
            title = label.split(".", 1)[1].strip() if "." in label else label
            probe = title[: min(len(title), 28)]
            if probe and probe in line:
                return label
        return None

    # ── §5.6 boundary resolution ────────────────────────────────────────────

    @staticmethod
    def _resolve_boundaries(structure: BookStructure, text: str = "") -> None:
        """Order by offset and keep the most confident claim per chapter.

        §5.6 forbids a low-confidence node overwriting a high-confidence one.
        With one proposal per anchor this is mostly a guard, but it also strips
        any span that a later, weaker rule tried to re-cut.
        """
        best: dict[str, ChapterSpan] = {}
        for span in structure.chapters:
            prior = best.get(span.chapter_id)
            if prior is None or span.confidence > prior.confidence:
                best[span.chapter_id] = span
        spans = sorted(best.values(), key=lambda c: c.start_offset)
        for i, span in enumerate(spans):
            if i + 1 < len(spans):
                end = spans[i + 1].start_offset
            else:
                # The final chapter ends where back matter begins, not at EOF.
                # Leaving it at EOF would swallow the answers and appendices
                # into it, and leave nothing for _split_back_matter to find.
                end = structure.total_chars
                if text:
                    m = _BACK_MATTER.search(text, span.start_offset + 1)
                    if m:
                        end = max(span.start_offset, m.start())
            span.end_offset = max(span.start_offset, end)
        structure.chapters = spans

    @staticmethod
    def _renumber(structure: BookStructure) -> None:
        """Ids follow document order, and appendices sort last.

        Two worktree runs can disagree about whether a detected span is an
        appendix; keying by position rather than by the original number keeps
        the ids stable.
        """
        for i, span in enumerate(structure.chapters, start=1):
            span.chapter_id = f"ch{i}"
            if not span.title:
                span.title = f"Chapter {i}"

    @staticmethod
    def _subsections(body: str) -> list[str]:
        out: list[str] = []
        for m in re.finditer(r"^#{2,6}\s+(.{2,70})$", body, re.M):
            label = m.group(1).strip()
            if not _is_noise(label):
                out.append(label)
        return out[:60]


# ── helpers ──────────────────────────────────────────────────────────────────


def _parse_index(raw: str | None) -> list[dict]:
    if not raw:
        return []
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [h for h in data if isinstance(h, dict)] if isinstance(data, list) else []


def _index_titles(index: list[dict] | None) -> dict[int, str]:
    """Map chapter number to index title, level-1 only."""
    out: dict[int, str] = {}
    for h in index or []:
        if h.get("level") != 1:
            continue
        title = str(h.get("title") or "")
        m = _INDEX_CH_NUM.match(title)
        if m:
            out[int(m.group(1))] = f"{m.group(1)}. {m.group(2).strip()}"
    return out


def _tail(line: str) -> str:
    """The last HEADING_TAIL_CHARS of a line, which is where a heading sits."""
    line = (line or "").rstrip()
    return line[-HEADING_TAIL_CHARS:] if len(line) > HEADING_TAIL_CHARS else line


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum() or c.isspace()).strip()


def _is_noise(line: str) -> bool:
    """Reject picture-text blocks, tags and bare numbers."""
    s = (line or "").strip()
    if not s:
        return True
    if s.startswith("<") or "picture text" in s.lower():
        return True
    if re.fullmatch(r"[\d#\s•,.:;·-]*", s):
        return True
    # A single word glued by <br> tags is OCR debris, e.g. "L<br>U<br>C".
    if s.count("<br>") >= 2:
        return True
    return False


def chapter_spans_from_structure(structure: BookStructure, text: str) -> list:
    """Turn structure into the Chapter objects the producer consumes.

    Lives here so the producer does not need to know how structure was found,
    and so a structure can be persisted once and reused across runs.
    """
    from stratum.services.bu_v2_producer import Chapter

    out: list[Chapter] = []
    for span in structure.chapters:
        body = text[span.start_offset : span.end_offset]
        out.append(
            Chapter(
                chapter_id=span.chapter_id,
                number=_num(span.chapter_id),
                title=span.title,
                text=body,
                start=span.start_offset,
                end=span.end_offset,
                subsections=span.subsections,
                # §5.4: the span's kind travels with the Chapter so downstream
                # stages can tell a chapter from worked answers/an appendix. It
                # was dropped here, which is how "bm1" reached the discourse arc.
                kind=span.kind,
            )
        )
    return out


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0
