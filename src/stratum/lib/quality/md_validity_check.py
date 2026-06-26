"""md_validity_check — MD 内容有效性（≥500字符视为有效）.

扫描版例外: omodul 已设 scanned/empty/garbled 时跳过，不覆盖。
"""
from __future__ import annotations

MD_MIN_CHARS = 500

_PQ_OMODUL_HANDLED = frozenset(["scanned", "empty", "garbled", "ocr_ok"])


def check_md_validity(
    content: str | None, current_pq: str | None
) -> tuple[bool, str | None]:
    """Return (valid, reason_if_not).

    reason: md_empty | md_too_short
    如果 omodul 已标记 scanned/empty/garbled，直接返回 (True, None) 不干预。
    """
    if current_pq in _PQ_OMODUL_HANDLED:
        return True, None
    if not content:
        return False, "md_empty"
    if len(content) < MD_MIN_CHARS:
        return False, "md_too_short"
    return True, None
