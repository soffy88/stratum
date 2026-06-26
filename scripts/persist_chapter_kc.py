"""把19章作为'按章KC'入 kc_onto(synthesis_marker='AII章节KC'), 与谱社区KC双套并存."""
import asyncio, asyncpg, os, json, re
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv; load_dotenv(Path(__file__).resolve().parents[1]/"aii"/".env", override=True)
SUB='microecon_en_full_v2'
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    SM=Path("/home/soffy/shared/stratum-to-aii/Principles_of_Microeconomics_The_Way_We__01KVAJCX.md").read_text(encoding='utf-8',errors='replace')
    ct={int(m.group(1)):m.group(2).strip() for m in re.finditer(r'(?m)^# Chapter (\d+):\s*(.+)$',SM)}
    kus=await c.fetch(f"SELECT ku_id,(provenance->>'chapter')::int ch FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    byc=defaultdict(list)
    for k in kus: byc[k['ch']].append(k['ku_id'])
    await c.execute("DELETE FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII章节KC'",SUB)
    for ch in sorted(byc):
        await c.execute("""INSERT INTO aii.kc_onto(substrate_id,level,community_label,summary,member_ku_ids,synthesis_marker)
            VALUES($1,$2,$3,$4,$5,'AII章节KC')""",SUB,ch,f"Ch{ch}: {ct.get(ch,'')[:40]}",f"教材第{ch}章的知识单元",json.dumps(byc[ch]))
    print(f"chapter KC: {len(byc)} 入 kc_onto")
    await c.close()
asyncio.run(go())
