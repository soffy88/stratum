"""结构噪声门 — 纯规则(0 LLM)判一段文本是不是"结构噪声"(目录/索引/标题/表格/书本元话语).

★教训(上次靠长度<40漏了43字标题"Supply in the Short Run versus the Long Run"):
  规则按【结构特征】判,不靠长度. 核心信号:正文 KU 是完整句子(以 . / 。 结尾);
  结构噪声不是句子(标题无终止标点 / 索引以页码结尾 / 表格带 | / 书本元话语自指).

is_structural_noise(text) -> reason:str | None   (None = 正文, 留)
strip_toc_index_lines(text) -> text              (分块前剥高置信 TOC/Index 行, 保守只剥页码族)
"""
from __future__ import annotations

import re

_PAGE_REF = re.compile(r',\s*\d+([–\-]\d+)?(\s*,\s*\d+([–\-]\d+)?)*\s*$')      # "..., 218–219, 586–590"
_TRAILING_PAGE = re.compile(r'\s\d{1,4}$')                                     # "Rent-Seeking 95"
_TABLE_FIG = re.compile(r'^(table|figure|fig\.)\s*\d', re.I)                   # "Table 11.4 ..."
_SECTION = re.compile(r'^(\d+(\.\d+)+\s|\d+\.\s|chapter\b|part\s+\d|appendix\b)', re.I)  # "3.4 Sunk Costs" / "CHAPTER 14"
# ★窄化: 只抓"纯书本元话语"(整条在讲书/教学框架), 不抓正文里顺带的章节交叉引用
# (避免误删 "We live in a world of scarcity. As you learned in the previous chapter..." 这种真正文)
_BOOK_META = re.compile(
    r'throughout (the|this) book|we have woven|'
    r'in this (chapter|section),?\s+we(\'ll| will| show| examine| discuss| explore| introduce)', re.I)
_QWORD = re.compile(r'^(what|how|why|when|where|who|which|is|are|does|do|can|should)\b', re.I)
_TERMINAL = ('.', '。', '！', '!', '”', '"', ')', '）')   # 句子/引文/括号收尾 = 正文信号


def is_structural_noise(text: str) -> str | None:
    """返回噪声类型(删)或 None(正文,留). 正文=完整句子(终止标点收尾),不会被误判."""
    t = (text or "").strip()
    if not t:
        return "empty"
    # 高置信结构标记 — 不管长度/标点先判
    # ★不靠 '|' 判表格: 经济学正文含 |E|>1 / |η|=1 绝对值/弹性记号是真 KU(会误删). 表格靠 Table/Figure\d 判.
    if _TABLE_FIG.search(t):
        return "table_figure"
    if _BOOK_META.search(t):
        return "book_meta"
    if _PAGE_REF.search(t):
        return "index_pageref"                         # 以页码列表结尾 = 索引条目

    ends_sentence = t.endswith(_TERMINAL)
    # 问句标题: ?结尾 + 疑问词起 + 短(<70, 排除带答疑的教学长问句) + 句内无句号
    if t.endswith("?") and _QWORD.match(t) and len(t) < 70 and "." not in t[:-1]:
        return "question_heading"
    # 标题: 不是句子(无终止标点) → 按结构特征判, 不靠长度
    if not ends_sentence and not t.endswith("?") and not t.endswith(("：", ":")):
        wc = len(t.split())
        if _SECTION.match(t):
            return "section_heading"                   # "3.4 Sunk Costs" / "CHAPTER 14 ..."
        if t.isupper() and wc <= 16:
            return "allcaps_heading"
        if _TRAILING_PAGE.search(t) and wc <= 16:
            return "toc_pageref"                        # "Government Regulation 109"
        # title-case 裸标题: 首字母大写 + 词数有限 + 无内部句号 + 逗号不多
        # (catch 43字 "Supply in the Short Run versus the Long Run" — 靠"非句子"特征非长度)
        if t[:1].isupper() and wc <= 14 and "." not in t and t.count(",") <= 1:
            return "bare_heading"
    return None


# 分块前剥: 只剥【高置信】TOC/Index 行(页码族/表图), 不剥裸标题(太险, 留给 persist 门).
_STRIP_REASONS = {"index_pageref", "toc_pageref", "table_figure", "table_fragment"}


def strip_toc_index_lines(text: str) -> tuple[str, int]:
    """逐行剥高置信 TOC/Index/表格行(页码族). 保守: 正文段落(完整句)一律保留.
    返回 (剥后文本, 剥掉行数)."""
    kept, dropped = [], 0
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            kept.append(line)
            continue
        # markdown 正文标题(## 开头)若带页码也剥, 否则保留结构
        probe = re.sub(r"^#+\s*|\*+", "", s).strip()    # 去 markdown 标记后判
        reason = is_structural_noise(probe)
        if reason in _STRIP_REASONS:
            dropped += 1
            continue
        kept.append(line)
    return "\n".join(kept), dropped
