"""去重同章近重复KU(单复数/大小写, 如 Engel's curve×2、Prisoners' dilemma×2)+级联清边/链接."""
import asyncio, asyncpg, os, re
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv; load_dotenv(Path(__file__).resolve().parents[1]/"aii"/".env",override=True)
SUB='microecon_en_full_v2'
def norm(t):
    t=re.sub(r'\([^)]*\)','',t).lower().strip(); t=re.sub(r"[^a-z0-9\s]",'',t); return re.sub(r's\b','',re.sub(r'\s+',' ',t).strip())
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows=await c.fetch(f"SELECT ku_id,title,(provenance->>'chapter')::int ch FROM aii.ku_onto WHERE substrate_id='{SUB}' ORDER BY ku_id")
    grp=defaultdict(list)
    for r in rows: grp[(r['ch'],norm(r['title']))].append(r['ku_id'])
    d=0
    for k,v in grp.items():
        for kid in v[1:]:
            for t in ['ku_concept_onto','concept_readout_edge','ku_internal_logic','ku_logic_structure','ku_onto']:
                await c.execute(f"DELETE FROM aii.{t} WHERE ku_id=$1",kid)
            d+=1
    print(f"deduped {d}")
    await c.close()
asyncio.run(go())
