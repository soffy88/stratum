"""deck.json construction from grounded material, with a mocked model."""

from __future__ import annotations

import json
import re

import pytest

from stratum.services.ppt_export.deck_builder import (
    CONTENT_TYPES,
    DeckBuildError,
    DeckOptions,
    build_deck,
    chapter_prompt,
    normalize_slide,
    plan_slots,
    slide_text,
)
from stratum.services.ppt_export.fit import clen, plain_formula, trim
from stratum.services.ppt_export.material import (
    ChapterMaterial,
    detect_language,
    is_language,
    load_material,
    toc_sections,
)

from .fixtures import FakeProvider, tiny_book


# ── planning ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pages", [5, 8, 12, 20, 30])
def test_book_plan_meets_page_count_exactly(pages):
    slots = plan_slots(tiny_book(), DeckOptions(pages=pages))
    total = sum(s.count if s.kind == "content" else 1 for s in slots)
    assert total == pages
    assert slots[0].kind == "cover" and slots[-1].kind == "closing"


def test_chapter_plan_uses_only_that_chapter():
    slots = plan_slots(tiny_book(), DeckOptions(pages=10, chapter_id="ch2"))
    assert {s.chapter_id for s in slots} == {"ch2"}
    assert sum(s.count for s in slots if s.kind == "content") == 8
    assert all(s.count <= 4 for s in slots)


def test_chapter_without_understanding_is_refused():
    book = tiny_book()
    book.chapters.append(ChapterMaterial(chapter_id="ch3", excerpt="只有原文，没有理解"))
    with pytest.raises(DeckBuildError):
        plan_slots(book, DeckOptions(chapter_id="ch3"))
    assert "ch3" not in {c.chapter_id for c in book.usable_chapters()}


def test_page_count_is_clamped():
    assert DeckOptions(pages=2).clamp().pages == 5
    assert DeckOptions(pages=99).clamp().pages == 30


# ── normalisation ────────────────────────────────────────────────────────────


def test_normalize_trims_to_layout_capacity_and_strips_latex():
    raw = {
        "type": "explain",
        "title": "这是一个非常非常长的结论式标题它显然超过了二十个字的上限",
        "blocks": [
            {"label": "定义"},
            {"formula": r"$\lim_{\Delta x \to 0} \frac{\Delta y}{\Delta x}$"},
            {"text": "说明" * 40},
        ],
        "notes": "口播" * 300,
    }
    s = normalize_slide(raw)
    assert s is not None
    assert clen(s["title"]) <= 20
    formula = s["blocks"][1]["formula"]
    assert "\\" not in formula and "$" not in formula and "Δ" in formula and "→" in formula
    assert clen(s["blocks"][2]["text"]) <= 40
    assert len(s["notes"]) <= 320


@pytest.mark.parametrize(
    "raw",
    [
        {"type": "chart", "title": "不支持的页型"},
        {"type": "grid", "title": "条目太少", "items": [{"text": "只有一条"}]},
        {
            "type": "definitions",
            "items": [{"title": "a", "text": "b"}, {"title": "c", "text": "d"}],
        },
        {"type": "compare", "title": "缺一边", "left": {"title": "甲", "items": ["x", "y"]}},
        "not a slide",
    ],
)
def test_normalize_rejects_invalid_slides(raw):
    assert normalize_slide(raw) is None


def test_trim_prefers_punctuation_boundary():
    assert trim("导数是变化率，它由极限定义并且可以计算", 10) == "导数是变化率"
    assert clen(trim("a" * 3 + "很长的中文内容" * 10, 12)) <= 12


def test_plain_formula_handles_nested_fracs():
    assert plain_formula(r"\frac{1}{x^{2}}") == "(1)/(x^(2))"


def test_language_detection_tolerates_formulas():
    assert detect_language("设函数 f(x) 在点 x0 的某邻域内有定义，若 lim f(x) 存在") == "zh"
    assert detect_language("The derivative of sin x is cos x for every real x") == "en"
    assert is_language("求导三步：dy/dx = lim Δy/Δx", "zh")
    assert not is_language("The derivative measures instantaneous change", "zh")


# ── prompts are grounded and language-locked ─────────────────────────────────


def test_chapter_prompt_carries_material_and_language_rule():
    book = tiny_book()
    slot = plan_slots(book, DeckOptions(pages=8))[2]
    ch = book.chapter(slot.chapter_id)
    prompt = chapter_prompt(book, ch, slot, audience="大一学生", used_titles=["已用标题"])
    assert ch.thesis in prompt
    assert ch.subsections[0] in prompt
    assert "输出语言：简体中文" in prompt
    assert "翻译成中文" in prompt
    assert "已用标题" in prompt
    assert "资料里没有的事实" in prompt


# ── building ─────────────────────────────────────────────────────────────────


def _content(deck):
    return [s for s in deck["slides"] if s["type"] in CONTENT_TYPES]


def test_build_deck_happy_path():
    provider = FakeProvider()
    deck, report = build_deck(tiny_book(), DeckOptions(pages=10), provider)
    slides = deck["slides"]
    assert len(slides) == 10
    assert [s["n"] for s in slides] == list(range(1, 11))
    assert slides[0]["type"] == "cover" and slides[-1]["type"] == "closing"
    assert slides[0]["title"] == "导数让变化可以精确度量"
    for s in slides:
        if s["type"] not in ("toc", "section"):
            assert s.get("notes"), s
        assert is_language(slide_text(s), "zh"), s
    titles = [s["title"] for s in _content(deck)]
    assert all(4 <= clen(t) <= 20 for t in titles)
    assert deck["meta"]["density"] == "low" and deck["meta"]["notes"] is True
    assert deck["meta"]["aii_source"]["run_id"] == "br_tiny"
    assert report.fallback_slides == 0
    json.dumps(deck, ensure_ascii=False)  # serialisable


def test_english_answer_is_retried_in_chinese():
    provider = FakeProvider(english_first=True)
    deck, report = build_deck(tiny_book(), DeckOptions(pages=8), provider)
    assert report.language_retries >= 1
    retry_prompts = [c["prompt"] for c in provider.calls if "没有用简体中文" in c["prompt"]]
    assert retry_prompts, "the retry must name the language failure"
    for s in deck["slides"]:
        assert is_language(slide_text(s), "zh"), s


def test_model_that_never_answers_in_chinese_falls_back_to_material():
    provider = FakeProvider(always_english=True)
    deck, report = build_deck(tiny_book(), DeckOptions(pages=7), provider)
    assert report.fallback_slides > 0
    text = json.dumps(deck["slides"], ensure_ascii=False)
    assert "instantaneous" not in text
    for s in deck["slides"]:
        assert is_language(slide_text(s), "zh"), s
    # fallback content comes from the stored understanding, not from nowhere
    assert "导数" in text and "常数的导数等于零" in text


def test_no_notes_option_strips_notes():
    deck, _ = build_deck(tiny_book(), DeckOptions(pages=6, notes=False), FakeProvider())
    assert all("notes" not in s for s in deck["slides"])


# ── material loading ─────────────────────────────────────────────────────────


class _Rows:
    def __init__(self, tables):
        self.tables = tables
        self.sql = []

    def query(self, sql, params):
        self.sql.append((sql, params))
        for key, rows in self.tables.items():
            if key in sql:
                return rows
        return []


class _TextChapter:
    def __init__(self, cid, title, text):
        self.chapter_id, self.title, self.text, self.number, self.subsections = (
            cid,
            title,
            text,
            int(cid[2:]),
            [],
        )


def test_load_material_prefers_verified_and_reads_sections():
    db = _Rows(
        {
            "FROM stratum.substrates": [{"id": "s1", "title": "高等数学", "language": None}],
            "FROM stratum.book_understandings_v2": [
                {
                    "run_id": "br_v",
                    "status": "VERIFIED",
                    "version": 2,
                    "genre": "数学",
                    "central_theses_json": json.dumps(["导数刻画变化"]),
                    "governing_questions_json": [],
                }
            ],
            "FROM stratum.chapter_understandings": [
                {
                    "chapter_id": "ch1",
                    "chapter_question": "什么是极限？",
                    "chapter_goal": "",
                    "chapter_thesis": "极限是微积分的基础。",
                    "primary_role": "FOUNDATION",
                    "concepts_introduced_refs": ["极限", "极限"],
                    "evidence_program_json": json.dumps(
                        [
                            {"claim_ref": "数列极限唯一。", "is_supported": True},
                            {"claim_ref": "未证实的说法", "is_supported": False},
                        ]
                    ),
                    "qualifications_json": [],
                }
            ],
            "FROM stratum.book_syntheses": [
                {"concept_system": {"core": [{"label": "极限", "definition": "无限接近"}]}}
            ],
        }
    )
    body = "第一章 极限\n第一节 数列的极限\n数列极限的定义是这样的，对于任意给定的正数……" * 3
    m = load_material(
        "s1",
        db=db,
        text_loader=lambda sid: (body, [_TextChapter("ch1", "1. 极限", body)]),
    )
    assert m.run_id == "br_v" and m.language == "zh"
    assert "ORDER BY (status='VERIFIED') DESC" in db.sql[1][0]
    ch = m.chapters[0]
    assert ch.concepts == ["极限"]
    assert ch.claims == ["数列极限唯一。"]
    assert ch.subsections == ["第一节 数列的极限"]
    assert "数列极限的定义" in ch.section_snippets["第一节 数列的极限"]
    assert m.concept_defs["极限"] == "无限接近"


def test_load_material_without_understanding_is_explicit():
    from stratum.services.ppt_export.material import MaterialUnavailable

    db = _Rows({"FROM stratum.substrates": [{"id": "s1", "title": "x", "language": "zh"}]})
    with pytest.raises(MaterialUnavailable):
        load_material("s1", db=db, text_loader=lambda sid: ("", []))


def test_toc_sections_group_by_chapter():
    md = (
        "目录\n第一节 映射与函数 1\n第二节 数列的极限 18\n第一节 导数概念 71\n第二节 求导法则 82\n"
        + "正文" * 50
    )
    assert toc_sections(md, 2) == [
        ["第一节 映射与函数", "第二节 数列的极限"],
        ["第一节 导数概念", "第二节 求导法则"],
    ]


def test_topic_label_titles_are_rewritten_as_claims():
    from stratum.services.bu_v2_provider import ModelResponse
    from stratum.services.ppt_export.deck_builder import looks_like_topic

    assert looks_like_topic("导数的定义", "zh")
    assert not looks_like_topic("导数是增量之比的极限", "zh")

    class Polisher(FakeProvider):
        def complete(self, prompt, **kw):
            if "像话题名" in prompt:
                self.calls.append({"prompt": prompt, "system": ""})
                return ModelResponse(
                    json.dumps({"titles": [{"n": 3, "title": "导数是增量之比的极限"}]}),
                    "fake",
                    "fake",
                )
            resp = super().complete(prompt, **kw)
            data = json.loads(resp.text)
            labels = ["导数的定义", "极限的概念", "连续的性质", "求导的方法"]
            for i, sl in enumerate(data.get("slides", [])):
                sl["title"] = labels[(len(self.calls) + i) % 4]
            return ModelResponse(json.dumps(data, ensure_ascii=False), "fake", "fake")

    deck, report = build_deck(tiny_book(), DeckOptions(pages=6), Polisher())
    assert report.titles_polished == 1
    assert deck["slides"][2]["title"] == "导数是增量之比的极限"


def test_placeholder_labels_copied_from_the_schema_are_dropped():
    s = normalize_slide(
        {
            "type": "definitions",
            "title": "两个概念支撑本章",
            "side": {"title": "引导(10)", "body": "先懂概念再算题"},
            "items": [{"title": "函数", "text": "依赖关系"}, {"title": "极限", "text": "无限接近"}],
        }
    )
    assert s["side"] == {"body": "先懂概念再算题"}


# ── distinct titles and exact page count ─────────────────────────────────────


def _assert_distinct_titles(deck):
    from stratum.services.ppt_export.deck_builder import is_template_title, titles_similar

    titles = [
        s["title"]
        for s in deck["slides"]
        if s["type"] in CONTENT_TYPES and s.get("title") and "（续" not in s["title"]
    ]
    for t in titles:
        assert not is_template_title(t), t
        assert "是本章的基石" not in t and "书中明确给出这些结论" not in t, t
    for i, a in enumerate(titles):
        for b in titles[i + 1 :]:
            assert not titles_similar(a, b), (a, b)
    return titles


def test_title_similarity_catches_near_duplicates():
    from stratum.services.ppt_export.deck_builder import is_template_title, titles_similar

    assert titles_similar("导数是函数变化率的精确描述", "导数是函数变化速率的瞬时度量")
    assert titles_similar("导数是变化率的极限。", "**导数是变化率的极限**")
    assert not titles_similar("导数是增量之比的极限", "可导与连续别混为一谈")
    assert not titles_similar("函数是映射的一种", "函数是变量之间的依赖关系")
    assert is_template_title("映射、函数、极限是本章的基石")
    assert is_template_title("书中明确给出这些结论")


def test_fallback_titles_are_specific_conclusions_and_distinct():
    from stratum.services.ppt_export.deck_builder import fallback_slides

    book = tiny_book()
    slides = fallback_slides(book.chapters[0], 8, "zh", book.concept_defs)
    assert len(slides) >= 4
    titles = [s["title"] for s in slides]
    assert len({t for t in titles}) == len(titles)
    assert all("是本章的基石" not in t and "书中明确" not in t for t in titles)
    # titles are taken from the chapter's own understanding
    assert any(t in book.chapters[0].thesis or t in book.chapters[0].claims[0] for t in titles)
    # an avoid list is honoured
    again = fallback_slides(book.chapters[0], 8, "zh", book.concept_defs, avoid=titles)
    assert not set(s["title"] for s in again) & set(titles)


def test_model_that_never_answers_yields_distinct_untemplated_titles():
    deck, report = build_deck(tiny_book(), DeckOptions(pages=9), FakeProvider(always_english=True))
    assert len(deck["slides"]) == 9
    assert report.fallback_slides > 0
    _assert_distinct_titles(deck)


def test_near_duplicate_model_titles_are_rewritten():
    from stratum.services.bu_v2_provider import ModelResponse

    dupes = ["导数是函数变化率的精确描述", "导数是函数变化速率的瞬时度量"]

    class Dupes(FakeProvider):
        def __init__(self):
            super().__init__()
            self.polish_prompts: list[str] = []

        def complete(self, prompt, **kw):
            if "像话题名" in prompt:
                self.polish_prompts.append(prompt)
                # a useless polish answer: still a near-duplicate
                return ModelResponse(
                    json.dumps({"titles": [{"n": 3, "title": "导数是函数变化率的精确描述"}]}),
                    "fake",
                    "fake",
                )
            resp = super().complete(prompt, **kw)
            data = json.loads(resp.text)
            for i, sl in enumerate(data.get("slides", [])):
                sl["title"] = dupes[i % 2]
            return ModelResponse(json.dumps(data, ensure_ascii=False), "fake", "fake")

    provider = Dupes()
    deck, report = build_deck(tiny_book(), DeckOptions(pages=8), provider)
    assert len(deck["slides"]) == 8
    assert provider.polish_prompts and "太相近" in provider.polish_prompts[0]
    titles = _assert_distinct_titles(deck)
    assert report.titles_deduped > 0
    assert all(4 <= clen(t) <= 20 for t in titles)


def test_polish_fixes_duplicates_when_the_model_answers_well():
    from stratum.services.bu_v2_provider import ModelResponse

    class Fix(FakeProvider):
        def complete(self, prompt, **kw):
            if "像话题名" in prompt:
                ns = [int(n) for n in re.findall(r'"n": (\d+)', prompt)]
                good = [
                    "求导先求增量再取极限",
                    "可导一定连续反之不然",
                    "微分是增量的线性主部",
                    "单侧导数决定可导性",
                    "极限刻画无限接近过程",
                    "连续函数图像没有断点",
                ]
                return ModelResponse(
                    json.dumps(
                        {"titles": [{"n": n, "title": good[i]} for i, n in enumerate(ns)]},
                        ensure_ascii=False,
                    ),
                    "fake",
                    "fake",
                )
            resp = super().complete(prompt, **kw)
            data = json.loads(resp.text)
            for sl in data.get("slides", []):
                sl["title"] = "导数是函数变化率的精确描述"
            return ModelResponse(json.dumps(data, ensure_ascii=False), "fake", "fake")

    deck, report = build_deck(tiny_book(), DeckOptions(pages=7), Fix())
    assert report.titles_polished >= 1
    _assert_distinct_titles(deck)


def test_exact_page_count_when_a_chapter_cannot_be_grounded():
    from stratum.services.bu_v2_provider import ProviderError

    class FailsCh2(FakeProvider):
        def complete(self, prompt, **kw):
            if "导数与微分”这一章" in prompt:
                self.calls.append({"prompt": prompt, "system": ""})
                raise ProviderError("HTTP 502 upstream")
            return super().complete(prompt, **kw)

    for pages in (10, 12, 14):
        deck, report = build_deck(tiny_book(), DeckOptions(pages=pages), FailsCh2())
        assert len(deck["slides"]) == pages, report.warnings
        assert not any("requested" in w or "still missing" in w for w in report.warnings)
        for s in deck["slides"]:
            assert is_language(slide_text(s), "zh"), s
        _assert_distinct_titles(deck)


def test_exact_page_count_in_chapter_scope_by_splitting():
    from stratum.services.bu_v2_provider import ProviderError

    class Fails(FakeProvider):
        def complete(self, prompt, **kw):
            if "这一章写" in prompt:
                raise ProviderError("HTTP 502 upstream")
            return super().complete(prompt, **kw)

    deck, report = build_deck(tiny_book(), DeckOptions(pages=9, chapter_id="ch2"), Fails())
    assert len(deck["slides"]) == 9, report.warnings
    _assert_distinct_titles(deck)


def test_slides_without_notes_are_kept_with_synthesised_notes():
    from stratum.services.bu_v2_provider import ModelResponse

    class NoNotes(FakeProvider):
        def complete(self, prompt, **kw):
            resp = super().complete(prompt, **kw)
            data = json.loads(resp.text)
            for sl in data.get("slides", []) if isinstance(data, dict) else []:
                sl.pop("notes", None)
            return ModelResponse(json.dumps(data, ensure_ascii=False), "fake", "fake")

    deck, report = build_deck(tiny_book(), DeckOptions(pages=8), NoNotes())
    assert len(deck["slides"]) == 8
    assert report.fallback_slides == 0
    assert all(s.get("notes") for s in deck["slides"] if s["type"] in CONTENT_TYPES)
