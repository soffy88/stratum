"""新范式抽全本: 逐章(全章不截断→规划→讲透→完整性校验→补漏)→ 落库 ku_onto. 可断点续(每章checkpoint).
落库: 每讲透KU一行(title/natural_text=EN/natural_text_zh=中文/knowledge_type/chapter_id/grade/embedding)."""
import asyncio, json, os, re, sys
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import asyncpg
from chapter_ingest import slice_chapter, SM
from chapter_synthesize import _plan, _synth, _CTX
from clean_ku import clean, is_empty_shell
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from oprim import vector_encode
from obase import ProviderRegistry

SUB = "microecon_en_full_v2"
SC = Path("/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad")
CKPT = SC / f"ckpt_{SUB}.json"
_TYPE_MAP = {"concept": "conceptual", "principle": "rationale", "method": "procedural"}
_CJK = re.compile(r"[一-鿿]")


def _split_bilingual(body: str):
    """按行 CJK 分英/中. 返回 (en, zh)."""
    en, zh = [], []
    for line in body.split("\n"):
        (zh if _CJK.search(line) else en).append(line)
    return "\n".join(en).strip(), "\n".join(zh).strip()


async def synth_chapter(llm, n):
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)  # 全章不截断
    points = await _plan(llm, text, n)
    sem = asyncio.Semaphore(8)

    async def s(name, typ):
        async with sem:
            _, body = await _synth(llm, text, n, name, typ)
            return name, typ, body
    kus = await asyncio.gather(*(s(p["name"], p.get("type", "concept")) for p in points))
    names = [k for k, _, _ in kus]
    comp = check_completeness(text, names)
    if comp["missing_bold_terms"]:
        fill = await asyncio.gather(*(s(t.title(), "concept") for t in comp["missing_bold_terms"]))
        kus = list(kus) + list(fill)
        comp = check_completeness(text, [k for k, _, _ in kus])
    return text, kus, comp


async def persist(conn, n, kus):
    loop = asyncio.get_event_loop()
    for i, (name, typ, body) in enumerate(kus):
        en_raw, zh_raw = _split_bilingual(body)
        # ★清洗呈现: 去脚手架/markdown/(未涉及); 来源标注剥到 provenance.citations(命门不丢)
        en, en_cites = clean(en_raw)
        zh, zh_cites = clean(zh_raw)
        if is_empty_shell(zh or en):     # 全空壳(书没讲)→ 不入库
            continue
        kt = _TYPE_MAP.get(typ, "conceptual")
        emb = (await loop.run_in_executor(None, lambda c=(zh or en)[:2000]: vector_encode(texts=[c], provider="default")))[0]
        prov = {"chapter": n, "paradigm": "thorough-synthesis", "marker": "AII综合-讲透,非原文逐字",
                "citations": sorted(set(en_cites + zh_cites))}
        await conn.execute("""
            INSERT INTO aii.ku_onto (ku_id, substrate_id, title, natural_text, natural_text_zh,
                knowledge_type, grade, provenance, embedding)
            VALUES ($1,$2,$3,$4,$5,$6,'unverified',$7,$8)
            ON CONFLICT (ku_id) DO UPDATE SET natural_text=EXCLUDED.natural_text,
                natural_text_zh=EXCLUDED.natural_text_zh, knowledge_type=EXCLUDED.knowledge_type,
                provenance=EXCLUDED.provenance, embedding=EXCLUDED.embedding""",
            f"{SUB}::ch{n}_ku{i}", SUB, name[:200], en or zh, zh,
            kt, json.dumps(prov), emb)


async def main():
    register_providers(); llm = ProviderRegistry.get().llm("default")
    done = set(json.loads(CKPT.read_text())["done"]) if CKPT.exists() else set()
    print(f"[{SUB}] {len(done)}/19 chapters already done: {sorted(done)}", flush=True)
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector
    await register_vector(conn)
    for n in range(1, 20):
        if n in done:
            continue
        try:
            text, kus, comp = await synth_chapter(llm, n)
            await persist(conn, n, kus)
            done.add(n)
            CKPT.write_text(json.dumps({"done": sorted(done)}))
            print(f"  ch{n}: {len(kus)} KU persisted; complete={comp['complete']} "
                  f"missing={comp['missing_bold_terms']} [{len(done)}/19]", flush=True)
        except Exception as e:
            print(f"  ch{n} FAILED: {e}", flush=True)
    total = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    await conn.close()
    print(f"\nDONE: {total} thorough KUs across {len(done)} chapters", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
