"""新范式章节合成(讲透 + 防漏): 按章切 → 规划知识点 → 每点讲透合成(双语+溯源) → 完整性校验防漏 → 补漏.
★规划喂全章(不截断), 合成改定向窗口: intro[:1000] + section[pos-WIN_PRE:pos+WIN_POST].
  对齐数学管道已验证的 section-windowing 方式, 削减 ~78% _synth input token.
  窗口够覆盖: WIN_POST=20000 chars ≈ 3-4x 知识点平均展开长度; pos 找不到则 fallback 40K.
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
_WIN_PRE      = 500    # 知识点 pos 前的 chars(捕获定义/段落引入)
_WIN_POST     = 20000  # 知识点 pos 后的 chars(覆盖完整展开; 经济教材典型KU展开 3-8K chars)
_WIN_FALLBACK = 40000  # pos 未找到时的 fallback 窗口大小(章首)

PLAN_SYS = ("You identify the knowledge points a textbook chapter DIRECTLY AND SUBSTANTIVELY teaches. "
            "Output valid JSON only.")
SYN_SYS = ("You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
           "Cite [Ch{n}]. Write ONLY what IS substantively covered — skip any facet absent from this chapter "
           "(do NOT write placeholder text like 'not covered'). Integration not creation. Bilingual EN+中文. "
           "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字).")


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
    """★定向窗口合成: intro[:1000] + section[pos-WIN_PRE:pos+WIN_POST].
    pos 未找到(=0且非章首): fallback 到章首 40K chars."""
    if pos > 0:
        intro   = text[:1000]                                      # 章首记号/约定上下文
        section = text[max(0, pos - _WIN_PRE): pos + _WIN_POST]   # 定向窗口
        context = f"Chapter {n} opening (notation/context):\n\n{intro}\n\nRelevant section:\n\n{section}"
    else:
        # pos 未定位: 用章首 fallback(覆盖最密集的引入段落)
        context = f"Chapter {n} text (opening):\n\n{text[:_WIN_FALLBACK]}"
    r = await llm(messages=[{"role": "user", "content":
        f"{context}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
        f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets (do not write 'not covered'). English then 中文."}],
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
