"""KU 验证工作流(P2⑦): LLM 判 KU 对源章节的忠实度 → 落 grade + grounded_by.

补"所有KU永久unverified、grounded_by空"的生命周期缺口. 复用 chapter_synthesize 的源定位.
流程(单 substrate):
  KU.provenance.chapter → 切章 → _find_pos 定位 → 取窗口 → LLM 判
  {SUPPORTED, PARTIAL, UNSUPPORTED, CONTRADICTED}(KU是"讲透综合"非逐字, 看断言是否被源支持)
落库(--apply): grade(SUPPORTED→verified / PARTIAL→moderate / UNSUPPORTED→low / CONTRADICTED→refuted)
  + grounded_by={method:llm_faithfulness, verdict, model, ts}(满足 verified⟹method≠default 约束)

用法: python3 scripts/verify_kus.py <substrate_id> --md <source.md> [--max 20] [--apply]
"""
import asyncio, os, re, json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import asyncpg
from chapter_ingest import slice_chapter
from chapter_synthesize import _find_pos
from aii.api._provider import register_providers
from obase import ProviderRegistry

JUDGE_SYS = ("You verify whether a knowledge unit (KU) is faithful to the source chapter passage. "
             "The KU is a synthesized explanation (not verbatim). Output valid JSON only. "
             "verdict ∈ {SUPPORTED, PARTIAL, UNSUPPORTED, CONTRADICTED}: "
             "SUPPORTED=all key claims grounded in source; PARTIAL=mostly, minor unsupported; "
             "UNSUPPORTED=key claims not found in source; CONTRADICTED=source says otherwise.")
_GRADE = {"SUPPORTED": "verified", "PARTIAL": "moderate", "UNSUPPORTED": "low", "CONTRADICTED": "refuted"}


async def main():
    substrate = sys.argv[1]
    md = sys.argv[sys.argv.index("--md") + 1]
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 20
    apply = "--apply" in sys.argv
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    model = os.getenv("OLLAMA_MODEL") if os.getenv("ECON_LLM_PROVIDER") == "ollama" else "deepseek"
    raw = Path(md).read_text(encoding="utf-8", errors="replace")
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    kus = await conn.fetch("""SELECT ku_id, title, natural_text, provenance FROM aii.ku_onto
        WHERE substrate_id=$1 AND natural_text IS NOT NULL ORDER BY random() LIMIT $2""", substrate, mx)
    print(f"verifying {len(kus)} KUs of {substrate} vs {Path(md).name}", flush=True)

    _chcache: dict[int, str] = {}
    def chtext(n):
        if n not in _chcache:
            _chcache[n] = slice_chapter(raw, n)
        return _chcache[n]

    sem = asyncio.Semaphore(4)
    async def verify(ku):
        async with sem:
            prov = ku["provenance"]
            if isinstance(prov, str):
                try: prov = json.loads(prov)
                except Exception: prov = {}
            ch = (prov or {}).get("chapter")
            if not ch:
                return None
            text = chtext(int(ch))
            pos = _find_pos(text, ku["title"] or "")
            window = text[max(0, pos - 500): pos + 4000] if pos > 0 else text[:6000]
            try:
                r = await llm(messages=[{"role": "user", "content":
                    f"Source passage (Ch{ch}):\n{window[:5000]}\n\n"
                    f"KU to verify:\n{(ku['natural_text'] or '')[:1500]}\n\n"
                    f'JSON: {{"verdict":"..","note":".."}}'}], system=JUDGE_SYS, max_tokens=160)
                t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
                m = re.search(r"\{.*\}", t, re.DOTALL)
                d = json.loads(m.group(0)) if m else {}
            except Exception as e:
                return None
            return {"ku_id": ku["ku_id"], "verdict": (d.get("verdict") or "").upper(), "note": d.get("note", "")}

    res = [r for r in await asyncio.gather(*(verify(k) for k in kus)) if r]
    from collections import Counter
    dist = Counter(r["verdict"] for r in res)
    print("verdicts:", dict(dist))
    upd = 0
    for r in res:
        g = _GRADE.get(r["verdict"])
        if not g:
            continue
        print(f"  {r['verdict']:12}→{g:9} {r['ku_id'][-24:]}  {r['note'][:60]}")
        if apply:
            gb = json.dumps({"method": "llm_faithfulness", "verdict": r["verdict"], "model": model}, ensure_ascii=False)
            await conn.execute("UPDATE aii.ku_onto SET grade=$1, grounded_by=$2::jsonb, updated_at=now() WHERE ku_id=$3",
                               g, gb, r["ku_id"])
            upd += 1
    print(f"\nDONE: verified {len(res)}, graded {upd}" + ("" if apply else " (dry-run)"), flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
