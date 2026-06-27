"""新范式防漏标准件: 确定性(不靠 LLM)识别章节"应有知识点清单"(小节标题 + 黑体定义术语),
对照抽出的 KU 清单查漏.

★新范式双命门: 不编(fabrication, 靠溯源校验) + 不漏(omission, 靠本校验).
★为何不靠 LLM: LLM 规划/合成会漏(输入截断 / lost-in-the-middle / 规划识别不全).
  本校验用书的【结构信号】兜底, 不依赖 LLM, 抓一切漏(不管什么原因).
★可靠性依赖 Stratum 交付 md 的结构质量(AII-STRATUM-MD-SPEC-001 R1-R5: 规范小节标题 # N.M /
  黑体定义术语 **TERM** 保留). md 烂(术语丢、标题乱)→ 应有清单也可能漏识别 → 见该规格.
★配套铁律: 喂规划/合成的章节文本【绝不截断】(截断=系统性漏知识); 章大 → 分块喂, 不丢内容.
"""
from __future__ import annotations

import re

# 教材结构信号(确定性):小节标题 ## **N.M Title** + 黑体定义术语 **CAPS TERM**(词汇表惯例)
_SECTION = re.compile(r"(?m)^##\s*\*\*\s*(\d+\.\d+)\s+([^*\n]+?)\s*\*?\*?\s*$")
_BOLD_TERM = re.compile(r"\*\*([A-Z][A-Z’'\- ]{3,45})\*\*")
_STOP = {"EXAMPLE", "FALSE", "TRUE", "CHAPTER", "FIGURE", "TABLE", "NOTE", "ECONOMIC FALLACY",
         "SOURCE", "PART", "EXAMPLES"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower()).rstrip("s")


def _is_spaced_noise(t: str) -> bool:
    """剔除跑页眉间隔字母噪声 'C H A P T E R'(R9): 单字符 token 占多数."""
    toks = t.split()
    return len(toks) >= 4 and sum(1 for x in toks if len(x) == 1) >= len(toks) - 1


# 中文数学教材结构信号: 第N节 标题 + 定义N/定理N(替代 **TERM**)
_ZH_SECTION = re.compile(r"(?m)^第[一二三四五六七八九十]+节\s+([^\n…]{1,28})")
_MATH_SIGNAL = re.compile(r"定义\s*\d|定理\s*\d")
_ZH_SPLIT = re.compile(r"[与和、，及的]")


def _zh_math_should_have(chapter_text: str) -> dict:
    """数学模式: 第N节 标题=知识区(跳页眉重复取首现). 每节标题作 should-have."""
    secs, seen = [], set()
    for m in _ZH_SECTION.finditer(chapter_text):
        t = m.group(1).strip()
        if "…" in t or re.search(r"\d\s*$", t) or t in seen:
            continue
        seen.add(t)
        secs.append(t)
    return {"sections": [{"num": str(i + 1), "title": t, "terms": [t]} for i, t in enumerate(secs)],
            "bold_terms": secs}


def identify_should_have(chapter_text: str) -> dict:
    """确定性识别章节应有知识点: 黑体定义术语(权威)+ 小节(各挂其内黑体术语). 不调 LLM.
    ★数学书无 **TERM** 但有 定义N/定理N → 转数学模式(第N节 标题作 should-have)."""
    # 黑体术语 + 位置
    # ★数学书: 无 **TERM** 黑体但有 定义/定理 → 数学模式(第N节)
    if not _BOLD_TERM.search(chapter_text) and _MATH_SIGNAL.search(chapter_text):
        return _zh_math_should_have(chapter_text)
    term_pos: list[tuple[int, str]] = []
    seen = set()
    for m in _BOLD_TERM.finditer(chapter_text):
        t = m.group(1).strip()
        if t in seen or _is_spaced_noise(t):
            continue
        if any(t == s or t.startswith(s + " ") for s in _STOP):
            continue
        seen.add(t)
        term_pos.append((m.start(), t))
    terms = [t for _, t in term_pos]
    # 小节 + 起止位置, 各挂落在其区间内的黑体术语
    secs = [(m.start(), m.group(1), m.group(2).strip()) for m in _SECTION.finditer(chapter_text)]
    sections = []
    for i, (pos, num, title) in enumerate(secs):
        end = secs[i + 1][0] if i + 1 < len(secs) else len(chapter_text)
        in_sec = [t for p, t in term_pos if pos <= p < end]
        sections.append({"num": num, "title": title, "terms": in_sec})
    return {"sections": sections, "bold_terms": terms}


def check_completeness(chapter_text: str, extracted_ku_names: list[str]) -> dict:
    """对照抽出的 KU 名查漏. 黑体术语=权威应有清单; 小节漏 iff 其全部黑体术语都漏."""
    sh = identify_should_have(chapter_text)
    blob = " ".join(_norm(n) for n in extracted_ku_names)

    def covered(label: str) -> bool:
        nt = _norm(label)
        if nt and nt in blob:
            return True
        # 中文(无空格): 子概念整体 或 任一 2-字窗 在 blob → 覆盖(模糊主题匹配)
        if re.search(r"[一-鿿]", nt):
            parts = [p for p in _ZH_SPLIT.split(nt) if len(p) >= 2]
            if any(p in blob for p in parts):
                return True
            grams = {nt[i:i + 2] for i in range(len(nt) - 1) if re.match(r"[一-鿿]{2}", nt[i:i + 2])}
            return any(g in blob for g in grams)
        words = [w for w in nt.split() if len(w) > 3]
        return bool(words) and all(w in blob for w in words)

    missing_terms = [t for t in sh["bold_terms"] if not covered(t)]
    missing_sections = [s for s in sh["sections"]
                        if s["terms"] and all(not covered(t) for t in s["terms"])]
    return {
        "should_have": sh,
        "missing_bold_terms": missing_terms,
        "missing_sections": [f"{s['num']} {s['title']}" for s in missing_sections],
        "covered_terms": len(sh["bold_terms"]) - len(missing_terms),
        "total_terms": len(sh["bold_terms"]),
        "complete": not missing_terms,
    }
