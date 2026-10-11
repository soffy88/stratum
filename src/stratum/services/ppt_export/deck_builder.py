"""Write a luobo-ppt ``deck.json`` from grounded book material.

Shape of the work:

* ``plan_slots`` decides deterministically how many slides each chapter gets
  (cover, optional contents, optional section dividers, content, closing), so
  the requested page count is met exactly whatever the model returns.
* one model call frames the deck (cover title, storyline, closing), and one call
  per chapter batch writes that batch's content slides. Calls run concurrently.
* every slide the model returns is normalised against the deck schema: only a
  safe subset of slide types, every field cut to the layout capacity of
  ``references/layouts.md``, LaTeX turned into plain text.
* language is enforced: a Chinese book must yield a Chinese deck. A batch whose
  slides come back in the wrong language is asked again with the failure named;
  if it still fails, the slot is filled from the material itself (definitions
  from the chapter's concepts, its thesis, its supported claims) rather than
  shipping an English slide or an invented one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from stratum.services.bu_v2_provider import ModelProvider, ProviderError
from stratum.services.ppt_export.fit import clen, plain_formula, trim
from stratum.services.ppt_export.material import BookMaterial, ChapterMaterial, is_language

MIN_PAGES = 5
MAX_PAGES = 30
DEFAULT_PAGES = 12
BATCH = 4
_MAX_WORKERS = 3
_ATTEMPTS = 3

Progress = Callable[[str, float], None]


class DeckBuildError(RuntimeError):
    pass


@dataclass
class DeckOptions:
    pages: int = DEFAULT_PAGES
    chapter_id: str | None = None
    audience: str = ""
    notes: bool = True

    def clamp(self) -> DeckOptions:
        self.pages = max(MIN_PAGES, min(MAX_PAGES, int(self.pages or DEFAULT_PAGES)))
        return self


@dataclass
class Slot:
    kind: str  # cover | toc | section | content | closing
    chapter_id: str | None = None
    batch: int = 0
    count: int = 1
    focus: list[str] = field(default_factory=list)


@dataclass
class DeckReport:
    model_calls: int = 0
    language_retries: int = 0
    fallback_slides: int = 0
    titles_polished: int = 0
    warnings: list[str] = field(default_factory=list)


# ── capacities (references/layouts.md, low density) ──────────────────────────

TITLE_CAP = 20
NOTES_MAX = 320
CAPS: dict[str, dict[str, Any]] = {
    "definitions": {"side.title": 12, "side.body": 40, "items": (2, 4, 8, 26)},
    "explain": {"blocks": (2, 6), "label": 12, "text": 40, "formula": 44, "rule": 30, "note": 30},
    "process": {"items": (2, 5, 8, 30), "takeaway": 36},
    "compare": {"side.title": 10, "side.items": (1, 4, 20)},
    "grid": {"items": (2, 4, 10, 28)},
    "statement": {"headline": 16, "body": 44, "pill": 22},
    "warnings": {"items": (1, 3, 14, 32), "quote_lines": (1, 2, 12)},
    "question": {"question": 30, "kicker": 12, "body": 40},
}
CONTENT_TYPES = set(CAPS)


# ── planning ─────────────────────────────────────────────────────────────────


def _chunks(items: list[str], n: int) -> list[list[str]]:
    if n <= 1:
        return [items]
    size = max(1, -(-len(items) // n))
    out = [items[i : i + size] for i in range(0, len(items), size)]
    while len(out) < n:
        out.append([])
    return out[:n]


def plan_slots(material: BookMaterial, opts: DeckOptions) -> list[Slot]:
    """Allocate the requested page count across cover, chapters and closing."""
    opts.clamp()
    pages = opts.pages
    if opts.chapter_id:
        ch = material.chapter(opts.chapter_id)
        if ch is None or not ch.usable:
            raise DeckBuildError(f"chapter {opts.chapter_id} has no understanding to present")
        content = pages - 2
        slots = [Slot("cover", ch.chapter_id)]
        n_batches = -(-content // BATCH)
        focus = _chunks(ch.subsections, n_batches)
        left = content
        for b in range(n_batches):
            k = min(BATCH, left)
            slots.append(Slot("content", ch.chapter_id, b, k, focus[b] if n_batches > 1 else []))
            left -= k
        slots.append(Slot("closing", ch.chapter_id))
        return slots

    chapters = material.usable_chapters()
    if not chapters:
        raise DeckBuildError("the book understanding has no usable chapters")
    fixed = 2
    toc = 3 <= len(chapters) <= 8 and pages >= 8
    fixed += 1 if toc else 0
    sections = (
        pages >= 16
        and 3 <= len(chapters) <= 8
        and pages - fixed - len(chapters) >= 2 * len(chapters)
    )
    fixed += len(chapters) if sections else 0
    content = pages - fixed
    if content < len(chapters):
        keep = sorted(chapters, key=lambda c: -c.richness)[:content]
        chapters = [c for c in chapters if c in keep]
    alloc = {c.chapter_id: 1 for c in chapters}
    extra = content - len(chapters)
    ranked = sorted(chapters, key=lambda c: -c.richness)
    i = 0
    while extra > 0 and ranked:
        alloc[ranked[i % len(ranked)].chapter_id] += 1
        extra -= 1
        i += 1

    slots = [Slot("cover")]
    if toc:
        slots.append(Slot("toc"))
    for c in chapters:
        if sections:
            slots.append(Slot("section", c.chapter_id))
        k_total = alloc[c.chapter_id]
        n_batches = -(-k_total // BATCH)
        focus = _chunks(c.subsections, n_batches)
        left = k_total
        for b in range(n_batches):
            k = min(BATCH, left)
            slots.append(Slot("content", c.chapter_id, b, k, focus[b] if n_batches > 1 else []))
            left -= k
    slots.append(Slot("closing"))
    return slots


# ── prompts ──────────────────────────────────────────────────────────────────

_SCHEMA_ZH = """可用页型与字段（只能用这些 type，字段名必须一致，括号里是字数上限）：
1. explain 讲公式、定理、判断规则：{"type":"explain","title":"结论式标题","blocks":[{"label":"小标签(10)"},{"text":"一句说明(36)"},{"formula":"纯文本公式(40)"},{"rule":"判断规则(28)","tone":"up 或 down"},{"note":"小注(28)"}]}，blocks 3 到 6 块
2. definitions 讲几个并列概念：{"type":"definitions","title":"…","side":{"title":"引导(10)","body":"一句话(36)"},"items":[{"title":"概念名(8)","text":"解释(24)"}]}，items 2 到 4 条
3. process 讲有先后顺序的步骤或推导：{"type":"process","title":"…","items":[{"title":"步骤名(8)","text":"做什么(28)"}],"takeaway":"一句结论(30)"}，items 3 到 5 条
4. compare 讲两种东西的对比：{"type":"compare","title":"…","left":{"title":"甲(8)","items":["要点(18)"]},"right":{"title":"乙(8)","items":["要点(18)"]}}，每边 2 到 4 条
5. grid 讲三四个并列要点：{"type":"grid","title":"…","items":[{"title":"要点(8)","text":"说明(26)"}]}，items 3 到 4 条
6. statement 一句核心主张：{"type":"statement","title":"…","headline":"主张(14)","body":"解释(40)"}
7. warnings 讲易错点、适用条件、边界：{"type":"warnings","title":"…","items":[{"title":"易错点(12)","text":"说明(30)"}],"quote_lines":["金句(10)","金句(10)"]}，items 2 到 3 条
8. question 抛出一个问题引出下一页：{"type":"question","question":"问题(26)，可用 **强调词**","body":"提示(36)"}
每一页都必须有 "notes"（老师口播稿，100 到 220 字）。"""

_RULES_ZH = """写作规则：
1. 每页 title 是一句能单独成立的结论（6 到 18 个字），不是话题名。好的：“导数就是瞬时变化率的极限”；不好的：“导数的定义”。
2. 一页只讲一个观点。屏幕上只放关键词和短句，严格遵守括号里的字数上限；展开的讲解写进 notes。
3. notes 是老师上课时要说的话：口语化、短句，和本页内容一一对应，可以引用书中的例子和说法。
4. 只使用下面资料里的知识。资料里没有的事实、数字、年份、人名、引文一律不写。
5. 资料中出现的英文内容，请翻译成中文后使用（专有名词可在中文后括注英文）。
6. 公式写成纯文本，如 f′(x) = lim(Δx→0) Δy/Δx，不要用 $ 或 \\frac 之类的 LaTeX 命令。
7. 同一种 type 不要连续用三次；理科教材优先用 explain、definitions、process、warnings。
8. 输出语言：简体中文。title、要点、notes 全部用中文。"""

_SCHEMA_EN = """Slide types you may use (only these; field names exact; numbers are maximum words):
1. explain - formulas, theorems, rules: {"type":"explain","title":"claim title","blocks":[{"label":"tag (6)"},{"text":"one sentence (20)"},{"formula":"plain-text formula"},{"rule":"rule (16)","tone":"up or down"},{"note":"note (16)"}]}, 3-6 blocks
2. definitions - parallel concepts: {"type":"definitions","title":"...","side":{"title":"lead (6)","body":"one line (20)"},"items":[{"title":"term (4)","text":"meaning (14)"}]}, 2-4 items
3. process - ordered steps: {"type":"process","title":"...","items":[{"title":"step (4)","text":"what to do (16)"}],"takeaway":"one line (18)"}, 3-5 items
4. compare - two things side by side: {"type":"compare","title":"...","left":{"title":"A (4)","items":["point (10)"]},"right":{"title":"B (4)","items":["point (10)"]}}
5. grid - three or four parallel points: {"type":"grid","title":"...","items":[{"title":"point (5)","text":"detail (14)"}]}
6. statement - one core claim: {"type":"statement","title":"...","headline":"claim (8)","body":"explanation (24)"}
7. warnings - pitfalls, conditions, limits: {"type":"warnings","title":"...","items":[{"title":"pitfall (6)","text":"detail (18)"}],"quote_lines":["line (6)","line (6)"]}
8. question - a question that sets up the next slide: {"type":"question","question":"question (16)","body":"hint (20)"}
Every slide must carry "notes": the lecturer's spoken script, 60-160 words."""

_RULES_EN = """Rules:
1. Each title is a complete claim (4-12 words), not a topic label: "The derivative is the limit of the rate of change", not "Definition of derivative".
2. One idea per slide. Only keywords and short phrases on screen, within the word limits; the explanation goes into notes.
3. notes is what the lecturer says: spoken, short sentences, matching the slide; reuse the book's examples and wording.
4. Use only the material below. Never add facts, numbers, years, names or quotes that are not in it.
5. Formulas in plain text such as f'(x) = lim(dx->0) dy/dx; no $ or LaTeX commands.
6. Do not use the same type three times in a row.
7. Output language: English."""


def _system(lang: str) -> str:
    if lang == "zh":
        return (
            "你是一名资深大学讲师兼演示文稿撰稿人。你只根据用户提供的书籍资料写讲解型 PPT，"
            "绝不编造资料中没有的内容。你只输出 JSON，不输出任何解释。所有内容使用简体中文。"
        )
    return (
        "You are a senior university lecturer who writes lecture slide decks. You use only the "
        "book material the user provides and never invent anything. Output JSON only."
    )


def chapter_prompt(
    material: BookMaterial,
    chapter: ChapterMaterial,
    slot: Slot,
    *,
    audience: str,
    used_titles: list[str],
    feedback: str = "",
) -> str:
    data = json.dumps(
        chapter.to_prompt(material.concept_defs, focus=slot.focus or None),
        ensure_ascii=False,
        indent=1,
    )
    focus = "、".join(slot.focus) if slot.focus else ""
    used = "\n".join(f"- {t}" for t in used_titles) or "-"
    if material.language == "zh":
        parts = [
            f"任务：为《{material.title}》中“{chapter.display_title()}”这一章写 {slot.count} 页"
            f"讲解型 PPT 内容页（这是第 {slot.batch + 1} 部分）。",
            f"受众：{audience or '正在学习这本书的学生'}。场景：课堂讲解。",
            "",
            "【本章资料】（来自 AII 对本书的理解和原文摘录，只能使用这些）",
            data,
        ]
        if focus:
            parts += ["", f"【这一部分侧重的小节】{focus}"]
        parts += ["", "【其他部分已用的标题，不要重复】", used, "", _RULES_ZH, "", _SCHEMA_ZH]
        if feedback:
            parts += ["", f"【上次输出的问题，必须改正】{feedback}"]
        parts += ["", f'输出：{{"slides": [...]}}，正好 {slot.count} 页。']
        return "\n".join(parts)
    parts = [
        f'Task: write {slot.count} lecture content slides for the chapter "'
        f'{chapter.display_title()}" of "{material.title}" (part {slot.batch + 1}).',
        f"Audience: {audience or 'students reading this book'}. Setting: a lecture.",
        "",
        "[Chapter material - the only facts you may use]",
        data,
    ]
    if focus:
        parts += ["", f"[Sections to focus on] {', '.join(slot.focus)}"]
    parts += ["", "[Titles already used elsewhere - do not repeat]", used, "", _RULES_EN]
    parts += ["", _SCHEMA_EN]
    if feedback:
        parts += ["", f"[Problems with your previous answer - fix them] {feedback}"]
    parts += ["", f'Output: {{"slides": [...]}} with exactly {slot.count} slides.']
    return "\n".join(parts)


def frame_prompt(material: BookMaterial, chapter: ChapterMaterial | None, audience: str) -> str:
    data = chapter.to_prompt(material.concept_defs) if chapter else material.book_prompt()
    blob = json.dumps(data, ensure_ascii=False, indent=1)
    scope_zh = (
        f"《{material.title}》“{chapter.display_title()}”一章"
        if chapter
        else f"《{material.title}》"
    )
    if material.language == "zh":
        return "\n".join(
            [
                f"任务：为{scope_zh}的讲解型 PPT 写封面和结尾。受众：{audience or '学生'}。",
                "【资料】（只能使用这些）",
                blob,
                "",
                "要求：title 是一句结论（6 到 14 个字），点出这部分内容最核心的思想；"
                "subtitle 不超过 16 个字；storyline 用一句话讲清这份讲解的来龙去脉；"
                "closing.headline 是结论或行动号召（不超过 16 个字，不要写“谢谢”）；"
                "closing.body 不超过 28 个字；cover_notes 和 closing.notes 是口播稿，各 80 到 180 字。"
                "资料中的英文请翻译成中文。全部用简体中文。",
                '输出：{"title":"…","subtitle":"…","storyline":"…","cover_notes":"…",'
                '"closing":{"headline":"…","body":"…","notes":"…"}}',
            ]
        )
    return "\n".join(
        [
            f'Task: write the cover and closing of a lecture deck on "{material.title}"'
            + (f', chapter "{chapter.display_title()}"' if chapter else "")
            + f". Audience: {audience or 'students'}.",
            "[Material - the only facts you may use]",
            blob,
            "",
            "title: one claim of 4-8 words stating the core idea; subtitle up to 10 words; "
            "storyline: one sentence; closing.headline: a conclusion or call to action (up to 9 "
            'words, never "thank you"); closing.body up to 16 words; cover_notes and closing.notes: '
            "spoken scripts of 50-120 words.",
            'Output: {"title":"...","subtitle":"...","storyline":"...","cover_notes":"...",'
            '"closing":{"headline":"...","body":"...","notes":"..."}}',
        ]
    )


# ── normalisation ────────────────────────────────────────────────────────────


# Labels from the schema text that a model sometimes copies verbatim.
_PLACEHOLDERS = {
    "引导",
    "小标签",
    "概念名",
    "步骤名",
    "要点",
    "甲",
    "乙",
    "金句",
    "易错点",
    "主张",
    "问题",
    "提示",
    "说明",
    "解释",
    "一句说明",
    "一句话",
    "判断规则",
    "小注",
    "结论式标题",
    "做什么",
    "lead",
    "term",
    "point",
    "tag",
}


def _s(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = re.sub(r"[（(]\d{1,2}[)）]$", "", text).strip()  # copied "(12)" limits
    return "" if text in _PLACEHOLDERS or text in ("…", "...") else text


def _opt(value: str, cap: int) -> str:
    """Optional field: cut at a clean boundary or drop it, never mid-phrase."""
    if clen(value) <= cap:
        return value
    cut = trim(value, cap)
    return cut if cut and cut[-1:] in "。！？.!?" or clen(cut) >= cap * 0.8 else ""


def _items(raw: Any, lo: int, hi: int, tcap: int, xcap: int) -> list[dict[str, str]] | None:
    out = []
    for it in raw if isinstance(raw, list) else []:
        if isinstance(it, str):
            it = {"text": it}
        if not isinstance(it, dict):
            continue
        title = trim(_s(it.get("title") or it.get("name") or it.get("label")), tcap)
        text = trim(_s(it.get("text") or it.get("desc") or it.get("description")), xcap)
        if not text and not title:
            continue
        entry = {"title": title, "text": text} if title else {"text": text}
        out.append(entry)
    out = out[:hi]
    return out if len(out) >= lo else None


def _str_items(raw: Any, lo: int, hi: int, cap: int) -> list[str] | None:
    out = [trim(_s(x if not isinstance(x, dict) else x.get("text")), cap) for x in raw or []]
    out = [x for x in out if x][:hi]
    return out if len(out) >= lo else None


def normalize_slide(raw: Any) -> dict[str, Any] | None:
    """Coerce one model slide into a valid luobo-ppt slide, or ``None``."""
    if not isinstance(raw, dict):
        return None
    typ = _s(raw.get("type")).lower()
    if typ == "list":
        typ = "grid"
    if typ not in CONTENT_TYPES:
        return None
    caps = CAPS[typ]
    slide: dict[str, Any] = {"type": typ}
    title = trim(_s(raw.get("title")), TITLE_CAP)
    if typ != "question":
        if not title:
            return None
        slide["title"] = title
    if typ == "definitions":
        side = raw.get("side") if isinstance(raw.get("side"), dict) else {}
        lo, hi, tc, xc = caps["items"]
        items = _items(raw.get("items"), lo, hi, tc, xc)
        if not items:
            return None
        slide["items"] = items
        st, sb = _opt(_s(side.get("title")), 12), _opt(_s(side.get("body")), 40)
        if sb:
            slide["side"] = {"title": st, "body": sb} if st else {"body": sb}
    elif typ == "explain":
        blocks = []
        for b in raw.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            for key in ("label", "text", "formula", "rule", "note"):
                if b.get(key):
                    val = _s(b[key])
                    if key == "formula":
                        val = trim(plain_formula(val), caps["formula"])
                    else:
                        val = trim(plain_formula(val) if "\\" in val else val, caps[key])
                    if val:
                        blk: dict[str, str] = {key: val}
                        if key == "rule":
                            tone = _s(b.get("tone")).lower()
                            blk["tone"] = tone if tone in ("up", "down") else "up"
                        blocks.append(blk)
                    break
        lo, hi = caps["blocks"]
        blocks = blocks[:hi]
        if len(blocks) < lo or not any(
            ("text" in b or "formula" in b or "rule" in b) for b in blocks
        ):
            return None
        slide["blocks"] = blocks
    elif typ == "process":
        lo, hi, tc, xc = caps["items"]
        items = _items(raw.get("items"), lo, hi, tc, xc)
        if not items:
            return None
        for it in items:
            it.setdefault("title", trim(it["text"], tc))
        slide["items"] = items
    elif typ == "compare":
        sides = {}
        lo, hi, cap = caps["side.items"]
        for key in ("left", "right"):
            side = raw.get(key) if isinstance(raw.get(key), dict) else {}
            its = _str_items(side.get("items"), lo, hi, cap)
            st = trim(_s(side.get("title")), caps["side.title"])
            if not its or not st:
                return None
            sides[key] = {"title": st, "items": its}
        slide.update(sides)
    elif typ == "grid":
        lo, hi, tc, xc = caps["items"]
        items = _items(raw.get("items"), lo, hi, tc, xc)
        if not items:
            return None
        slide["items"] = items
    elif typ == "statement":
        headline = trim(_s(raw.get("headline")), caps["headline"])
        if not headline:
            return None
        slide["headline"] = headline
        body = _opt(_s(raw.get("body")), caps["body"])
        if body:
            slide["body"] = body
    elif typ == "warnings":
        lo, hi, tc, xc = caps["items"]
        items = _items(raw.get("items"), lo, hi, tc, xc)
        if not items:
            return None
        slide["items"] = items
        ql = _str_items(raw.get("quote_lines"), 1, 2, 12)
        if ql:
            slide["quote_lines"] = ql
    elif typ == "question":
        q = trim(_s(raw.get("question") or raw.get("title")), caps["question"])
        if not q:
            return None
        slide["question"] = q
        body = _opt(_s(raw.get("body")), caps["body"])
        if body:
            slide["body"] = body
    take = _opt(_s(raw.get("takeaway")), 30)
    if take and typ in ("process", "explain"):
        slide["takeaway"] = take
    notes = _s(raw.get("notes"))
    if notes:
        slide["notes"] = notes[:NOTES_MAX]
    return slide


_FORMULA_KEYS = {"formula"}


def slide_text(slide: dict[str, Any], *, include_notes: bool = True) -> str:
    """All human-language text of a slide (formulas excluded) for language checks."""
    parts: list[str] = []

    def walk(v: Any, key: str = "") -> None:
        if key in _FORMULA_KEYS or key in ("type", "tone", "layout", "n"):
            return
        if key == "notes" and not include_notes:
            return
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)

    walk(slide)
    return " ".join(parts)


# ── fallbacks (material only, never invented) ────────────────────────────────


def fallback_slides(
    chapter: ChapterMaterial, count: int, lang: str, defs: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Slides assembled directly from stored understanding when the model fails."""
    zh = lang == "zh"
    out: list[dict[str, Any]] = []
    usable_concepts = [c for c in chapter.concepts if is_language(c, lang)][:4]
    if len(usable_concepts) >= 2:
        out.append(
            {
                "type": "grid",
                "title": (
                    trim(f"{'、'.join(usable_concepts[:3])}是本章的基石", TITLE_CAP)
                    if zh
                    else "These concepts carry the chapter"
                ),
                "items": [_concept_item(c, (defs or {}).get(c, ""), lang) for c in usable_concepts],
                "notes": (
                    f"这一章引入了{'、'.join(usable_concepts)}这几个核心概念。"
                    + (chapter.thesis if is_language(chapter.thesis, lang) else "")
                )
                if zh
                else f"This chapter introduces {', '.join(usable_concepts)}. {chapter.thesis}",
            }
        )
    if chapter.thesis and is_language(chapter.thesis, lang):
        out.append(
            {
                "type": "statement",
                "title": trim(chapter.display_title(), TITLE_CAP),
                "headline": trim(chapter.thesis, 16),
                "body": trim(chapter.goal if is_language(chapter.goal, lang) else "", 44)
                or trim(chapter.thesis, 44),
                "notes": chapter.thesis + (chapter.goal if is_language(chapter.goal, lang) else ""),
            }
        )
    claims = [c for c in chapter.claims if is_language(c, lang)]
    for i in range(0, len(claims), 4):
        group = claims[i : i + 4]
        if len(group) < 2:
            break
        out.append(
            {
                "type": "grid",
                "title": "书中明确给出这些结论" if zh else "The text states these results",
                "items": [{"text": trim(c, 28)} for c in group],
                "notes": ("书里明确给出的结论有：" if zh else "The text states: ")
                + "；".join(group),
            }
        )
    return out[:count]


def _concept_item(name: str, definition: str, lang: str) -> dict[str, str]:
    if definition and is_language(definition, lang):
        return {"title": trim(name, 10), "text": trim(definition, 28)}
    return {"text": trim(name, 28)}


_TOPIC_ENDINGS_ZH = (
    "的定义",
    "的推导",
    "的概念",
    "的应用",
    "的计算",
    "的方法",
    "的性质",
    "的意义",
    "的作用",
    "的分类",
    "概述",
    "简介",
    "介绍",
    "总结",
    "要点",
    "核心概念",
    "基本概念",
    "关键结论",
)
_TOPIC_START_EN = ("definition of", "introduction to", "overview", "summary", "key concepts")


def looks_like_topic(title: str, lang: str) -> bool:
    """A label ("导数的定义") rather than a claim ("导数是变化率的极限")."""
    t = (title or "").replace("**", "").strip()
    if not t:
        return False
    if lang == "zh":
        return t.endswith(_TOPIC_ENDINGS_ZH) or (
            clen(t) <= 6 and not re.search(r"[是能让把会要]", t)
        )
    low = t.lower()
    return low.startswith(_TOPIC_START_EN) or len(low.split()) <= 3


def polish_prompt(material: BookMaterial, slides: list[dict[str, Any]]) -> str:
    rows = []
    for sl in slides:
        points = [p for p in slide_text(sl, include_notes=False).split(" ") if p][:12]
        rows.append(
            {
                "n": sl["n"],
                "title": sl.get("title", ""),
                "points": " ".join(points)[:200],
                "notes": (sl.get("notes") or "")[:160],
            }
        )
    blob = json.dumps(rows, ensure_ascii=False, indent=1)
    if material.language == "zh":
        return "\n".join(
            [
                f"下面是《{material.title}》讲解 PPT 中几页的标题，它们像话题名，不像结论。",
                "请把每个标题改写成一句能单独成立的结论（6 到 18 个字），只依据该页的要点和备注，"
                "不新增事实。例：“导数的定义”→“导数是增量之比的极限”。全部用简体中文。",
                blob,
                '输出：{"titles": [{"n": 页码, "title": "新标题"}]}',
            ]
        )
    return "\n".join(
        [
            f'These slide titles from a lecture deck on "{material.title}" read like topic labels.',
            "Rewrite each as a standalone claim of 4-12 words, using only that slide's points and "
            "notes; add no new facts.",
            blob,
            'Output: {"titles": [{"n": slide number, "title": "new title"}]}',
        ]
    )


def _polish_titles(
    provider: ModelProvider,
    material: BookMaterial,
    slides: list[dict[str, Any]],
    report: DeckReport,
) -> int:
    """One call that turns topic-label titles into conclusions. Returns count fixed."""
    lang = material.language
    targets = [
        sl
        for sl in slides
        if sl.get("type") in CONTENT_TYPES
        and sl.get("type") != "question"
        and looks_like_topic(sl.get("title", ""), lang)
    ]
    if not targets:
        return 0
    report.model_calls += 1
    try:
        data = provider.complete(
            polish_prompt(material, targets),
            system=_system(lang),
            json_mode=True,
            max_tokens=200 * len(targets) + 400,
            temperature=0.2,
        ).json()
    except ProviderError as exc:
        report.warnings.append(f"title polish: {str(exc)[:160]}")
        return 0
    items = data.get("titles") if isinstance(data, dict) else data
    by_n = {sl["n"]: sl for sl in targets}
    fixed = 0
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        try:
            sl = by_n.get(int(it.get("n")))
        except (TypeError, ValueError):
            continue
        new = trim(_s(it.get("title")), TITLE_CAP)
        if (
            sl
            and new
            and 4 <= clen(new) <= TITLE_CAP
            and is_language(new, lang)
            and not looks_like_topic(new, lang)
        ):
            sl["title"] = new
            fixed += 1
    return fixed


# ── building ─────────────────────────────────────────────────────────────────


def _parse_slides(text_json: Any) -> list[Any]:
    if isinstance(text_json, dict):
        for key in ("slides", "pages", "items"):
            if isinstance(text_json.get(key), list):
                return list(text_json[key])
        return [text_json] if text_json.get("type") else []
    return list(text_json) if isinstance(text_json, list) else []


def _wrong_language(slides: list[dict[str, Any]], lang: str) -> list[int]:
    return [i for i, s in enumerate(slides) if not is_language(slide_text(s), lang)]


def _batch_feedback(lang: str, n_lang: int, n_notes: int, n_invalid: int, need: int) -> str:
    zh = lang == "zh"
    problems = []
    if n_lang:
        problems.append(
            f"有 {n_lang} 页没有用简体中文，所有标题、要点和备注都必须用中文"
            if zh
            else f"{n_lang} slides were not in English"
        )
    if n_notes:
        problems.append(
            f"有 {n_notes} 页缺少 notes，每页都必须写 100 到 220 字的口播稿"
            if zh
            else f"{n_notes} slides had no notes"
        )
    if n_invalid:
        problems.append(
            f"有 {n_invalid} 页的 type 或字段不符合页型说明（字段名必须一致，条目数要够）"
            if zh
            else f"{n_invalid} slides did not match the slide type fields"
        )
    problems.append(f"请重新输出正好 {need} 页" if zh else f"output exactly {need} slides")
    return "；".join(problems)


def _write_batch(
    provider: ModelProvider,
    material: BookMaterial,
    chapter: ChapterMaterial,
    slot: Slot,
    opts: DeckOptions,
    used_titles: list[str],
    report: DeckReport,
) -> list[dict[str, Any]]:
    """Write one batch, accumulating valid slides across attempts."""
    lang = material.language
    tag = f"{chapter.chapter_id}#{slot.batch}"
    feedback = ""
    kept: list[dict[str, Any]] = []
    for attempt in range(_ATTEMPTS):
        need = slot.count - len(kept)
        sub = Slot(slot.kind, slot.chapter_id, slot.batch, need, slot.focus)
        prompt = chapter_prompt(
            material,
            chapter,
            sub,
            audience=opts.audience,
            used_titles=used_titles + [k["title"] for k in kept],
            feedback=feedback,
        )
        report.model_calls += 1
        try:
            resp = provider.complete(
                prompt,
                system=_system(lang),
                json_mode=True,
                max_tokens=900 * need + 600,
                temperature=0.3,
            )
            raw = _parse_slides(resp.json())
        except ProviderError as exc:
            feedback = (
                "上次输出不是合法 JSON，请只输出 JSON。"
                if lang == "zh"
                else "Output valid JSON only."
            )
            report.warnings.append(f"{tag} attempt {attempt + 1}: {str(exc)[:160]}")
            continue
        normalized = [normalize_slide(r) for r in raw]
        n_invalid = sum(1 for x in normalized if x is None) + max(0, need - len(raw))
        slides = [x for x in normalized if x]
        n_lang = n_notes = 0
        for sl in slides:
            if not is_language(slide_text(sl), lang):
                n_lang += 1
            elif opts.notes and len(sl.get("notes", "")) < 30:
                n_notes += 1
            elif sl["title"] not in {k["title"] for k in kept}:
                kept.append(sl)
        if n_lang:
            report.language_retries += 1
        if len(kept) >= slot.count:
            return kept[: slot.count]
        feedback = _batch_feedback(lang, n_lang, n_notes, n_invalid, slot.count - len(kept))
        report.warnings.append(
            f"{tag} attempt {attempt + 1}: {len(raw)} returned, lang={n_lang} "
            f"notes={n_notes} invalid={n_invalid}"
        )
    missing = slot.count - len(kept)
    if missing > 0:
        fill = [
            s
            for s in fallback_slides(chapter, missing + 2, lang, material.concept_defs)
            if s["title"] not in used_titles
        ]
        report.fallback_slides += min(missing, len(fill))
        kept = kept + fill[:missing]
        if len(kept) < slot.count:
            report.warnings.append(f"{tag}: only {len(kept)} of {slot.count} slides grounded")
    return kept[: slot.count]


def _frame(
    provider: ModelProvider,
    material: BookMaterial,
    chapter: ChapterMaterial | None,
    opts: DeckOptions,
    report: DeckReport,
) -> dict[str, Any]:
    lang = material.language
    for _ in range(2):
        report.model_calls += 1
        try:
            data = provider.complete(
                frame_prompt(material, chapter, opts.audience),
                system=_system(lang),
                json_mode=True,
                max_tokens=1200,
                temperature=0.3,
            ).json()
        except ProviderError as exc:
            report.warnings.append(f"frame: {str(exc)[:120]}")
            continue
        if not isinstance(data, dict):
            continue
        closing = data.get("closing") if isinstance(data.get("closing"), dict) else {}
        text = " ".join(
            _s(x) for x in (data.get("title"), data.get("subtitle"), closing.get("headline"))
        )
        if not is_language(text, lang):
            report.language_retries += 1
            continue
        return data
    return {}


def _spoken(slide: dict[str, Any], zh: bool) -> str:
    """Minimal notes from the slide itself, for the rare slide that has none."""
    points = [
        (it.get("title", "") + ("：" if zh else ": ") if it.get("title") else "")
        + it.get("text", "")
        for it in slide.get("items", [])
        if isinstance(it, dict)
    ]
    head = slide.get("title") or slide.get("question") or ""
    if zh:
        return f"这一页的结论是：{head}。" + (
            "要点有：" + "；".join(points) + "。" if points else ""
        )
    return f"The point of this slide: {head}. " + ("; ".join(points) if points else "")


def _short_title(title: str) -> str:
    t = re.sub(r"\s*[\(（].*?[\)）]\s*", "", title or "")
    return trim(t, 14)


def _chapter_label(ch: ChapterMaterial, lang: str) -> str:
    t = re.sub(
        r"^\s*(chapter\s*\d+\s*[:：.]?|第\s*\S+?\s*章|\d+\s*[.、:：])\s*",
        "",
        ch.title or "",
        flags=re.I,
    ).strip()
    return t or ch.question or ch.chapter_id


def _glyph(material: BookMaterial) -> str:
    for ch in material.title:
        if "\u4e00" <= ch <= "\u9fff" or ch.isalpha():
            return ch.upper()
    return "A"


def build_deck(
    material: BookMaterial,
    opts: DeckOptions,
    provider: ModelProvider,
    *,
    progress: Progress | None = None,
) -> tuple[dict[str, Any], DeckReport]:
    """Write the deck. Returns ``(deck_json, report)``."""
    opts.clamp()
    report = DeckReport()
    lang = material.language
    zh = lang == "zh"
    slots = plan_slots(material, opts)
    chapter = material.chapter(opts.chapter_id) if opts.chapter_id else None
    content_slots = [s for s in slots if s.kind == "content"]
    total_calls = len(content_slots) + 1
    done = [0]

    def tick() -> None:
        done[0] += 1
        if progress:
            progress("writing", done[0] / total_calls)

    # Titles the batches should avoid: chapter theses keep batches apart cheaply.
    seed_titles = [c.display_title() for c in material.usable_chapters()][:20]

    def run_slot(slot: Slot) -> list[dict[str, Any]]:
        ch = material.chapter(slot.chapter_id or "")
        assert ch is not None
        try:
            return _write_batch(provider, material, ch, slot, opts, seed_titles, report)
        finally:
            tick()

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        frame_future = pool.submit(_frame, provider, material, chapter, opts, report)
        results = list(pool.map(run_slot, content_slots))
        frame = frame_future.result()
    tick()

    by_slot = {id(s): r for s, r in zip(content_slots, results)}
    closing = frame.get("closing") if isinstance(frame.get("closing"), dict) else {}
    book_short = _short_title(material.title)

    slides: list[dict[str, Any]] = []
    for slot in slots:
        if slot.kind == "cover":
            title = trim(_s(frame.get("title")), 16)
            if not title:
                title = trim(
                    (chapter.thesis if chapter and is_language(chapter.thesis, lang) else "")
                    or (_chapter_label(chapter, lang) if chapter else book_short),
                    16,
                )
            subtitle = _opt(_s(frame.get("subtitle")), 18) or trim(
                _chapter_label(chapter, lang) if chapter else book_short, 18
            )
            cover: dict[str, Any] = {
                "type": "cover",
                "kicker": trim(
                    book_short
                    if chapter
                    else (material.genre if is_language(material.genre, lang) else book_short),
                    14,
                ),
                "title": title,
                "subtitle": subtitle,
            }
            notes = _s(frame.get("cover_notes"))
            cover["notes"] = (
                notes[:NOTES_MAX]
                if notes
                else (
                    f"今天我们来讲{_chapter_label(chapter, lang) if chapter else material.title}。{title}。"
                    if zh
                    else f"Today: {title}."
                )
            )
            slides.append(cover)
        elif slot.kind == "toc":
            items = []
            for c in material.usable_chapters()[:8]:
                items.append({"title": trim(_chapter_label(c, lang), 14)})
            slides.append({"type": "toc", "title": "目录" if zh else "Contents", "items": items})
        elif slot.kind == "section":
            c = material.chapter(slot.chapter_id or "")
            assert c is not None
            sub = c.question if is_language(c.question, lang) else ""
            slides.append(
                {
                    "type": "section",
                    "title": trim(_chapter_label(c, lang), 16),
                    **({"subtitle": trim(sub, 24)} if sub else {}),
                }
            )
        elif slot.kind == "content":
            for s in by_slot.get(id(slot), []):
                if opts.notes and not s.get("notes"):
                    s["notes"] = _spoken(s, zh)
                slides.append(s)
        elif slot.kind == "closing":
            headline = trim(_s(closing.get("headline")), 18) or trim(
                ("先吃透核心概念，再动手练习" if zh else "Master the ideas, then practise"), 18
            )
            body = _opt(_s(closing.get("body")), 30)
            c_notes = _s(closing.get("notes"))
            slides.append(
                {
                    "type": "closing",
                    "headline": headline,
                    **({"body": body} if body else {}),
                    "notes": c_notes[:NOTES_MAX]
                    if c_notes
                    else (f"最后总结一下：{headline}。" if zh else f"To sum up: {headline}."),
                }
            )
    if not opts.notes:
        for s in slides:
            s.pop("notes", None)
    for i, s in enumerate(slides, 1):
        s["n"] = i
    report.titles_polished = _polish_titles(provider, material, slides, report)

    content_count = sum(1 for s in slides if s["type"] in CONTENT_TYPES)
    if content_count == 0:
        raise DeckBuildError("the model produced no usable slides and no fallback was possible")
    if len(slides) != opts.pages:
        report.warnings.append(f"{len(slides)} slides produced for {opts.pages} requested")

    scope_title = _chapter_label(chapter, lang) if chapter else book_short
    deck = {
        "meta": {
            "title": trim(_s(frame.get("title")) or scope_title, 20),
            "series": trim(book_short, 14),
            "footer": trim(f"{book_short} · {scope_title}" if chapter else book_short, 24),
            "topic": (
                f"lecture slides on {material.genre or 'a textbook'}"
                if material.genre and not zh
                else "university lecture slides explaining a textbook chapter"
            ),
            "anchor": {
                "description": "an open textbook with a softly glowing diagram above its pages",
                "glyph": _glyph(material),
            },
            "scenario": "talk",
            "audience": opts.audience or ("学生" if zh else "students"),
            "density": "low",
            "notes": bool(opts.notes),
            "auto_page": True,
            "storyline": trim(_s(frame.get("storyline")), 60),
            "aii_source": {
                "substrate_id": material.substrate_id,
                "run_id": material.run_id,
                "chapter_id": opts.chapter_id,
            },
        },
        "slides": slides,
    }
    return deck, report
