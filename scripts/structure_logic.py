import asyncio, asyncpg, os, json
from collections import defaultdict
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'
def extract_chains(edges):
    adj=defaultdict(list); indeg=defaultdict(int); nodes=set()
    for s,d in edges:
        if d not in adj[s]: adj[s].append(d)
        indeg[d]+=1; nodes.add(s); nodes.add(d)
    for n in nodes: indeg.setdefault(n,0)
    sources=[n for n in nodes if indeg[n]==0] or list(nodes)[:1]
    chains=[]
    def dfs(n,path,seen):
        if n in seen or not adj[n]: chains.append(path); return
        for m in adj[n]: dfs(m,path+[m],seen|{n})
    for s in sources: dfs(s,[s],set())
    # 只留多跳链(≥3节点=≥2跳); 去被包含的子链
    chains=[c for c in chains if len(c)>=3]
    chains.sort(key=len,reverse=True)
    kept=[]
    for c in chains:
        if not any(' > '.join(c) in ' > '.join(k) for k in kept): kept.append(c)
    return kept
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.ku_logic_structure(
        substrate_id text, ku_id text, causal_chains jsonb, decomposition jsonb, prerequisites jsonb,
        PRIMARY KEY(substrate_id,ku_id));""")
    await c.execute("DELETE FROM aii.ku_logic_structure WHERE substrate_id=$1",SUB)
    rows=await c.fetch("SELECT ku_id,src_name,dst_name,relation_type FROM aii.ku_internal_logic WHERE substrate_id=$1",SUB)
    byku=defaultdict(list)
    for r in rows: byku[r['ku_id']].append((r['src_name'],r['dst_name'],r['relation_type']))
    nchains=0; ndecomp=0
    for ku,rels in byku.items():
        chains=extract_chains([(s,d) for s,d,t in rels if t=='derives'])
        decomp=defaultdict(list)
        for s,d,t in rels:
            if t=='subsumes' and d not in decomp[s]: decomp[s].append(d)
        prereq=[[s,d] for s,d,t in rels if t=='prerequisite']
        nchains+=len(chains); ndecomp+=len(decomp)
        await c.execute("INSERT INTO aii.ku_logic_structure VALUES($1,$2,$3,$4,$5)",
            SUB,ku,json.dumps(chains,ensure_ascii=False),json.dumps(decomp,ensure_ascii=False),json.dumps(prereq,ensure_ascii=False))
    print(f"structured {len(byku)} KUs: {nchains} causal chains(≥2跳), {ndecomp} decomposition groups",flush=True)
    await c.close()
asyncio.run(go())
