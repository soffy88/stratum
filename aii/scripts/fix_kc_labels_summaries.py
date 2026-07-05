"""按章KC摘要: 程序化生成(0 LLM), 取代原LLM版本.
原版靠 DeepSeek 看"KU标题堆砌"瞎猜摘要, 且 .env 路径写死指向已不存在的旧项目路径
(/home/soffy/projects/AII), KEY 恒为 None → 调用全部静默失败(日志"双语摘要: 0/9"),
summary 从未被真正覆盖, 一直停留在 persist_chapter_kc.py 写的占位符.

改用该章 KU 关联的高频概念(materialize_links.py 确定性抽取, 非LLM)拼模板摘要:
更忠实(数据不是脑补)、零API依赖、零延迟、零失败可能。
★不假造双语: concept_onto.name 对中文书存的就是中文(name_zh 从未被填过), 中文书
只产出中文摘要, 不编一份假英文——与"中文原书不假造英文原文"同一原则(见 KU 语言修复)。
"""

import asyncio, asyncpg, json, os, re
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")
MD_FILE = os.getenv("AII_MD_FILE")


def _is_chinese(s: str) -> bool:
    return len(re.findall(r"[一-鿿]", s)) > len(re.findall(r"[A-Za-z]", s))


def _book_lang_zh() -> bool:
    """★读 MD 正文判断全书语言, 不用 KU title——title 层面的判断会被经济学术语污染
    (KU标题常保留英文原词如 "Globalization"/"Comparative advantage", 即使全书是
    中文书, title堆起来中英文字符数会被术语拉平甚至反超, 误判整本书为"英文书".
    实测 econ_zh_da27a19f30(大繁荣, 中文书)踩过: title判断给出 False, 10章有2章
    因此被导向英文分支、中文summary保留旧占位符. 正文绝大部分是叙述性文字, 术语只是
    零星点缀, 判断远比 title 可靠)."""
    if MD_FILE and Path(MD_FILE).exists():
        text = Path(MD_FILE).read_text(encoding="utf-8", errors="replace")[:50000]
        return _is_chinese(text)
    return True  # 无法读原文时兜底: 书库以中文为主, 默认中文更安全(不编假英文)


async def go():
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    kcs = await c.fetch(
        "SELECT kc_id, member_ku_ids FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII章节KC'",
        SUB,
    )
    zh_book = _book_lang_zh()
    n = 0
    for kc in kcs:
        ids = (
            json.loads(kc["member_ku_ids"])
            if isinstance(kc["member_ku_ids"], str)
            else kc["member_ku_ids"]
        )
        if not ids:
            continue
        top = await c.fetch(
            """SELECT cc.name, count(*) d FROM aii.ku_concept_onto kco
               JOIN aii.concept_onto cc ON kco.concept_id = cc.concept_id
               WHERE kco.ku_id = ANY($1::text[])
               GROUP BY cc.concept_id, cc.name ORDER BY d DESC LIMIT 5""",
            ids,
        )
        names = [r["name"] for r in top]
        if not names:
            continue
        if zh_book:
            summary = (
                f"本章围绕{'、'.join(names)}等{len(names)}个核心概念展开，共{len(ids)}个知识单元。"
            )
            summary_en = None  # ★不编假英文
        else:
            summary = None
            summary_en = f"This chapter covers {', '.join(names)} ({len(names)} core concepts, {len(ids)} KUs)."
        await c.execute(
            "UPDATE aii.kc_onto SET summary=COALESCE($2,summary), summary_en=$3 WHERE kc_id=$1",
            kc["kc_id"],
            summary,
            summary_en,
        )
        n += 1
    print(f"程序化摘要(0 LLM): {n}/{len(kcs)}")
    await c.close()


if __name__ == "__main__":
    asyncio.run(go())
