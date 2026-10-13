"""Concept-label noise filter shared by the graph enricher and the learning guide.

Frozen KU anchors include worked examples, exercise headers and extraction
fragments ("EXAMPLE 4 Show that ...", "习题1-6（第50页）", "(a) Vertical:",
"= _xy_"). They are evidence, not concepts, and must not become concept nodes
or learning-guide steps.
"""

from __future__ import annotations

import re

NON_CONCEPT_KINDS = frozenset(
    {"EXAMPLE", "EXERCISE", "EXERCISES", "PROBLEM", "SOLUTION", "NOTE", "REMARK", "FIGURE", "TABLE"}
)

_NOISE_PATTERNS = [
    re.compile(r"^(example|exercises?|solution|problem|caution|figure|table|summary)\b", re.I),
    re.compile(r"^(例|习题|总习题|练习|解|证明|图|表)\s*[\d一二三四五六七八九十]"),
    re.compile(r"^(总习题|复习题)"),
    re.compile(r"^\(?[a-zA-Z]\)"),  # (a) ... / a) ...
    re.compile(r"^\(?\d+[.)]"),  # 21. / (3)
    re.compile(r"^[=+\-*/<>,:;.\\]"),  # formula fragments
    re.compile(r"^\(\s*[_\\$]"),  # "( _t_ ) = ..."
]

_FRAGMENT_PATTERNS = [
    re.compile(r"\*\*|\s_\w"),  # leftover markdown / math italics
    re.compile(r"^(is|are|was|were|of|and|or|if|then|when|where|which|that)\b", re.I),
    re.compile(r"\b(of|at|to|for|with|in|by|from|and|or|the|is|are)\s*[:,]?$", re.I),
]

_NUMBERED_ZH = re.compile(r"^(?:定理|定义|推论|引理|性质)\s*\d+'?\s*(.*)$")
_STATEMENT_OPENERS = ("设", "如果", "若", "就是说", "不难", "也", "是", "的", ":", "：")

_WORDISH = re.compile(r"[A-Za-z]{2,}|[\u4e00-\u9fff]")


def is_noise_concept(label: str, kind: str = "") -> bool:
    """True when ``label`` (with KU ``kind``) is not a learnable concept."""
    text = (label or "").strip()
    if (kind or "").upper() in NON_CONCEPT_KINDS:
        return True
    if not text or not _WORDISH.search(text):
        return True
    if any(p.search(text) for p in _NOISE_PATTERNS):
        return True
    if any(p.search(text) for p in _FRAGMENT_PATTERNS):
        return True
    # Unnamed numbered statements ("定理1 设 \\(f(x)\\) ...", "定义 2 如果 ...")
    # are the statement body, not a concept name.
    numbered = _NUMBERED_ZH.match(text)
    if numbered:
        rest = numbered.group(1).strip()
        if (
            not rest
            or "\\(" in text
            or "$" in text
            or rest.startswith(_STATEMENT_OPENERS)
            or len(text) > 30
        ):
            return True
    # English sentences ("All the Limit Laws in Theorem 1 are true when ...")
    # are statements, not concept names.
    return not re.search(r"[\u4e00-\u9fff]", text) and len(text.split()) > 8


def display_label(label: str, max_chars: int = 48) -> str:
    """Shorten a statement-style label ("定理 2 如果函数 ...") for display."""
    text = " ".join((label or "").split())
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"
