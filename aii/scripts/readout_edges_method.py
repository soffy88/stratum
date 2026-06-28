import asyncio, asyncpg, os, json, re, httpx
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'; KEY=os.getenv('DEEPSEEK_API_KEY')
TARGET=['Economic Cost','Explicit Cost','Implicit Cost','Accounting Cost','Profit','Economic Profit',
 'Marginal cost','Marginal benefit','Investment','Investment Return','Discount Rate','Net Present Value',
 'Scarcity','Rational choice','Opportunity Cost','Comparative Advantage','Demand','Demand Curve','Supply Curve',
 'Price elasticity of demand','Monopoly definition and conditions','Sunk Cost','Present Value (PV)','Human Capital',
 'Producer Surplus','Consumer Surplus','Market Equilibrium','Equilibrium Price','Bargaining power','Threat point']
SYS=("Read out ONLY the directed relations this knowledge unit's text EXPLICITLY expresses. "
     "Do NOT infer relations not stated; do NOT pair unrelated concepts. Types: "
     "prerequisite (A must be understood/exist before B), subsumes (A includes B as a part/type), "
     "derives (A leads to/produces/implies B). src/dst named in text. "
     'Output JSON {"rels":[{"src":"..","dst":"..","type":".."}]}. None→{"rels":[]}.')
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    await c.execute("DELETE FROM aii.concept_readout_edge WHERE substrate_id=$1",SUB)
    kus=await c.fetch(f"SELECT ku_id,title,natural_text FROM aii.ku_onto WHERE substrate_id='{SUB}' AND title=ANY($1::text[])",TARGET)
    print(f"sample KUs: {len(kus)}",flush=True)
    sem=asyncio.Semaphore(10); tot=[0]; lock=asyncio.Lock()
    async with httpx.AsyncClient(trust_env=False, timeout=40) as cli:
        async def rd(k):
            async with sem:
                rels=[]
                try:
                    r=await cli.post("https://api.deepseek.com/chat/completions",
                        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
                        json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                              "messages":[{"role":"system","content":SYS},{"role":"user","content":f"Concept: {k['title']}\n\n{k['natural_text'][:2500]}"}]})
                    t=r.json()["choices"][0]["message"]["content"]
                    j=json.loads(t)
                    rels=[x for x in j.get('rels',[]) if x.get('src') and x.get('dst') and x.get('type') in('prerequisite','subsumes','derives') and x['src']!=x['dst']]
                except Exception as e: print("  err",k['title'][:20],str(e)[:40],flush=True)
                async with lock:
                    for x in rels:
                        await c.execute("INSERT INTO aii.concept_readout_edge VALUES($1,$2,$3,$4,$5)",SUB,k['ku_id'],x['src'][:120],x['dst'][:120],x['type']); tot[0]+=1
        await asyncio.gather(*(rd(k) for k in kus))
    print(f"readout edges: {tot[0]}",flush=True)
    await c.close()
asyncio.run(go())
