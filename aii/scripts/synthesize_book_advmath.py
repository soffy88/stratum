"""高级数学经济专用飞轮抽全本: 逐章(全章不截断→规划→讲透→完整性校验→补漏)→ 落库 ku_onto.
克隆自 synthesize_book_llm_v1.py, 只换了两处:
  ① 讲透用 chapter_synthesize_advmath(高中生讲透版 SYN_SYS), 不是默认版.
  ② ★不能遗漏是本频道存在的唯一理由: 任何一章 synth_chapter 抛异常, 原版只打印
    "ch{n} FAILED"然后跳过继续, 最后仍 exit 0——那本书就悄悄漏了一整章却还能通过
    econ_pipeline.sh 的 exit code 判断进下一步。这里改成一章失败=全书失败(exit 1),
    逼着章节重跑/人工看,而不是带着漏章"看起来完成"。
可断点续(每章checkpoint, 已成功的章不重跑)。
"""

import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import asyncpg
import opencc
from chapter_ingest import slice_chapter, SM, chapter_numbers
from chapter_synthesize_advmath import _plan, _synth, _find_pos
from clean_ku import clean, is_empty_shell, is_junk
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from oprim import vector_encode
from obase import ProviderRegistry

_T2S = opencc.OpenCC("t2s")

SUB = os.getenv("SUBSTRATE", "advmath_placeholder")
SC = Path(os.getenv("PIPELINE_CKPT_DIR", "advmath_pipeline/ckpts"))
SC.mkdir(parents=True, exist_ok=True)
CKPT = SC / f"ckpt_{SUB}.json"
_TYPE_MAP = {
    "conceptual": "conceptual",
    "rationale": "rationale",
    "procedural": "procedural",
    "positional": "positional",
    "factual": "factual",
    "concept": "conceptual",
    "principle": "conceptual",
    "method": "procedural",
}
_CJK = re.compile(r"[一-鿿]")


def _split_bilingual(body: str):
    """按行 CJK 分英/中. 返回 (en, zh)."""
    en, zh = [], []
    for line in body.split("\n"):
        (zh if _CJK.search(line) else en).append(line)
    return "\n".join(en).strip(), "\n".join(zh).strip()


async def synth_chapter(llm, n):
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)
    points = await _plan(llm, text, n)
    sem = asyncio.Semaphore(int(os.getenv("AII_SYNTH_CONCURRENCY", "4")))

    async def s(p):
        async with sem:
            _, body = await _synth(
                llm, text, n, p["name"], p.get("type", "concept"), p.get("pos", 0)
            )
            return p, body

    kus = await asyncio.gather(*(s(p) for p in points))
    names = [p["name"] for p, _ in kus]
    comp = check_completeness(text, names)
    if comp["missing_bold_terms"]:
        fill_pts = []
        for t in comp["missing_bold_terms"]:
            pos = _find_pos(text.lower(), t)
            fill_pts.append(
                {"name": t.title(), "type": "concept", "pos": max(0, pos) if pos >= 0 else 0}
            )
        fill = await asyncio.gather(*(s(p) for p in fill_pts))
        kus = list(kus) + list(fill)
        comp = check_completeness(text, [p["name"] for p, _ in kus])
    return text, kus, comp


async def persist(conn, n, kus):
    loop = asyncio.get_event_loop()
    for i, (p, body) in enumerate(kus):
        name = p["name"]
        typ = p.get("type", "conceptual")
        en_raw, zh_raw = _split_bilingual(body)
        en, en_cites = clean(en_raw)
        zh, zh_cites = clean(zh_raw)
        if zh:
            zh = _T2S.convert(zh)  # 繁体→简体(机械转换, 简体输入原样不变)
        if (
            is_empty_shell(zh or en)
            or len(re.findall(r"[一-龥]", zh or "")) < 10
            or is_junk(f"{zh or ''} {en or ''}")
        ):
            continue
        kt = _TYPE_MAP.get(typ, "conceptual")
        is_pos = kt == "positional"
        stance = (p.get("stance_holder") or None) if is_pos else None
        # ★LLM 偶尔标 positional 却不给 stance_holder → 撞 ck_ku_onto_positional_holder
        # 硬约束, 整章 persist 中途炸掉(前面已插的KU真提交, 后面全丢, 还得重跑一次LLM).
        # 降级成 conceptual 而不是让DB拒绝: KU内容本身抽出来了, 只是够不上positional的
        # 元数据要求, 不该因为这个丢整章.
        if is_pos and not stance:
            kt = "conceptual"
            is_pos = False
        opposing = (p.get("opposing") or p.get("opposing_stance") or None) if is_pos else None
        ku_id = f"{SUB}::ch{n}_ku{i}"
        emb = (
            await loop.run_in_executor(
                None, lambda c=(zh or en)[:2000]: vector_encode(texts=[c], provider="default")
            )
        )[0]
        prov = {
            "chapter": n,
            "paradigm": "thorough-synthesis-advmath",
            "marker": "AII综合-讲透(高中生可懂版,不降深度),非原文逐字",
            "type": typ,
            "explains": p.get("explains"),
            "citations": sorted(set(en_cites + zh_cites)),
            "source_lang": "mixed",
        }
        await conn.execute(
            """
            INSERT INTO aii.ku_onto (ku_id, substrate_id, title, natural_text, natural_text_zh,
                knowledge_type, stance_holder, opposing_stance, grade, provenance, embedding)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'unverified',$9,$10)
            ON CONFLICT (ku_id) DO UPDATE SET natural_text=EXCLUDED.natural_text,
                natural_text_zh=EXCLUDED.natural_text_zh, knowledge_type=EXCLUDED.knowledge_type,
                stance_holder=EXCLUDED.stance_holder, opposing_stance=EXCLUDED.opposing_stance,
                provenance=EXCLUDED.provenance, embedding=EXCLUDED.embedding""",
            ku_id,
            SUB,
            name[:200],
            en or zh,
            zh,
            kt,
            stance,
            opposing,
            json.dumps(prov),
            emb,
        )


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    chapters = chapter_numbers(SM.read_text(encoding="utf-8", errors="replace"))
    done = set(json.loads(CKPT.read_text())["done"]) if CKPT.exists() else set()
    print(f"[{SUB}] {len(done)}/{len(chapters)} chapters done; book has {chapters}", flush=True)
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector

    await register_vector(conn)
    failed_chapters = []
    for n in chapters:
        if n in done:
            continue
        try:
            text, kus, comp = await synth_chapter(llm, n)
            await persist(conn, n, kus)
            done.add(n)
            CKPT.write_text(json.dumps({"done": sorted(done)}))
            print(
                f"  ch{n}: {len(kus)} KU persisted; complete={comp['complete']} "
                f"missing={comp['missing_bold_terms']} [{len(done)}/{len(chapters)}]",
                flush=True,
            )
        except Exception as e:
            # ★不像原版 synthesize_book_llm_v1.py 那样打印后继续——这个频道存在的唯一
            # 理由就是"不能遗漏", 一章失败必须让整本书失败退出, 不能悄悄漏一章还算完成.
            print(f"  ch{n} FAILED: {e}", flush=True)
            failed_chapters.append(n)
    total = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    await conn.close()
    print(f"\nDONE: {total} thorough KUs across {len(done)}/{len(chapters)} chapters", flush=True)
    if failed_chapters:
        print(f"FAILED chapters (book incomplete, not passing): {failed_chapters}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
