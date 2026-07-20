"""高级数学经济专用飞轮的章节合成: 复用 chapter_synthesize_llm_v1 的规划/定位逻辑(_plan/_find_pos/_CTX),
只换 SYN_SYS 和 _synth ——这批书(高级微观/代数几何/拓扑/递归宏观理论等)术语密度和抽象程度比
econ_zh/misc 现有书高得多, 用户明确要求: 讲解到一个没有专业背景的高中生能看懂, 但不能降低原书
本身的推导深度/严谨性——这是"加桥梁"不是"简化替换", 现有 SYN_SYS(econ_zh/misc 共用)完全没有
这条要求(那条现役管线 _synth 甚至已经是0LLM程序抠, 根本不改写语言, 见 chapter_synthesize.py)。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import chapter_synthesize_llm_v1 as _base
from chapter_synthesize_llm_v1 import (
    _CTX,
    _WIN_FALLBACK,
    _WIN_POST,
    _WIN_PRE,
    _call_with_retry,
    _facets,
    _find_pos,
    _plan,
)  # noqa: F401

PLAN_SYS = (
    "You identify the knowledge points a textbook chapter DIRECTLY AND SUBSTANTIVELY teaches, "
    "classified by ontological type (conceptual / rationale / procedural / positional / factual). "
    "★FAITHFUL TO THE TEXT: for rationale, give ONLY the causal mechanism/justification the text "
    "actually states — never invent causation the text doesn't say. For positional, mark ONLY genuine "
    "disputes the text presents — never turn a settled result into a 'dispute'. Types reflect what the "
    "book really is — never force a type that isn't there. "
    "This is an advanced graduate-level math/economics text (e.g. advanced microeconomics, algebraic "
    "geometry, topology, recursive macroeconomics) — do not skip a concept just because it looks hard; "
    "if the chapter substantively develops it, list it. Output valid JSON only."
)
# ★_plan() 引用的是它自己模块里的全局 PLAN_SYS/_PLAN_TYPES(不是参数), 要在这里覆盖模块属性
# 才能生效——否则 import 进来的 _plan 会悄悄继续用 chapter_synthesize_llm_v1 自己的默认版本。
# ⚠2026-07-11修复: 之前只覆盖了PLAN_SYS, 漏了_PLAN_TYPES——LLM被_plan()里硬编码的窄枚举
# (concept|principle|method)限死, rationale永远选不到, 而下面_TYPE_MAP明明按五分类写的,
# 导致质量门rationale(why)=0对每本书100%必然报警(见记忆 aii-advmath-flywheel-stuck)。
_base.PLAN_SYS = PLAN_SYS
_base._PLAN_TYPES = "conceptual|rationale|procedural|positional|factual"

SYN_SYS = (
    "You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
    "Cite [Ch{n}]. Write ONLY what IS substantively covered — skip any facet absent from this chapter "
    "(do NOT write placeholder text like 'not covered'). Integration not creation. Bilingual EN+中文. "
    "★ACCESSIBILITY BAR (this book is graduate-level advanced math/economics — harder than default): "
    "for EVERY technical term, notation, or theorem you use, gloss it in plain language a smart "
    "high-schooler with no calculus/no economics background could follow, THEN give the exact rigorous "
    "statement. Do NOT force an analogy or contrived mental image where none fits naturally — a stiff "
    "or forced analogy is worse than none; plain, direct explanation is fine. The plain-language gloss "
    "is an ADDITION, never a replacement: do NOT drop, simplify, water down, or approximate the actual "
    "mathematical content, derivation steps, proof logic, or technical precision of the original. A "
    "reader must come away understanding BOTH the intuition AND the exact rigorous claim — never one "
    "at the expense of the other. "
    "★COMPLETENESS (harder than default): this channel's whole reason to exist is not missing anything — "
    "when a chapter states a theorem, do not silently omit any of its hypotheses/conditions; when it "
    "gives a proof or derivation, keep every step, not just the conclusion. "
    "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字). "
    "★ The 中文 section must be written ENTIRELY in Chinese — no inline English words/phrases mixed into "
    "Chinese sentences (technical notation like Γ(G,S) or [Ch2] is fine; English prose words are not).\n\n"
    "EXAMPLE (this is the bar to hit — study the shape, not the specific words):\n"
    "Bad (definition restated, not what we want):\n"
    '"A determinant is a mathematical operator representing linear relationships between variables, '
    'expressible as a table of rows and columns."\n'
    "Good (plain-language gloss first, then full rigor kept intact):\n"
    '"The determinant of a matrix tells you, in one number, how much a linear transformation scales '
    "area (or volume, in higher dimensions), and whether it flips orientation in the process. For an "
    "n×n matrix A, det(A) is defined recursively by cofactor expansion along any row i: det(A) = Σⱼ "
    "(-1)^(i+j) a_ij M_ij, where M_ij is the (i,j)-minor [Ch3]. This recursive definition is why det(I) "
    "= 1 (no scaling) and det(A)=0 exactly when A collapses space into a lower dimension (some direction "
    'gets squashed to zero volume) [Ch3]."\n'
    "Notice: the good version LOSES NOTHING — the formula, the recursion, the citation are all still "
    "there. It just ALSO tells you plainly what the object means before the symbols land."
)


async def _synth(llm, text, n, name, typ, pos: int = 0):
    """定向窗口合成, 同 chapter_synthesize_llm_v1._synth, 换 SYN_SYS(高中生讲透版)."""
    if pos > 0:
        intro = text[:1000]
        section = text[max(0, pos - _WIN_PRE) : pos + _WIN_POST]
        context = (
            f"Chapter {n} opening (notation/context):\n\n{intro}\n\nRelevant section:\n\n{section}"
        )
    else:
        context = f"Chapter {n} text (opening):\n\n{text[:_WIN_FALLBACK]}"
    r = await _call_with_retry(
        llm,
        messages=[
            {
                "role": "user",
                "content": f'{context}\n\nSynthesize ONE thorough KU for: "{name}" (type={typ}). '
                f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets (do not write 'not covered'). "
                f"Remember the accessibility bar: gloss every term for a smart high-schooler without losing "
                f"any rigor. English then 中文.",
            }
        ],
        system=SYN_SYS.format(n=n),
        max_tokens=3200,  # ★比默认1100高很多: 完整推导+双语讲透都要, 实测1400/2200都还会被截断
    )
    return name, "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
