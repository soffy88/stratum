"""fragment_detect — 双条件碎片检测.

判定为 fragment 要同时满足:
  1. 标题词命中（扉页/目录/版权页/第X章节等）
  2. MD 内容 < 2000 字符（"第四部分118万字" 不会误判）
"""
from __future__ import annotations

import re

_FRAGMENT_TITLE_EXACT = frozenset([
    "扉页", "目录", "版权页", "作者按", "前言", "序言", "序",
    "后记", "附录", "致谢", "索引", "目次", "版权", "著作权",
    "contents", "preface", "introduction", "table of contents",
])

_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百千\d]+[章节部分篇讲]")

FRAGMENT_CONTENT_MAX = 2000


def is_fragment(title: str | None, md_content: str | None) -> bool:
    """True 当且仅当: 标题是碎片词 AND MD 内容 < 2000 字符."""
    stripped = (title or "").strip()

    title_hit = (
        stripped.lower() in _FRAGMENT_TITLE_EXACT
        or bool(_CHAPTER_RE.match(stripped))
    )
    if not title_hit:
        return False

    return len(md_content or "") < FRAGMENT_CONTENT_MAX
