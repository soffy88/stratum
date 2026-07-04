"""判断一本 MD 是否"值得走 B 范式程序抽取"(而非"是否数学教材").

背景: math_textbook()(math_convert.py)判的是粗粒度"数学密度/章节结构", 但
B 范式抽取器(math_program_ingest.py)靠 MARK 正则找**带阿拉伯数字编号**的
"定义N/定理N"标记抠陈述. 两者不等价——叙事类数学科普书(数字乾坤/混沌…)数学
密度、章节都够, 却从不写"定理3.2:"这种编号, MARK 一个都命不中, B范式只能
产出 0 KU、白跑一轮. 用真实 MARK 正则精确判断, 而非用密度这类代理指标.

阈值 MIN_MARKS=5: 实测样板书(An_Intro..1403命中/斯图542/Calculus_Vol1 82)
与确认抽不出的科普书(0命中)之间有巨大间隔, 5 是宽松安全线, 不会误伤边缘书.
"""

from __future__ import annotations

import re

MARK = re.compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*"
    r"(Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)"
    r"\s*(\d+(?:\.\d+)*)"
)
_FLIP = re.compile(r"(?m)^(\d+)[ \t]+(定义|定理|引理|推论|命题)(?=[ \t　])")
MIN_MARKS = 5


def mark_count(text: str) -> int:
    """与 math_program_ingest.py 的 MARK 逻辑对齐(含'数字在前'翻转), 计数带编号的定义/定理/例."""
    text = _FLIP.sub(r"\2 \1", text)
    return len(MARK.findall(text))


def is_extractable(text: str) -> tuple[bool, int]:
    n = mark_count(text)
    return n >= MIN_MARKS, n


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    txt = open(path, encoding="utf-8", errors="replace").read()
    ok, n = is_extractable(txt)
    print(f"{'✓可抽' if ok else '✗抽不出(应挪其它)'}  MARK命中={n}  {path}")
