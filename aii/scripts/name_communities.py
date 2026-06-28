import asyncio, asyncpg, os, json, re, httpx
from collections import defaultdict
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'; KEY=os.getenv('DEEPSEEK_API_KEY')
def norm(t):
    t=re.sub(r'\([^)]*\)','',t).lower().strip(); t=re.sub(r'[^a-z0-9\s/&-]','',t)
    return re.sub(r's\b','',re.sub(r'\s+',' ',t).strip())
SYS=("Given a cluster of economics concepts, output a SHORT theme name + one-line summary in Simplified Chinese. "
     "The theme must be the GENUINE common subject (no 附会). Output JSON {\"label\":\"<≤8字主题>\",\"summary\":\"<一句话>\"}.")
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows=await c.fetch("SELECT community_id,concept_name FROM aii.spectral_community WHERE substrate_id=$1",SUB)
    byc=defaultdict(list)
    for r in rows: byc[r['community_id']].append(r['concept_name'])
    # concept title -> ku_id + degree(for core)
    kus=await c.fetch(f"SELECT ku_id,title FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    t2ku={}; 
    for k in kus: t2ku.setdefault(norm(k['title']),k['ku_id'])
    await c.execute("DELETE FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII谱社区KC'",SUB)
    async with httpx.AsyncClient(trust_env=False,timeout=40) as cli:
        for cid,concepts in sorted(byc.items(),key=lambda x:-len(x[1])):
            if len(concepts)<3: continue
            try:
                r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
                    json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                          "messages":[{"role":"system","content":SYS},{"role":"user","content":"Concepts: "+", ".join(concepts)}]})
                j=json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e: j={"label":f"社区{cid}","summary":str(e)[:30]}
            members=[t2ku[norm(cn)] for cn in concepts if norm(cn) in t2ku]
            await c.execute("""INSERT INTO aii.kc_onto(substrate_id,level,community_label,summary,member_ku_ids,synthesis_marker)
                VALUES($1,-1,$2,$3,$4,'AII谱社区KC')""",SUB,j.get('label'),j.get('summary'),json.dumps(members))
            print(f"  C{cid}({len(concepts)}概念,{len(members)}KU) → 【{j.get('label')}】 {j.get('summary','')[:50]}")
    n=await c.fetchval("SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII谱社区KC'",SUB)
    print(f"\n持久化谱社区KC: {n} 个入 kc_onto")
    await c.close()
asyncio.run(go())
