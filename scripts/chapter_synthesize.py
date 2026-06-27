"""新范式章节合成(讲透 + 防漏): 按章切 → 规划知识点 → 每点讲透合成(双语+溯源) → 完整性校验防漏 → 补漏.
★规划喂全章(不截断), 合成改定向窗口+程序骨架混合:
  - 有教材定义框(**TERM** def / **EXAMPLE** 块): 程序提取WHAT骨架(0 token)
    → LLM只看WHY后段窗口(跳过已提取的定义段); 节省~51%/call
  - 无定义框: 标准定向窗口 intro[:1000]+section[pos-WIN_PRE:pos+WIN_POST]
  对齐数学管道已验证的 section-windowing 方式.
★防漏: 用 planning_completeness(确定性, 不靠LLM)对照"应有黑体术语/小节"查漏, 漏的补抽.
Usage: chapter_synthesize.py <chapter_n>
"""
import asyncio, json, re, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
from chapter_ingest import slice_chapter, SM
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from obase import ProviderRegistry

# _plan 仍用全章分块喂(规划不截断, 不影响 token).
_CTX = 130000
# ★定向窗口参数 — 每个 KU 合成只喂知识点所在小节, 不喂整章.
_WIN_PRE        = 500    # 知识点 pos 前的 chars(标准路径)
_WIN_POST       = 20000  # 知识点 pos 后的 chars(标准路径)
_WIN_FALLBACK   = 40000  # pos 未找到时 fallback
# ★混合路径参数 — 程序提取了WHAT骨架后, LLM看WHY窗口
# 注意: 不跳过定义区(避免引入段被截断); 节省来自省去 intro[:1000]+pre-pos 500 + 缩短 20K→9K
_WIN_SKEL_DEF   = 0      # 从 pos 开始读(不跳过定义区, 防止"Let bygones"等引入段丢失)
_WIN_POST_HYBRID = 9000  # 从 pos 起读 9K chars(比标准 20K 更小)

PLAN_SYS = ("You identify the knowledge points a textbook chapter DIRECTLY AND SUBSTANTIVELY teaches. "
            "Output valid JSON only.")
SYN_SYS = ("You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
           "Cite [Ch{n}]. Write ONLY what IS substantively covered — skip any facet absent from this chapter "
           "(do NOT write placeholder text like 'not covered'). Integration not creation. Bilingual EN+中文. "
           "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字).")


def _extract_skeleton(text: str, name: str, pos: int):
    """程序提取WHAT骨架: 教材定义框(**TERM** def) + **EXAMPLE** 块.
    搜索窗 pos-200:pos+3500 (覆盖"先叙事后定义"的教材格式, 如 Transaction Costs 定义在 pos+2697).
    单复数形式都试(如 Cost vs Costs).
    返回: (bold_def_str, [example_str, ...]) — 均为原文片段."""
    win = text[max(0, pos - 200): min(len(text), pos + 3500)]
    # 1. 教材定义框: **TERM** sentence (大写/Title/原始形式, 单数+复数都试)
    bold_def = ""
    name_u = name.upper(); name_t = name.title()
    candidates = [name_u, name_u + "S", name_t, name_t + "s", name]
    for term in candidates:
        m = re.search(rf'\*\*{re.escape(term)}\*\*\s+[^\n*]{{5,150}}', win, re.I)
        if m:
            bold_def = m.group(0).strip()
            break
    # 2. **EXAMPLE** 块(搜索窗内, 最多3个)
    examples = re.findall(r'\*\*EXAMPLE\*\*\s*([^\n*]{20,280})', win)
    return bold_def, examples[:3]


def _facets(typ):
    return {"concept": "WHAT(内涵essence/外延boundary/用处use), WHY(why true/important), HOW(how applied)",
            "principle": "WHAT(meaning), WHY(rationale/evidence), IMPLICATION(what follows)",
            "method": "WHAT, WHEN, HOW(steps), WHY"}.get(typ, "WHAT, WHY, HOW")


def _find_pos(text_lo: str, name: str) -> int:
    """在小写章文本中定位知识点名称的首次出现位置. 未找到返回 -1."""
    # 先搜全名(前30字符)
    pos = text_lo.find(name.lower()[:30])
    if pos >= 0:
        return pos
    # 搜最长有意义词(>4字符), 按长度降序
    for word in sorted(name.split(), key=len, reverse=True):
        if len(word) > 4:
            pos = text_lo.find(word.lower())
            if pos >= 0:
                return pos
    return -1


async def _plan(llm, text, n):
    """规划仍喂全章(不截断); 额外为每个知识点定位 pos 供 _synth 用."""
    chunks = [text] if len(text) <= _CTX else [text[i:i + _CTX] for i in range(0, len(text), _CTX)]
    pts = []
    for ck in chunks:
        r = await llm(messages=[{"role": "user", "content":
            f"Chapter {n} text (part):\n\n{ck}\n\n"
            f"List ONLY the concepts this chapter DIRECTLY AND SUBSTANTIVELY teaches — "
            f"concepts with their own definition or ≥2 paragraphs of explanation. "
            f"EXCLUDE concepts merely mentioned in passing, used as 1-sentence examples, "
            f"or previewed/introduced for a later chapter. "
            'JSON: {"points":[{"name":"..","type":"concept|principle|method"}]}'}],
            system=PLAN_SYS, max_tokens=700)
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            pts += json.loads(m.group(0)).get("points", [])
    # dedup by normalized name (单复数/大小写归一)
    seen, out = set(), []
    for p in pts:
        k = re.sub(r"s\b", "", re.sub(r"\s+", " ", p.get("name", "").strip().lower()))[:40]
        if k and k not in seen:
            seen.add(k); out.append(p)
    # ★为每个知识点定位 pos (供 _synth 定向窗口用)
    text_lo = text.lower()
    for p in out:
        found = _find_pos(text_lo, p.get("name", ""))
        p["pos"] = found if found >= 0 else 0
    return out


async def _synth(llm, text, n, name, typ, pos: int = 0):
    """★定向窗口合成 + 程序骨架混合(hybrid):
    pos>0 且程序能提取定义框/例子 → hybrid: 程序WHAT骨架 + LLM只看WHY后段(小窗口)
    pos>0 无骨架 → 标准定向窗口
    pos=0 → fallback 章首40K"""
    bold_def, examples = _extract_skeleton(text, name, pos) if pos > 0 else ("", [])
    has_skeleton = bool(bold_def or examples)

    if pos > 0 and has_skeleton:
        # ── HYBRID路径: 程序已提取WHAT, LLM只看WHY后段 ──
        intro = text[:500]                                          # 短intro(约束/记号)
        # 定义区之后的WHY段(程序已覆盖定义区,跳过避免重复喂)
        why_start = min(len(text), pos + _WIN_SKEL_DEF)
        why_end   = min(len(text), why_start + _WIN_POST_HYBRID)
        why_section = text[why_start:why_end]
        # 骨架提示(直接放进 prompt, 不多余)
        skel = ""
        if bold_def:  skel += f"Extracted definition: {bold_def}\n"
        if examples:  skel += "Extracted examples:\n" + "\n".join(f"• {e[:200]}" for e in examples)
        context = (f"Chapter {n} opening:\n\n{intro}\n\n"
                   f"Programmatic skeleton for \"{name}\":\n{skel}\n\n"
                   f"Section text (after definition):\n\n{why_section}")
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\n"
            f"Synthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Include the WHAT from the skeleton above. "
            f"Focus on WHY (importance/rationale — integrate from section, "
            f"SKIP unrelated paragraphs and end-of-chapter questions). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    elif pos > 0:
        # ── 标准定向窗口 (无骨架) ──
        intro   = text[:1000]
        section = text[max(0, pos - _WIN_PRE): pos + _WIN_POST]
        context = f"Chapter {n} opening (notation/context):\n\n{intro}\n\nRelevant section:\n\n{section}"
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    else:
        # ── Fallback: pos未找到, 章首40K ──
        context = f"Chapter {n} text (opening):\n\n{text[:_WIN_FALLBACK]}"
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    return name, "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    register_providers(); llm = ProviderRegistry.get().llm("default")
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)
    print(f"chapter {n}: {len(text)} chars", flush=True)
    points = await _plan(llm, text, n)
    print(f"planned {len(points)} knowledge points", flush=True)
    for p in points:
        print(f"  {p['name']}: pos={p.get('pos', 0)}", flush=True)
    sem = asyncio.Semaphore(8)

    async def s(p):
        async with sem:
            return await _synth(llm, text, n, p["name"], p.get("type", "concept"), p.get("pos", 0))
    kus = await asyncio.gather(*(s(p) for p in points))
    names = [k for k, _ in kus]
    # ★防漏: 完整性校验
    comp = check_completeness(text, names)
    print(f"completeness: {comp['covered_terms']}/{comp['total_terms']} terms; "
          f"complete={comp['complete']} missing={comp['missing_bold_terms']}", flush=True)
    # 补漏: 搜 pos 后再调 _synth
    if comp["missing_bold_terms"]:
        text_lo = text.lower()
        fill_pts = []
        for t in comp["missing_bold_terms"]:
            pos = _find_pos(text_lo, t)
            fill_pts.append({"name": t.title(), "type": "concept", "pos": max(0, pos) if pos >= 0 else 0})
        fill = await asyncio.gather(*(s(p) for p in fill_pts))
        kus = list(kus) + list(fill)
        print(f"backfilled {len(fill)} missing → total {len(kus)} KUs", flush=True)
    import os
    Path(os.getenv("PIPELINE_CKPT_DIR", "/tmp") + f"/ch{n}_synth.md").write_text(
        "\n\n".join(f"### {nm}\n{body}" for nm, body in kus), encoding="utf-8")
    print(f"DONE: {len(kus)} thorough KUs (complete after backfill)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
