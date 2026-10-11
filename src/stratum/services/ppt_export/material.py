"""Collect the grounded material a deck is written from.

Everything here comes from what AII already stored about the book:

* ``stratum.chapter_understandings`` (BU2 P4/P5): chapter question, goal,
  thesis, concepts introduced, supported claims, qualifications;
* ``stratum.book_understandings_v2`` (P10): central theses and governing
  questions;
* ``stratum.book_syntheses`` (P13): core concepts with their definitions;
* the parsed book text (``derivative``), split into chapters by the same
  ``BookLoader`` BU2 used, for chapter titles, section headings and a short
  excerpt of the author's own wording.

The material is a read-only snapshot; the model never sees anything else.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


class MaterialUnavailable(LookupError):
    """The book exists but has no understanding to build a deck from."""


def detect_language(text: str) -> str:
    """``zh`` when Chinese prose dominates, else ``en``.

    Counts CJK characters against latin words of three or more letters, so a
    Chinese maths text full of ``x``, ``dx`` and ``sin`` still reads as Chinese.
    """
    cjk = len(_CJK.findall(text or ""))
    words = len(_LATIN_WORD.findall(text or ""))
    return "zh" if cjk and cjk >= words else "en"


def is_language(text: str, language: str) -> bool:
    """Whether ``text`` is written in ``language`` (formula-heavy text tolerated)."""
    cjk = len(_CJK.findall(text or ""))
    words = len(_LATIN_WORD.findall(text or ""))
    if language == "zh":
        return cjk >= 2 * words or (cjk >= 6 and words <= 2)
    return words >= cjk


@dataclass
class ChapterMaterial:
    chapter_id: str
    number: int | None = None
    title: str = ""
    question: str = ""
    goal: str = ""
    thesis: str = ""
    role: str = ""
    concepts: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    subsections: list[str] = field(default_factory=list)
    section_snippets: dict[str, str] = field(default_factory=dict)
    excerpt: str = ""

    @property
    def richness(self) -> int:
        return (
            len(self.concepts) * 2
            + len(self.claims)
            + len(self.subsections) // 3
            + (3 if self.thesis else 0)
        )

    @property
    def usable(self) -> bool:
        return bool(self.thesis or self.question or self.concepts or self.claims)

    def display_title(self) -> str:
        return self.title or self.question or self.chapter_id

    def to_prompt(
        self, concept_defs: dict[str, str] | None = None, focus: list[str] | None = None
    ) -> dict[str, Any]:
        defs = concept_defs or {}
        names = focus or self.subsections
        sections = [
            {
                "title": t,
                **({"excerpt": self.section_snippets[t]} if self.section_snippets.get(t) else {}),
            }
            for t in names[:14]
        ]
        return {
            "chapter_id": self.chapter_id,
            "title": self.display_title(),
            "question": self.question,
            "goal": self.goal,
            "thesis": self.thesis,
            "concepts": [
                {"name": c, **({"definition": defs[c]} if defs.get(c) else {})}
                for c in self.concepts
            ],
            "claims": self.claims[:10],
            "qualifications": self.qualifications[:4],
            "sections": sections,
            "excerpt": self.excerpt if not focus else self.excerpt[:500],
        }


@dataclass
class BookMaterial:
    substrate_id: str
    title: str
    language: str
    run_id: str = ""
    bu_status: str = ""
    genre: str = ""
    central_theses: list[str] = field(default_factory=list)
    governing_questions: list[str] = field(default_factory=list)
    concept_defs: dict[str, str] = field(default_factory=dict)
    chapters: list[ChapterMaterial] = field(default_factory=list)

    def chapter(self, chapter_id: str) -> ChapterMaterial | None:
        return next((c for c in self.chapters if c.chapter_id == chapter_id), None)

    def usable_chapters(self) -> list[ChapterMaterial]:
        return [c for c in self.chapters if c.usable]

    def book_prompt(self) -> dict[str, Any]:
        return {
            "book_title": self.title,
            "genre": self.genre,
            "central_theses": self.central_theses[:4],
            "governing_questions": self.governing_questions[:4],
            "chapters": [
                {"chapter_id": c.chapter_id, "title": c.display_title(), "thesis": c.thesis}
                for c in self.usable_chapters()
            ],
        }


# ── helpers ──────────────────────────────────────────────────────────────────


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return [value] if value.strip() else []
    if isinstance(value, dict):
        for key in ("entries", "items", "list"):
            if isinstance(value.get(key), list):
                return list(value[key])
        return [value]
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _uniq(items: list[str], limit: int | None = None) -> list[str]:
    out: list[str] = []
    for s in items:
        s = (s or "").strip()
        if s and s not in out:
            out.append(s)
    return out[:limit] if limit else out


_MD_NOISE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>|^#+\s*", re.M)


def clean_excerpt(body: str, limit: int = 1400) -> str:
    """The first readable prose of a chapter body, markdown noise removed."""
    text = _MD_NOISE.sub("", body or "")
    lines = [ln.strip() for ln in text.splitlines()]
    kept = [ln for ln in lines if len(ln) >= 12 and not re.fullmatch(r"[\d\s.\-—·]+", ln)]
    joined = " ".join(kept)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined[:limit]


_CN_NUM = "一二三四五六七八九十"
_SECTION_LINE = re.compile(
    r"(?m)^[ \t#>*]*第([一二三四五六七八九十]{1,3})节[ \t\u3000]*([^\n…\.]{2,30}?)[ \t\u3000.…·\d]*$"
)
_SECTION_ANY = re.compile(r"第([一二三四五六七八九十]{1,3})节[ \t\u3000]*([^\s…\.\d]{2,24})")


def _sections_in(body: str) -> list[tuple[str, int]]:
    """Numbered section headings (第X节 ...) that open a line in ``body``."""
    out: list[tuple[str, int]] = []
    seen: set[str] = set()
    for m in _SECTION_LINE.finditer(body or ""):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append((f"第{m.group(1)}节 {m.group(2).strip()}", m.end()))
    return out


def toc_sections(markdown: str, n_chapters: int) -> list[list[str]]:
    """Section titles per chapter from the table of contents in the front matter.

    The contents lists 第一节, 第二节 ... for each chapter in order; a new
    第一节 starts the next chapter.
    """
    head = (markdown or "")[: max(20000, len(markdown or "") // 20)]
    groups: list[list[str]] = []
    for m in _SECTION_ANY.finditer(head):
        title = f"第{m.group(1)}节 {m.group(2).strip()}"
        if m.group(1) == "一" or not groups:
            if len(groups) >= n_chapters:
                break
            groups.append([])
        if title not in groups[-1]:
            groups[-1].append(title)
    return groups


def _snippet(body: str, start: int, limit: int = 320) -> str:
    return clean_excerpt(body[start : start + limit * 3], limit)


def _chapter_number(chapter_id: str) -> int | None:
    m = re.search(r"(\d+)", chapter_id or "")
    return int(m.group(1)) if m else None


# ── loading ──────────────────────────────────────────────────────────────────


class _DB:
    """Seam over ``stratum.db`` so tests can supply rows without Postgres."""

    def query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        from stratum.db import query

        return query(sql, params)


def _load_text_chapters(substrate_id: str) -> tuple[str, list[Any]]:
    """Chapter split of the parsed text, the same way BU2 ``execute`` does it.

    The structure extractor owns structure (BU2 spec §5); the loader's heading
    heuristics are the fallback. Chapter ids therefore match the stored
    chapter understandings.
    """
    from stratum.services.bu_v2_entrypoint import BookLoader
    from stratum.services.bu_v2_structure_extractor import (
        BookStructureExtractor,
        chapter_spans_from_structure,
    )

    loader = BookLoader()
    title, markdown, chapters = loader.load(substrate_id)
    if markdown:
        try:
            structure = BookStructureExtractor().extract_from_text(
                markdown,
                book_id=substrate_id,
                title=title,
                index=getattr(loader, "last_index", None) or None,
            )
            if structure.chapters:
                chapters = chapter_spans_from_structure(structure, markdown)
        except Exception:  # loader result stands
            pass
    return markdown, chapters


def _attach_sections(
    chapters: list[ChapterMaterial], text_by_id: dict[str, Any], markdown: str
) -> None:
    """Fill section titles and a short snippet under each from the book text."""
    toc: list[list[str]] | None = None
    for idx, ch in enumerate(chapters):
        body = getattr(text_by_id.get(ch.chapter_id), "text", "") or ""
        found = _sections_in(body)
        if found:
            ch.subsections = _uniq([t for t, _ in found], 30)
            for title, pos in found:
                ch.section_snippets.setdefault(title, _snippet(body, pos))
            continue
        if not ch.subsections:
            if toc is None:
                toc = toc_sections(markdown, len(chapters))
            if idx < len(toc):
                ch.subsections = toc[idx]
        for title in ch.subsections:
            name = title.split(" ", 1)[-1]
            pos = body.find(name, min(len(body), 200))
            if pos >= 0:
                ch.section_snippets.setdefault(title, _snippet(body, pos + len(name)))


def load_material(
    substrate_id: str,
    *,
    run_id: str | None = None,
    db: Any = None,
    text_loader: Any = None,
) -> BookMaterial:
    """Snapshot the stored understanding of one book.

    Ownership is checked by the caller; this function only reads. The latest
    VERIFIED run is preferred over newer drafts.
    """
    db = db or _DB()
    rows = db.query(
        "SELECT id, title, language FROM stratum.substrates WHERE id=%(sid)s",
        {"sid": substrate_id},
    )
    if not rows:
        raise MaterialUnavailable("book not found")
    sub = rows[0]

    bu_rows = db.query(
        """
        SELECT run_id, status, version, genre, central_theses_json, governing_questions_json
        FROM stratum.book_understandings_v2
        WHERE substrate_id=%(sid)s AND (%(rid)s IS NULL OR run_id=%(rid)s)
        ORDER BY (status='VERIFIED') DESC, version DESC
        LIMIT 1
        """,
        {"sid": substrate_id, "rid": run_id},
    )
    if not bu_rows:
        raise MaterialUnavailable(
            "this book has no book understanding yet; run book understanding first"
        )
    bu = bu_rows[0]
    rid = bu["run_id"]

    ch_rows = db.query(
        """
        SELECT chapter_id, chapter_question, chapter_goal, chapter_thesis, primary_role,
               concepts_introduced_refs, evidence_program_json, qualifications_json
        FROM stratum.chapter_understandings
        WHERE run_id=%(rid)s
        """,
        {"rid": rid},
    )
    syn_rows = db.query(
        "SELECT concept_system FROM stratum.book_syntheses WHERE run_id=%(rid)s LIMIT 1",
        {"rid": rid},
    )

    concept_defs: dict[str, str] = {}
    if syn_rows:
        cs = _as_dict(syn_rows[0].get("concept_system"))
        for bucket in ("core", "supporting", "peripheral", "concepts"):
            for c in _as_list(cs.get(bucket)):
                if isinstance(c, dict) and c.get("label") and c.get("definition"):
                    concept_defs.setdefault(str(c["label"]), str(c["definition"]))

    try:
        markdown, text_chapters = (text_loader or _load_text_chapters)(substrate_id)
    except Exception:  # the understanding alone is still usable
        markdown, text_chapters = "", []
    by_id = {getattr(c, "chapter_id", ""): c for c in text_chapters}

    chapters: list[ChapterMaterial] = []
    for r in ch_rows:
        cid = r["chapter_id"]
        claims = [
            str(e.get("claim_ref") or e.get("claim") or "")
            for e in _as_list(r.get("evidence_program_json"))
            if isinstance(e, dict) and e.get("is_supported", True)
        ]
        tc = by_id.get(cid)
        chapters.append(
            ChapterMaterial(
                chapter_id=cid,
                number=getattr(tc, "number", None) or _chapter_number(cid),
                title=str(getattr(tc, "title", "") or ""),
                question=(r.get("chapter_question") or "").strip(),
                goal=(r.get("chapter_goal") or "").strip(),
                thesis=(r.get("chapter_thesis") or "").strip(),
                role=(r.get("primary_role") or "").strip(),
                concepts=_uniq([str(x) for x in _as_list(r.get("concepts_introduced_refs"))], 8),
                claims=_uniq(claims, 12),
                qualifications=_uniq([str(x) for x in _as_list(r.get("qualifications_json"))], 4),
                subsections=list(getattr(tc, "subsections", []) or [])[:30],
                excerpt=clean_excerpt(getattr(tc, "text", "") or ""),
            )
        )
    chapters.sort(key=lambda c: (c.number is None, c.number or 0, c.chapter_id))
    _attach_sections(chapters, by_id, markdown)

    sample = " ".join(
        [sub.get("title") or "", markdown[:4000], markdown[len(markdown) // 2 :][:4000]]
    )
    lang = str(sub.get("language") or "").lower()
    language = "zh" if lang.startswith("zh") else detect_language(sample)

    return BookMaterial(
        substrate_id=substrate_id,
        title=sub.get("title") or substrate_id,
        language=language,
        run_id=rid,
        bu_status=bu.get("status") or "",
        genre=bu.get("genre") or "",
        central_theses=_uniq([str(x) for x in _as_list(bu.get("central_theses_json"))]),
        governing_questions=_uniq([str(x) for x in _as_list(bu.get("governing_questions_json"))]),
        concept_defs=concept_defs,
        chapters=chapters,
    )
