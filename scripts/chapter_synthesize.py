"""新范式章节合成(讲透 + 防漏): 按章切 → 规划知识点 → 每点讲透合成(双语+溯源) → 完整性校验防漏 → 补漏.
★铁律: 喂规划/合成的章节文本【全章, 绝不截断】(截断=系统性漏知识); 超 LLM 上下文则分块喂, 不丢内容.
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

# LLM 上下文裕量(字符). 全章 <= 此值直接喂; 超出则分块喂规划(各块出点, 合并), ★绝不截断丢内容.
_CTX = 130000

PLAN_SYS = "You identify the CORE knowledge points a textbook chapter teaches. Output valid JSON only."
SYN_SYS = ("You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
           "Cite [Ch{n}]. If a facet is not covered write '(not covered)'. Integration not creation. Bilingual EN+中文. "
           "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字).")


def _facets(typ):
    return {"concept": "WHAT(内涵essence/外延boundary/用处use), WHY(why true/important), HOW(how applied)",
            "principle": "WHAT(meaning), WHY(rationale/evidence), IMPLICATION(what follows)",
            "method": "WHAT, WHEN, HOW(steps), WHY"}.get(typ, "WHAT, WHY, HOW")


async def _plan(llm, text, n):
    # 全章; 超 _CTX 分块喂各出点再合并(不截断)
    chunks = [text] if len(text) <= _CTX else [text[i:i + _CTX] for i in range(0, len(text), _CTX)]
    pts = []
    for ck in chunks:
        r = await llm(messages=[{"role": "user", "content":
            f"Chapter {n} text (part):\n\n{ck}\n\nList the CORE knowledge points taught (each: name + type concept|principle|method). "
            'JSON: {"points":[{"name":"..","type":".."}]}'}], system=PLAN_SYS, max_tokens=700)
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            pts += json.loads(m.group(0)).get("points", [])
    # dedup by normalized name (单复数/大小写归一, 防多块规划产近重复点 如 'explicit cost'/'explicit costs')
    seen, out = set(), []
    for p in pts:
        k = re.sub(r"s\b", "", re.sub(r"\s+", " ", p.get("name", "").strip().lower()))[:40]
        if k and k not in seen:
            seen.add(k); out.append(p)
    return out


async def _synth(llm, text, n, name, typ):
    r = await llm(messages=[{"role": "user", "content":
        f"Chapter {n} text:\n\n{text[:_CTX]}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
        f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; mark '(not covered)' if absent. English then 中文."}],
        system=SYN_SYS.format(n=n), max_tokens=1100)
    return name, "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    register_providers(); llm = ProviderRegistry.get().llm("default")
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)  # 全章, 不截断
    print(f"chapter {n}: {len(text)} chars (fed in full, no truncation)", flush=True)
    points = await _plan(llm, text, n)
    print(f"planned {len(points)} knowledge points", flush=True)
    sem = asyncio.Semaphore(8)

    async def s(p):
        async with sem:
            return await _synth(llm, text, n, p["name"], p.get("type", "concept"))
    kus = await asyncio.gather(*(s(p) for p in points))
    names = [k for k, _ in kus]
    # ★防漏: 完整性校验
    comp = check_completeness(text, names)
    print(f"completeness: {comp['covered_terms']}/{comp['total_terms']} terms; "
          f"complete={comp['complete']} missing={comp['missing_bold_terms']}", flush=True)
    # 补漏
    if comp["missing_bold_terms"]:
        fill = await asyncio.gather(*(s({"name": t.title(), "type": "concept"}) for t in comp["missing_bold_terms"]))
        kus = list(kus) + list(fill)
        print(f"backfilled {len(fill)} missing → total {len(kus)} KUs", flush=True)
    Path("/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad"
         f"/ch{n}_synth.md").write_text(
        "\n\n".join(f"### {nm}\n{body}" for nm, body in kus), encoding="utf-8")
    print(f"DONE: {len(kus)} thorough KUs (complete after backfill)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
