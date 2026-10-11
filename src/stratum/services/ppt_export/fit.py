"""Text measuring and trimming in luobo-ppt's reading units.

luobo-ppt counts one CJK character or one latin word as one unit
(``outline_check.clen``); its layout capacities are expressed in those units.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[A-Za-z0-9][A-Za-z0-9'.\-]*|\s+|.", re.S)
_COUNTED = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]|[A-Za-z0-9]")
_BREAK = set("，。；：、,.;:！？!?）)」』】 ")
_TRAILING = "，、；：,;: -—·"

_LATEX = {
    r"\Delta": "Δ",
    r"\delta": "δ",
    r"\varepsilon": "ε",
    r"\epsilon": "ε",
    r"\alpha": "α",
    r"\beta": "β",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\pi": "π",
    r"\xi": "ξ",
    r"\infty": "∞",
    r"\to": "→",
    r"\rightarrow": "→",
    r"\Rightarrow": "⇒",
    r"\iff": "⇔",
    r"\leq": "≤",
    r"\le": "≤",
    r"\geq": "≥",
    r"\ge": "≥",
    r"\neq": "≠",
    r"\approx": "≈",
    r"\cdot": "·",
    r"\times": "×",
    r"\int": "∫",
    r"\sum": "Σ",
    r"\sqrt": "√",
    r"\lim": "lim",
    r"\sin": "sin",
    r"\cos": "cos",
    r"\tan": "tan",
    r"\ln": "ln",
    r"\log": "log",
    r"\in": "∈",
    r"\partial": "∂",
    r"\prime": "′",
    r"\quad": " ",
    r"\,": " ",
    r"\;": " ",
    r"\left": "",
    r"\right": "",
}
_LATEX_KEYS = sorted(_LATEX, key=len, reverse=True)
_FRAC = re.compile(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}")
_SCRIPT = re.compile(r"([\^_])\{([^{}]*)\}")


def clen(text: str) -> int:
    """Reading units: CJK characters plus latin/number words."""
    count = 0
    for tok in _TOKEN.findall(text or ""):
        if _COUNTED.match(tok):
            count += 1
    return count


def trim(text: str, cap: int) -> str:
    """Cut ``text`` to at most ``cap`` units, preferring a punctuation boundary."""
    text = (text or "").strip()
    if cap <= 0 or clen(text) <= cap:
        return text
    out: list[str] = []
    used = 0
    last_break = -1
    for tok in _TOKEN.findall(text):
        counted = bool(_COUNTED.match(tok))
        if counted and used >= cap:
            break
        out.append(tok)
        if counted:
            used += 1
        if tok in _BREAK or tok.isspace():
            last_break = len(out)
    if last_break > 0 and used and clen("".join(out[:last_break])) >= cap * 0.6:
        out = out[:last_break]
    return "".join(out).rstrip(_TRAILING).strip()


def plain_formula(text: str) -> str:
    """Turn stray LaTeX into the plain-text maths luobo-ppt typesets."""
    s = (text or "").replace("$$", "").replace("$", "")
    for _ in range(4):
        s2 = _SCRIPT.sub(r"\1(\2)", s)
        s2 = _FRAC.sub(r"(\1)/(\2)", s2)
        if s2 == s:
            break
        s = s2
    for key in _LATEX_KEYS:
        s = s.replace(key, _LATEX[key])
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"[ \t]{2,}", " ", s).strip()
