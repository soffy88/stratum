"""按章KC入 kc_onto(synthesis_marker='AII章节KC'). 通用: 章标题取自md(第N章 或 # Chapter)."""

import asyncio, asyncpg, os, json, re, sys
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
from chapter_ingest import SM, chapter_starts

SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")


def _titles(text):
    """★复用 chapter_starts()(已处理中/英文、阿拉伯/中文数字、目录块识别), 不再自己
    重写一套独立正则去定位章节——旧版中文分支只认汉字数字("第一章"), 现在中文书主流
    用阿拉伯数字("第1章")编号, 旧正则全不命中, 标题退化成空壳"第N章"。"""
    out = {}
    for n, pos in chapter_starts(text).items():
        nl = text.find("\n", pos)
        line = text[pos : nl if nl > 0 else pos + 60].strip()
        is_en = bool(re.match(r"#{0,4}\s*Chapter\s*\d+", line, re.I))
        title = re.sub(
            r"^#{0,4}\s*(?:Chapter\s*\d+:?|第[一二三四五六七八九十百千0-9]+章)\s*[·:：]?\s*",
            "",
            line,
            flags=re.I,
        ).strip()
        if not title and nl > 0:  # 标题另起一行(如"# Chapter 21:\n\nTitle")
            nl2 = text.find("\n", nl + 1)
            title = text[nl + 1 : nl2 if nl2 > 0 else nl + 60].strip()
            # 下一行有时重复了章节标记本身("第2章 系统大观园")→ 再去一次前缀防重复
            title = re.sub(
                r"^#{0,4}\s*(?:Chapter\s*\d+:?|第[一二三四五六七八九十百千0-9]+章)\s*[·:：]?\s*",
                "",
                title,
                flags=re.I,
            ).strip()
        label = f"Ch{n}" if is_en else f"第{n}章"
        out[n] = f"{label}·{title[:40]}" if title else label
    return out


async def go():
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    titles = _titles(SM.read_text(encoding="utf-8", errors="replace"))
    kus = await c.fetch(
        f"SELECT ku_id,(provenance->>'chapter')::int ch FROM aii.ku_onto WHERE substrate_id='{SUB}'"
    )
    byc = defaultdict(list)
    for k in kus:
        byc[k["ch"]].append(k["ku_id"])
    await c.execute(
        "DELETE FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII章节KC'", SUB
    )
    for ch in sorted(byc):
        await c.execute(
            """INSERT INTO aii.kc_onto(substrate_id,level,community_label,summary,member_ku_ids,synthesis_marker)
            VALUES($1,$2,$3,$4,$5,'AII章节KC')""",
            SUB,
            ch,
            titles.get(ch, f"第{ch}章"),
            f"第{ch}章的知识单元",
            json.dumps(byc[ch]),
        )
    print(f"chapter KC: {len(byc)} 入 kc_onto")
    await c.close()


if __name__ == "__main__":
    asyncio.run(go())
