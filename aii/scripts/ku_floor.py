"""Absolute KU floor shared by the quality gate, econ discovery and the econ batch skip check.

★2026-10-14: econ_zh_d2132c37af (好好赚钱, 11 chapters) "passed" the quality gate with 4 KUs
from 1 chapter, because the density check only counts chapters that already have KUs
(expected = max(8, 1 x 10) -> 4/10 = 40% > 35%), and discovery/batch then treated any book
with registration + BU + >=1 KU as finished. A book whose chapters mostly failed (LLM outage)
was frozen as complete with almost nothing in it.

The floor is deliberately loose (it only catches near-empty books, not long-tail ones):
  * at least one chapter must carry KUs
  * total KUs >= QGATE_MIN_KU (8; misc books QGATE_MISC_MIN_KU = 3)
  * KU-bearing chapters >= QGATE_MIN_CH_COVERAGE (30%) of the book's chapters, when the
    book's chapter count is known
Every reason starts with "KU密度不足: 实抽N" so flywheel_retry_quarantined.py's existing
patterns classify it as retryable.
"""

from __future__ import annotations

import os


def _f(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def min_ku(is_misc: bool = False) -> int:
    return int(_f("QGATE_MISC_MIN_KU", "3") if is_misc else _f("QGATE_MIN_KU", "8"))


def min_ch_coverage() -> float:
    return _f("QGATE_MIN_CH_COVERAGE", "0.3")


def thin_reason(
    ku_total: int,
    ku_chapters: int,
    book_chapters: int | None = None,
    *,
    is_misc: bool = False,
) -> str | None:
    """Return why a book is below the absolute KU floor, or None when it clears it."""
    ku_total = int(ku_total or 0)
    ku_chapters = int(ku_chapters or 0)
    if ku_total <= 0:
        return "KU密度不足: 实抽0仅0%(无KU)"
    if ku_chapters <= 0:
        return f"KU密度不足: 实抽{ku_total}但0章有KU(章节全部失败/无章节出处)"
    floor = min_ku(is_misc)
    if ku_total < floor:
        return f"KU密度不足: 实抽{ku_total}<绝对下限{floor}(覆盖{ku_chapters}章)"
    if book_chapters and book_chapters > 0:
        cov = ku_chapters / book_chapters
        need = min_ch_coverage()
        if cov < need:
            return (
                f"KU密度不足: 实抽{ku_total}仅覆盖{ku_chapters}/{book_chapters}章"
                f"({cov:.0%}<{need:.0%})"
            )
    return None
