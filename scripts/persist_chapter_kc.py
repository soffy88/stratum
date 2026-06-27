"""按章KC入 kc_onto(synthesis_marker='AII章节KC'). 通用: 章标题取自md(第N章 或 # Chapter)."""
import asyncio, asyncpg, os, json, re, sys
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
from chapter_ingest import SM, chapter_starts
SUB = os.getenv('SUBSTRATE', 'microecon_en_full_v2')


_CNM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _titles(text):
    out = {}
    # 英文 # Chapter N: Title
    for n, pos in chapter_starts(text).items():
        nl = text.find('\n', pos)
        line = text[pos: nl if nl > 0 else pos + 50]
        if re.search(r'[一-鿿]', line):
            continue
        out[n] = f"Ch{n}: {re.sub(r'^#\\s*Chapter\\s*\\d+:\\s*', '', line).strip()[:40]}"
    # 中文 第N章 <非空标题>(跳页眉重复的裸"第N章"+TOC页码)→ 取每章首个带标题
    if not out:
        for m in re.finditer(r'第([一二三四五六七八九十]+)章\s+([^\n…\d]{2,30})', text):
            n = _CNM.get(m.group(1))
            t = m.group(2).strip()
            if n and t and n not in out:
                out[n] = f"第{n}章·{t}"
    return out


async def go():
    c = await asyncpg.connect(os.getenv('DATABASE_URL'))
    titles = _titles(SM.read_text(encoding='utf-8', errors='replace'))
    kus = await c.fetch(f"SELECT ku_id,(provenance->>'chapter')::int ch FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    byc = defaultdict(list)
    for k in kus:
        byc[k['ch']].append(k['ku_id'])
    await c.execute("DELETE FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII章节KC'", SUB)
    for ch in sorted(byc):
        await c.execute("""INSERT INTO aii.kc_onto(substrate_id,level,community_label,summary,member_ku_ids,synthesis_marker)
            VALUES($1,$2,$3,$4,$5,'AII章节KC')""", SUB, ch, titles.get(ch, f"第{ch}章"),
            f"第{ch}章的知识单元", json.dumps(byc[ch]))
    print(f"chapter KC: {len(byc)} 入 kc_onto")
    await c.close()
asyncio.run(go())
