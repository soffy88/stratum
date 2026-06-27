import asyncio, asyncpg, os, json, httpx
from dotenv import load_dotenv; load_dotenv("/home/soffy/projects/AII/aii/.env", override=True)
SUB=os.getenv('SUBSTRATE','microecon_en_full_v2'); KEY=os.getenv('DEEPSEEK_API_KEY')
SYS=("Given a knowledge cluster's member KU titles, write a 1-2 sentence cluster summary (这个主题讲什么) "
     "STRICTLY from the members (no fabrication). Output JSON {\"zh\":\"<简体中文>\",\"en\":\"<English>\"}.")
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    kcs=await c.fetch("SELECT kc_id,community_label,member_ku_ids FROM aii.kc_onto WHERE substrate_id=$1",SUB)
    # pre-fetch member titles (sequential)
    data=[]
    for kc in kcs:
        ids=json.loads(kc['member_ku_ids']) if isinstance(kc['member_ku_ids'],str) else kc['member_ku_ids']
        titles=await c.fetch("SELECT title FROM aii.ku_onto WHERE ku_id=ANY($1::text[]) LIMIT 18",ids)
        data.append((kc['kc_id'],kc['community_label'],", ".join(t['title'] for t in titles)))
    # concurrent LLM (no DB)
    sem=asyncio.Semaphore(8)
    async with httpx.AsyncClient(trust_env=False,timeout=40) as cli:
        async def gen(kid,label,tt):
            async with sem:
                try:
                    r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
                        json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                              "messages":[{"role":"system","content":SYS},{"role":"user","content":f"Cluster: {label}\nMembers: {tt}"}]})
                    j=json.loads(r.json()["choices"][0]["message"]["content"]); return kid,j.get('zh',''),j.get('en','')
                except Exception: return kid,None,None
        res=await asyncio.gather(*(gen(*d) for d in data))
    # sequential writes
    n=0
    for kid,zh,en in res:
        if zh: await c.execute("UPDATE aii.kc_onto SET summary=$2,summary_en=$3 WHERE kc_id=$1",kid,zh,en); n+=1
    print(f"双语摘要: {n}/{len(kcs)}")
    await c.close()
asyncio.run(go())
