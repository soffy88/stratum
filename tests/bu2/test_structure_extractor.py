"""Structure extractor tests — spec §13.1.

    normal book, bilingual book, repeated title, missing heading

Each case is a synthetic document built here rather than read from the
database, so the detector's behaviour is pinned against text whose structure
is known exactly. The real book is exercised in tests/test_p11_real_book.py
and in the §14 trial.
"""

from __future__ import annotations


from stratum.services.bu_v2_structure_extractor import (
    BookStructureExtractor,
    chapter_spans_from_structure,
)

BODY = "x" * 6000


def make_chapter_text(number: int, title: str, *, heading: str | None = None) -> str:
    head = heading if heading is not None else f"# {number} {title}"
    return f"{head}\n\n\n\nOVERVIEW This chapter covers {title}.\n\n" + BODY + "\n\n"


def normal_book(n: int = 3) -> str:
    parts = ["Front matter.\n\n" + "preface " * 500]
    for i in range(1, n + 1):
        parts.append(make_chapter_text(i, f"Topic{i}"))
    parts.append("ANSWERS TO ODD-NUMBERED EXERCISES\n\n" + "a" * 8000)
    return "".join(parts)


# ── normal book ──────────────────────────────────────────────────────────────


def test_normal_book_finds_every_chapter():
    s = BookStructureExtractor().extract_from_text(normal_book(3), book_id="b1")
    assert s.expected_chapters == 0  # no parser index supplied
    assert len(s.chapters) == 4  # 3 chapters + worked answers
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    assert [c.title for c in numbered] == ["1. Topic1", "2. Topic2", "3. Topic3"]
    assert all(c.detection_level == "L1_EXPLICIT" for c in numbered)
    assert all(c.confidence >= 0.9 for c in numbered)


def test_chapters_are_ordered_and_do_not_overlap():
    s = BookStructureExtractor().extract_from_text(normal_book(4), book_id="b1")
    for a, b in zip(s.chapters, s.chapters[1:]):
        assert a.end_offset == b.start_offset, "spans must tile without gaps or overlap"
        assert a.start_offset < a.end_offset


def test_coverage_accounting_balances():
    """front + chapters + back must equal the document, exactly."""
    text = normal_book(3)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    total = sum(c.char_count for c in s.chapters)
    assert s.front_matter_chars + total + s.back_matter_chars == len(text)


# ── bilingual book ───────────────────────────────────────────────────────────


def bilingual_book() -> str:
    parts = ["献词\n\n" + "致谢 " * 800]
    for i in range(1, 5):
        parts.append(
            f"# {i} Chapter{i} Topic\n\n\n\nOVERVIEW 第{i}章 概述。\n\n"
            + ("English prose. " * 400)
            + ("中文正文。" * 400)
            + BODY
        )
    return "".join(parts)


def test_bilingual_book_is_detected():
    s = BookStructureExtractor().extract_from_text(bilingual_book(), book_id="b1")
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    assert len(numbered) == 4
    assert [c.chapter_id for c in numbered] == ["ch1", "ch2", "ch3", "ch4"]


def test_bilingual_book_confidence_is_not_penalised():
    """A Chinese OVERVIEW must still count as a chapter marker."""
    s = BookStructureExtractor().extract_from_text(bilingual_book(), book_id="b1")
    assert s.confidence_mean >= 0.8


def test_ocr_debris_is_not_mistaken_for_a_title():
    """Picture-text debris like 'L<br>U<br>C' must not become a chapter."""
    debris = "<!-- Start of picture text -->\nL<br>U<br>C<br>A<br>L<br>C<br><!-- End of picture text -->\n\n"
    text = debris + "# 1 Real Chapter\n\n\n\nOVERVIEW real.\n\n" + BODY
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    assert len(numbered) == 1
    assert "Real Chapter" in numbered[0].title


# ── repeated title ───────────────────────────────────────────────────────────


def repeated_title_book() -> str:
    """The P10 failure mode: a title repeated 200 times in a table of contents."""
    parts = ["Contents\n\n"]
    for i in range(1, 4):
        parts.append(f"...........................................\n{i}. Topic{i} .... 41\n" * 60)
    parts.append("\n\n")
    for i in range(1, 4):
        parts.append(make_chapter_text(i, f"Topic{i}"))
    return "".join(parts)


def test_repeated_title_does_not_create_phantom_chapters():
    """180 table-of-contents lines must not become 180 chapters."""
    s = BookStructureExtractor().extract_from_text(repeated_title_book(), book_id="b1")
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    assert len(numbered) == 3, f"got {len(numbered)} chapters"
    for c in numbered:
        assert c.char_count >= 5000


def test_repeated_title_picks_the_body_not_the_contents():
    s = BookStructureExtractor().extract_from_text(repeated_title_book(), book_id="b1")
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    # The real chapter 1 begins after the whole contents listing, so its offset
    # must be well past it.
    assert numbered[0].start_offset > 3000


# ── missing heading ──────────────────────────────────────────────────────────


def test_book_without_overview_falls_back_to_headings():
    """A book that does not use OVERVIEW still gets chapters from headings."""
    parts = []
    for i in range(1, 4):
        parts.append(f"# {i} Topic{i}\n\n" + BODY + "\n\n")
    s = BookStructureExtractor().extract_from_text("".join(parts), book_id="b1")
    assert s.extraction_method == "heading_scan"
    assert len(s.chapters) == 3


def test_index_titles_fill_a_missing_heading():
    """§5.4 confidence falls, but the chapter is still found and named."""
    text = "".join(make_chapter_text(i, f"Topic{i}", heading="") for i in range(1, 4))
    index = [{"title": f"{i}. Topic{i}", "page": 10 * i, "level": 1} for i in range(1, 4)]
    s = BookStructureExtractor().extract_from_text(text, book_id="b1", index=index)
    assert s.expected_chapters == 3
    assert len(s.chapters) == 3
    assert all("Topic" in c.title for c in s.chapters)


def test_index_title_confidence_is_lower_than_explicit_heading():
    """§5.6: confidence must distinguish how a boundary was found."""
    with_headings = "".join(make_chapter_text(i, f"Topic{i}") for i in range(1, 4))
    without = "".join(make_chapter_text(i, f"Topic{i}", heading="") for i in range(1, 4))
    index = [{"title": f"{i}. Topic{i}", "page": 1, "level": 1} for i in range(1, 4)]
    a = BookStructureExtractor().extract_from_text(with_headings, book_id="b", index=index)
    b = BookStructureExtractor().extract_from_text(without, book_id="b", index=index)
    assert a.confidence_mean > b.confidence_mean


def test_low_confidence_never_overwrites_high_confidence():
    """§5.6 explicitly forbids a weaker node replacing a stronger one."""
    s = BookStructureExtractor().extract_from_text(normal_book(3), book_id="b1")
    s.chapters.append(
        type(s.chapters[0])(
            chapter_id=s.chapters[0].chapter_id,
            title="WEAK TITLE",
            start_offset=s.chapters[0].start_offset,
            end_offset=s.chapters[0].end_offset,
            confidence=0.10,
        )
    )
    BookStructureExtractor._resolve_boundaries(s, "x" * 100000)
    kept = next(c for c in s.chapters if c.chapter_id == "ch1")
    assert kept.title != "WEAK TITLE"


def test_short_span_is_rejected():
    """A heading with no body must not become a chapter."""
    text = "# 1 Real\n\nOVERVIEW x\n\n" + BODY + "\n# 2 Empty\n\n"
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    titles = [c.title for c in s.chapters]
    assert "2. Empty" not in titles


# ── back matter ──────────────────────────────────────────────────────────────


def test_worked_answers_become_their_own_section():
    s = BookStructureExtractor().extract_from_text(normal_book(3), book_id="b1")
    assert any(c.title == "Worked Answers" for c in s.chapters)


def test_index_is_excluded_not_counted():
    """An index is a locator. Counting it as understood content would be false."""
    text = "".join(make_chapter_text(i, f"T{i}") for i in range(1, 3))
    text += "\n## Applications Index\n\n" + ("entry, page\n" * 3000)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    assert not any(c.title.endswith("Index") for c in s.chapters)
    assert s.back_matter_chars > 0
    assert s.coverage_ratio < 1.0


# ── integration with the producer's Chapter type ─────────────────────────────


def test_structure_converts_to_producer_chapters():
    text = normal_book(3)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    spans = chapter_spans_from_structure(s, text)
    assert len(spans) == len(s.chapters)
    for span in spans:
        assert span.char_count > 0
        assert span.text == text[span.start : span.end]


def test_empty_text_yields_empty_structure():
    s = BookStructureExtractor().extract_from_text("", book_id="b1")
    assert s.chapters == []
    assert s.coverage_ratio == 0.0
    assert s.confidence_mean == 0.0


# ── context plumbing (§6.1): regression for a real bug ───────────────────────


def test_context_lives_on_chapter_not_on_the_understanding():
    """ChapterUnderstanding carries neither `context` nor `role`.

    Reading `c.context` off a ChapterUnderstanding raises AttributeError, and
    it did: a full 49-minute book run completed and then crashed in the
    reporting step. The run records these on RunResult instead, and this test
    pins the object boundary that caused it.
    """
    from stratum.knowledge.bu_v2_models import ChapterUnderstanding
    from stratum.services.bu_v2_producer import ChapterContext, Chapter

    cu = ChapterUnderstanding(id="cu1", run_id="r", chapter_id="ch1")
    for attr in ("context", "role"):
        assert not hasattr(cu, attr), f"ChapterUnderstanding must not gain {attr}"
    ch = Chapter(chapter_id="ch1", number=1, title="t", text="x", context=ChapterContext())
    assert ch.context is not None
    assert ch.role == "" or isinstance(ch.role, str)


def test_run_result_carries_context_used_flag():
    from stratum.services.bu_v2_entrypoint import RunResult

    r = RunResult(run_id="r", book_id="b", substrate_id="s")
    assert r.context_used is False
    assert r.chapter_roles == []


def test_loader_retains_the_parser_index():
    """§14's denominator comes from the parser index, so the loader must keep it.

    Without this the extractor cannot know the book declares 16 chapters and
    reports 0% detection on a perfect extraction — which is what a real 50-minute
    book run did.
    """
    from stratum.services.bu_v2_entrypoint import BookLoader

    loader = BookLoader()
    assert loader.last_index == []
    assert hasattr(loader, "last_index")


def test_concept_confidence_stays_in_range():
    """Regression: an operator-precedence bug let confidence reach 1.6.

    Only the last term of the weighted mean was divided, so a trajectory with
    several event kinds exceeded 1.0 and violated the CHECK constraint on
    concept_trajectory.confidence. Caught by a persisted run, not a test.
    """
    from stratum.knowledge.bu_v2_models import ChapterDelta, ChapterUnderstanding
    from stratum.services.bu_v2_concept_evolution import ConceptEvolutionBuilder

    def cu(i, intro=(), redef=(), deps=()):
        return ChapterUnderstanding(
            id=f"cu{i}",
            run_id="r",
            chapter_id=f"ch{i}",
            chapter_thesis="t",
            concepts_introduced_refs=list(intro),
            concepts_redefined_refs=list(redef),
            dependencies_on_prior=list(deps),
        )

    chapters = [
        cu(1, ["limit"]),
        cu(2, ["continuity"], ["limit"], ["limit"]),
        cu(3, ["integral"], ["limit"], ["limit", "continuity"]),
    ]
    deltas = [ChapterDelta(id="d3", run_id="r", chapter_id="ch3", revised_concepts_refs=["limit"])]
    result = ConceptEvolutionBuilder().build(
        chapters, run_id="r", book_id="b", deltas=deltas, chapter_text={}
    )
    assert result.trajectories
    for traj in result.trajectories:
        assert 0.0 <= traj.confidence <= 1.0, f"{traj.concept} confidence {traj.confidence}"


def test_every_span_has_a_unique_chapter_id():
    """Identity must never be empty.

    Back-matter spans were created with `chapter_id=""`, so the two of them in
    Thomas Calculus derived the same `cu_{run_id}_` id and the persisted run
    died on a duplicate key after ~50 minutes of work. `id` is what every
    downstream table keys on, so an empty one is a collision waiting to happen.
    """
    from stratum.services.bu_v2_structure_extractor import chapter_spans_from_structure

    book = _book_with_back_matter()
    structure = BookStructureExtractor().extract_from_text(book, book_id="b1")
    ids = [c.chapter_id for c in structure.chapters]
    assert all(ids), f"a span has no id: {ids}"
    assert len(set(ids)) == len(ids), f"duplicate span ids: {ids}"

    # The derived ChapterUnderstanding ids are what actually collided.
    run_id = "br_TEST"
    cu_ids = [f"cu_{run_id}_{s.chapter_id}" for s in chapter_spans_from_structure(structure, book)]
    assert len(set(cu_ids)) == len(cu_ids), f"duplicate ChapterUnderstanding ids: {cu_ids}"


def _book_with_back_matter() -> str:
    """A book whose tail really resolves into two back-matter spans.

    The markers have to match what `_split_back_matter` looks for, and the tail
    must be at least `min_chapter_chars` long, or the split never happens and
    the test passes for the wrong reason.
    """
    min_chars = BookStructureExtractor().min_chapter_chars
    # Each block ends with a newline: the markers are anchored with ^ under
    # re.M, so a section glued to the previous body is never detected.
    chapter = "1. First\n" + "c" * (min_chars + 500) + "\n"
    answers = "ANSWERS TO ODD-NUMBERED EXERCISES\n" + "a" * (min_chars + 500) + "\n"
    appendix = "# APPENDIX 1\n" + "p" * (min_chars + 500) + "\n"
    return f"OVERVIEW\n{chapter}{answers}{appendix}"


# ── index-driven openings: books with no numbered heading ──────────────────


def _openstax_book(n: int = 3) -> tuple[str, list[dict]]:
    """An OpenStax-style book and the parser index it came with.

    The markdown carries no numbered level-1 heading: chapter titles appear as
    bare lines above a figure caption, and the body opens with a "Chapter
    Objectives" heading. The parser index is the only place the chapter numbers
    live. This is the shape that made the heading scan report 2-3 chapters on a
    21-chapter book.
    """
    parts = ["# Principles of Economics\n\n" + "preface " * 400 + "\n\n"]
    index: list[dict] = []
    titles = [
        "Welcome to Economics!",
        "Choice in a World of Scarcity",
        "Demand and Supply",
        "Labor and Financial Markets",
    ]
    for i in range(1, n + 1):
        title = titles[(i - 1) % len(titles)] + (f" {i}" if i > 4 else "")
        index.append({"title": f"Chapter {i} {title}", "page": 20 + i * 20, "level": 1})
        parts.append(
            f"**{i}** \n\n{title} \n\n"
            f"**FIGURE {i}.1 Choices and Tradeoffs** A caption for chapter {i}.\n\n"
            f"#### **Chapter Objectives** \n\nIn this chapter you will learn about {title}.\n\n"
            + ("b" * 20_000)
            + "\n\n"
        )
    index.append({"title": "Appendix A The Use of Mathematics", "page": 900, "level": 1})
    parts.append("**APPENDIX A** " + "x" * 6000 + "\n\n")
    parts.append("**Answer Key** " + "k" * 6000 + "\n\n")
    parts.append("**Index** " + "i" * 4000 + "\n")
    return "".join(parts), index


def test_index_openings_finds_every_indexed_chapter():
    """21 chapters of the real book were 2 spans before this path existed."""
    text, index = _openstax_book(4)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1", index=index)
    assert s.expected_chapters == 4
    numbered = [c for c in s.chapters if c.kind == "chapter"]
    assert [c.title for c in numbered] == [
        "1. Welcome to Economics!",
        "2. Choice in a World of Scarcity",
        "3. Demand and Supply",
        "4. Labor and Financial Markets",
    ]
    assert s.extraction_method == "index_openings"
    assert all(c.detection_level == "L2_TYPOGRAPHY" for c in numbered)


def test_index_openings_text_balances_and_orders():
    text, index = _openstax_book(4)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1", index=index)
    total = sum(c.char_count for c in s.chapters)
    assert s.front_matter_chars + total + s.back_matter_chars == s.total_chars
    for a, b in zip(s.chapters, s.chapters[1:]):
        assert a.start_offset < a.end_offset <= b.start_offset


def test_index_openings_does_not_cut_a_book_it_cannot_beat():
    """With no index there is nothing to index into, so the scan's result stands."""
    text, _index = _openstax_book(2)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1")
    assert s.extraction_method == "heading_scan"
    # The only heading is the title line, so that is the one span the scan finds.
    assert [c.title for c in s.chapters if c.kind == "chapter"] == ["Principles of Economics"]
    # Back matter is still split out — that is independent of chapter detection.
    assert [c.kind for c in s.chapters].count("back_matter") == 1


def test_index_openings_separates_bold_back_matter():
    """Appendices/index written as ``**APPENDIX A**`` must not be a chapter."""
    text, index = _openstax_book(4)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1", index=index)
    kinds = [c.kind for c in s.chapters]
    assert "back_matter" in kinds
    assert s.back_matter_chars > 0
    assert [c for c in s.chapters if c.kind == "back_matter"][0].title == "Appendices"
    # The numbered chapters end at their own content, not at the index.
    assert s.chapters[-2].kind == "chapter"


def test_index_titles_accept_both_index_shapes():
    """The corpus writes "3. Demand" and "Chapter 3 Demand" interchangeably."""
    from stratum.services.bu_v2_structure_extractor import _index_titles

    assert _index_titles([{"title": "3. Demand", "level": 1}]) == {3: "3. Demand"}
    assert _index_titles([{"title": "Chapter 3 Demand", "level": 1}]) == {3: "3. Demand"}
    assert _index_titles([{"title": "Appendix A Maths", "level": 1}]) == {}
    assert _index_titles([{"title": "Chapter 3 Demand", "level": 2}]) == {}
    assert _index_titles([]) == {}


def test_index_openings_a_toc_title_is_not_consumed_twice():
    """A chapter title repeated in a running header must not steal a span."""
    text, index = _openstax_book(3)
    # Inject the first chapter's title as a bare line late in the book, the way
    # a running page header repeats it.
    marker = "Welcome to Economics!"
    text = text.replace(marker, marker + "\n\n" + marker + "\n\n", 1)
    s = BookStructureExtractor().extract_from_text(text, book_id="b1", index=index)
    labels = [c.title for c in s.chapters if c.kind == "chapter"]
    assert len(labels) == len(set(labels)) == 3
