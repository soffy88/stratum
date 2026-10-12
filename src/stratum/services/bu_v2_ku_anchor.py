"""Frozen-KU reader for BU2 — task B (KU anchoring).

The A-warehouse ``book_freeze`` pipeline (``a_repository/book_freeze.py``) turns
a book into frozen knowledge units: a Definition, Theorem, Example or Exercise
becomes a ``knowledge_unit`` row with a ``ku_occurrence`` carrying the verbatim
quote and a ``char:START-END (chapter)`` locator.

BU2 previously ignored those entirely and asked a model to invent a concept list
from the chapter text, which is why a 40-concept chapter yielded 3-5 concepts and
why a core theorem like Taylor's could go missing. This reader makes the frozen
KUs available to the producer as a *must-cover* list, so the deterministic
skeleton (952 KUs for Thomas) anchors the LLM semantic layer.

Chapter attribution: ``knowledge_unit`` has no chapter column. The chapter label
lives in two places, both parenthetical to the locator:
  * ``ku_occurrence.locator`` = ``char:468618-470118 (1 1. Functions)``
  * ``reading_evidence.location`` = ``{"start","end","chapter"}``
The occurrence locator is what this reader parses, and it is matched to a BU2
chapter by the chapter's leading number when one is present, else by a title
substring. A KU whose chapter cannot be matched to a BU2 chapter is still
returned under ``unmatched`` so a caller can see the gap rather than lose it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Roles the BU2 concept layer treats as must-cover. Examples and exercises are
# evidence, not concepts, so they are read but not forced into the concept list.
CONCEPT_ROLES = ("DEFINITION", "THEOREM")
ALL_ROLES = ("DEFINITION", "THEOREM", "EXAMPLE", "EXERCISE", "SUMMARY", "ASIDE", "OTHER")

_LOCATOR_CH = re.compile(r"char:(\d+)-(\d+)")
_LOCATOR_CHAPTER = re.compile(r"\((.*)\)\s*$")
# A leading chapter number in the label: "1 1. Functions", "第3章 ...", "12 ...".
_LEADING_NUM = re.compile(r"^\s*(?:第)?\s*(\d{1,3})\s*(?:章|\.|\s)")


@dataclass
class FrozenKU:
    """One frozen knowledge unit as BU2 needs it."""

    ku_id: str
    role: str
    title: str
    statement: str
    quote: str
    locator: str
    chapter_label: str
    start: int = 0
    end: int = 0

    @property
    def name(self) -> str:
        """The label the concept layer should use.

        The frozen title is often ``THEOREM 1（Limit Laws）`` or bare
        ``DEFINITION``. Prefer the parenthetical name; else strip the leading
        kind/number token and take the first short clause of the statement.
        """
        return _concept_name(self.title, self.statement, self.role)

    def to_anchor(self) -> dict[str, Any]:
        """The dict the producer's ``set_ku_anchor`` consumes."""
        return {
            "name": self.name,
            "title": self.title,
            "ku_id": self.ku_id,
            "kind": self.role,
            "quote": self.quote,
            "locator": self.locator,
            "chapter": self.chapter_label,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class ChapterKUIndex:
    """Frozen KUs grouped by the BU2 chapter id they belong to."""

    by_chapter: dict[str, list[FrozenKU]] = field(default_factory=dict)
    unmatched: list[FrozenKU] = field(default_factory=list)
    source_version_id: str = ""
    total: int = 0

    def anchors_for(self, chapter_id: str) -> list[dict[str, Any]]:
        """Must-cover anchor dicts for a chapter, DEF/THM first."""
        kus = self.by_chapter.get(chapter_id, [])
        ordered = sorted(kus, key=lambda k: (k.role not in CONCEPT_ROLES, k.role, k.start))
        return [k.to_anchor() for k in ordered]

    def concept_anchors_for(self, chapter_id: str) -> list[dict[str, Any]]:
        """Only the DEF/THM anchors — the concept/definition coverage floor."""
        kus = [k for k in self.by_chapter.get(chapter_id, []) if k.role in CONCEPT_ROLES]
        return [k.to_anchor() for k in sorted(kus, key=lambda k: (k.role, k.start))]

    def coverage(self, chapter_id: str) -> float:
        """Fraction of DEF/THM KUs the chapter is expected to cover (always 1.0).

        Present so the P13 gate can compare an *achieved* ratio against the
        expectation in one place rather than recomputing the denominator.
        """
        return 1.0 if self.concept_anchors_for(chapter_id) else 0.0

    def expected_defthm(self, chapter_id: str) -> int:
        return len(self.concept_anchors_for(chapter_id))


class FrozenKUReader:
    """Read frozen KUs for a substrate and index them by BU2 chapter."""

    def __init__(self, *, connection: Any | None = None):
        self._conn = connection

    # ── DB access ──────────────────────────────────────────────────────────

    def _query(self, sql: str, params: dict) -> list[dict]:
        if self._conn is not None:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [c[0] for c in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        from stratum.db import query

        return query(sql, params, limit=100000)

    def source_version_for(self, substrate_id: str) -> str | None:
        """The newest frozen source_version for a substrate, if any."""
        rows = self._query(
            "SELECT sv.id AS sv FROM stratum.source_version sv "
            "JOIN stratum.knowledge_unit ku ON ku.source_version_id = sv.id "
            "WHERE sv.book_source_id = %(s)s "
            "GROUP BY sv.id ORDER BY count(ku.id) DESC LIMIT 1",
            {"s": substrate_id},
        )
        return rows[0]["sv"] if rows else None

    def read_units(self, substrate_id: str) -> tuple[str, list[FrozenKU]]:
        """All frozen KUs for a substrate, with their occurrence locator/quote."""
        sv = self.source_version_for(substrate_id)
        if not sv:
            return "", []
        rows = self._query(
            "SELECT ku.id AS ku_id, ku.title, ku.statement, "
            "       o.role, o.quote_span, o.locator "
            "FROM stratum.knowledge_unit ku "
            "LEFT JOIN stratum.ku_occurrence o ON o.unit_id = ku.id "
            "WHERE ku.source_version_id = %(sv)s AND ku.freeze_status = 'FROZEN' "
            "ORDER BY o.role, ku.id",
            {"sv": sv},
        )
        units: list[FrozenKU] = []
        for r in rows:
            locator = r.get("locator") or ""
            start, end = _parse_char_range(locator)
            label = _parse_chapter_label(locator)
            units.append(
                FrozenKU(
                    ku_id=r["ku_id"],
                    role=(r.get("role") or "OTHER").upper(),
                    title=(r.get("title") or "").strip(),
                    statement=(r.get("statement") or "").strip(),
                    quote=(r.get("quote_span") or "").strip(),
                    locator=locator,
                    chapter_label=label,
                    start=start,
                    end=end,
                )
            )
        return sv, units

    # ── indexing ───────────────────────────────────────────────────────────

    def index_for_chapters(
        self, substrate_id: str, chapters: list[tuple[str, str]]
    ) -> ChapterKUIndex:
        """Index frozen KUs by BU2 chapter id.

        ``chapters`` is ``[(chapter_id, title), ...]`` in document order. A KU's
        chapter label is matched by leading number first (robust to bilingual
        titles), then by a distinctive title substring.
        """
        sv, units = self.read_units(substrate_id)
        index = ChapterKUIndex(source_version_id=sv, total=len(units))
        if not units:
            return index

        # Map: chapter number -> chapter_id (from "ch3"), and title -> chapter_id.
        # Only a numbered ``chN`` id contributes to num_to_id. A back-matter id
        # like "bm1" also contains a digit, and taking it as number 1 made the
        # answer appendix claim chapter 1's frozen KUs.
        num_to_id: dict[int, str] = {}
        title_to_id: dict[str, str] = {}
        for cid, title in chapters:
            m = re.fullmatch(r"ch(\d+)", cid or "")
            if m:
                num_to_id[int(m.group(1))] = cid
            if title:
                title_to_id[_norm(title)] = cid

        for ku in units:
            cid = _match_chapter(ku.chapter_label, num_to_id, title_to_id)
            if cid is None:
                index.unmatched.append(ku)
            else:
                index.by_chapter.setdefault(cid, []).append(ku)
        return index


# ── helpers ──────────────────────────────────────────────────────────────────


def _parse_char_range(locator: str) -> tuple[int, int]:
    m = _LOCATOR_CH.search(locator or "")
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2))


def _parse_chapter_label(locator: str) -> str:
    m = _LOCATOR_CHAPTER.search((locator or "").strip())
    return m.group(1).strip() if m else ""


def _leading_int(s: str) -> int | None:
    m = _LEADING_NUM.match(s or "")
    if m:
        return int(m.group(1))
    d = "".join(ch for ch in (s or "") if ch.isdigit())
    return int(d) if d else None


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _concept_name(title: str, statement: str, role: str) -> str:
    """Derive a human concept label from frozen KU fields."""
    t = (title or "").strip()
    # "THEOREM 1（Limit Laws）" -> "Limit Laws"
    m = re.search(r"[（(]\s*(.+?)\s*[）)]\s*$", t)
    if m and len(m.group(1).strip()) > 1:
        return m.group(1).strip()
    # "THEOREM 8—Properties of Continuous Functions" -> take after the dash.
    if "—" in t or " - " in t:
        after = re.split(r"[—-]", t, maxsplit=1)[1].strip()
        if after and after.lower() != role.lower():
            return after
    # Bare "DEFINITION"/"THEOREM N": fall back to the statement's first clause.
    s = (statement or "").strip()
    if s:
        # Drop the leading "THEOREM N" / "DEFINITION" marker.
        s = re.sub(
            r"^(THEOREM|DEFINITION|LEMMA|COROLLARY|PROPOSITION)\s*\S*\s*[-—]?\s*", "", s, flags=re.I
        )
        # The key term is usually the bolded phrase ("A **function** ƒ ...").
        bold = re.search(r"\*\*([^*]{2,60})\*\*", s)
        if bold:
            term = re.sub(r"\s+", " ", bold.group(1)).strip()
            if len(term) >= 3:
                return term
        # Otherwise the first sentence/phrase, trimmed of markup.
        clause = re.split(r"[.\n]", s, maxsplit=1)[0].strip()
        clause = re.sub(r"<[^>]+>", "", clause)
        clause = re.sub(r"\s+", " ", clause).strip()
        if len(clause) >= 3:
            return clause[:160]
    return t or role


def _match_chapter(
    label: str, num_to_id: dict[int, str], title_to_id: dict[str, str]
) -> str | None:
    if not label:
        return None
    n = _leading_int(label)
    if n is not None and n in num_to_id:
        return num_to_id[n]
    # Title substring match: "1. Functions" -> "functions".
    norm = _norm(label)
    # Strip a leading number token so "1functions" matches a "functions" title.
    if n is not None:
        norm = norm[len(str(n)) :]
    for title_norm, cid in title_to_id.items():
        if len(norm) >= 4 and (norm in title_norm or title_norm in norm):
            return cid
    return None
