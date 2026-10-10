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
import opencc
from chapter_ingest import slice_chapter, SM, chapter_numbers
from chapter_synthesize import _plan, _synth, _CTX, _find_pos
from clean_ku import clean, is_empty_shell, is_junk
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from oprim import vector_encode
from obase import ProviderRegistry

_T2S = opencc.OpenCC("t2s")


def _book_lang(text: str) -> str:
    """判断源书语言: 'en'(英文/非中文占多) / 'zh'(中文, 简繁不拘, 存前统一转简体).
    ★中文原书不需要"英文原文"这回事——_synth 是0LLM程序抠原文, 对中文书抠出来的
    就是中文, 不是翻译. 旧逻辑用 en_or_zh fallback 把中文塞进 natural_text(本该放
    独立英文内容的字段), 前端无条件标"英文原文"产生误导. 按源语言分支: 中文书只
    存一份原文(繁体先转简体, 简体不转不翻译); 英文书维持现状(英文原文+中文翻译)."""
    samp = text[:50000]
    zh = len(re.findall(r"[一-鿿]", samp))
    en = len(re.findall(r"[A-Za-z]", samp))
    return "zh" if zh > en else "en"


BOOK_LANG = _book_lang(SM.read_text(encoding="utf-8", errors="replace"))

SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")
SC = Path(
    os.getenv(
        "PIPELINE_CKPT_DIR",
        "/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad",
    )
)
SC.mkdir(parents=True, exist_ok=True)
CKPT = SC / f"ckpt_{SUB}.json"
# 六类直映射(type 即 knowledge_type); 旧类型 back-compat(principle 是 conceptual·原理, 不是 rationale)
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
    points = await _plan(llm, text, n)  # ★ _plan 含 pos + type + explains/stance(positional)
    sem = asyncio.Semaphore(
        int(os.getenv("AII_SYNTH_CONCURRENCY", "1"))
    )  # ★并发度由飞轮env控制(测3/4/5/6); 默认1=串行

    async def s(p):
        async with sem:
            _, body = await _synth(
                llm, text, n, p["name"], p.get("type", "conceptual"), p.get("pos", 0)
            )
            return p, body  # ★ 返回完整 point 字典 + body(带 explains/stance 透传 persist)

    kus = await asyncio.gather(*(s(p) for p in points))
    names = [p["name"] for p, _ in kus]
    comp = check_completeness(text, names)
    if comp["missing_bold_terms"]:  # 补漏: 黑体术语漏的 → 作 conceptual 点补抽
        fill_pts = []
        for t in comp["missing_bold_terms"]:
            pos = _find_pos(text, t)
            fill_pts.append(
                {"name": t.title(), "type": "conceptual", "pos": max(0, pos) if pos >= 0 else 0}
            )
        fill = await asyncio.gather(*(s(p) for p in fill_pts))
        kus = list(kus) + list(fill)
        comp = check_completeness(text, [p["name"] for p, _ in kus])
    return text, kus, comp


async def persist(conn, n, kus):
    loop = asyncio.get_event_loop()
    # ★双仓: A仓只抽原始KU不建关系. explains 链留在 KU 的 provenance(下方 prov["explains"]),
    #   explains 超边由 B仓 从 provenance 建(关系=B仓). A仓 不写 explains 边.
    for i, (p, body) in enumerate(kus):
        name = p["name"]
        typ = p.get("type", "conceptual")
        if BOOK_LANG == "zh":
            # ★中文原书: body 本就是原文中文(_synth 0LLM程序抠), 不按行拆英/中(那样会把
            # 原文错分成"没有可翻译内容→en空"); 整段当中文清洗, 不产出虚假的"英文原文".
            en_raw, zh_raw = "", body
        else:
            en_raw, zh_raw = _split_bilingual(body)
        # ★清洗呈现: 去脚手架/markdown/(未涉及); 来源标注剥到 provenance.citations(命门不丢)
        en, en_cites = clean(en_raw)
        zh, zh_cites = clean(zh_raw)
        if BOOK_LANG == "zh" and zh:
            zh = _T2S.convert(zh)  # 繁体→简体(机械转换, 简体输入原样不变)
        # 全空壳(书没讲)→ 不入库; 中文<10字也丢弃(对齐质量门空壳判定: 有英文无中文也算空壳)
        # ★LLM 拒答/脚手架泄漏/空 facet 壳(内容窗口空→LLM回道歉)也丢弃, 防垃圾入库
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
            "paradigm": "thorough-synthesis",
            "marker": "AII综合-讲透,非原文逐字",
            "type": typ,
            "explains": p.get("explains"),  # ★溯源记真实六类 + explains指向
            "citations": sorted(set(en_cites + zh_cites)),
            "source_lang": BOOK_LANG,  # ★zh=中文原书(natural_text非独立英文, 前端应显示"原文"不折叠)
        }
        # ★is_positional 是生成列(=knowledge_type='positional'), 不可显式插入; 只写 stance_holder/opposing_stance
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
        # explains 链已写入 prov["explains"](上方) → B仓据此建 explains 超边; A仓不写边.


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    chapters = chapter_numbers(SM.read_text(encoding="utf-8", errors="replace"))  # 实际章数(英/中)
    done = set(json.loads(CKPT.read_text())["done"]) if CKPT.exists() else set()
    print(f"[{SUB}] {len(done)}/{len(chapters)} chapters done; book has {chapters}", flush=True)
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector

    await register_vector(conn)
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
            print(f"  ch{n} FAILED: {e}", flush=True)
    total = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    await conn.close()
    print(f"\nDONE: {total} thorough KUs across {len(done)} chapters", flush=True)
    # ★摄取后钩子: 图变了 → 刷新概念图 + Laplacian(持续). AII_POST_INGEST_REFRESH=1 自动跑, 否则提示.
    if os.getenv("AII_POST_INGEST_REFRESH") == "1":
        import subprocess

        subprocess.run(["bash", str(ROOT / "scripts" / "refresh_graph.sh")])
        print("post-ingest: 概念图 + Laplacian + 谱社区KC 已刷新", flush=True)
    else:
        print(
            "hint: 运行 scripts/refresh_graph.sh 刷新概念图+Laplacian+谱社区KC (持续Laplacian钩子)",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
