import asyncio, asyncpg, os, re
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB=os.getenv('SUBSTRATE','microecon_en_full_v2')
def norm(t):
    t=re.sub(r'\([^)]*\)','',t).lower().strip(); t=re.sub(r'[^a-z0-9一-鿿\s/&-]','',t)
    return re.sub(r's\b','',re.sub(r'\s+',' ',t).strip())
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    # canon concepts (from v2 KU titles, same as materialize) → concept_id
    kus=await c.fetch(f"SELECT title FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    cb={}  # norm -> concept_id
    for k in kus:
        n=norm(k['title'])
        if n and n not in cb:
            name=re.sub(r'\s*\([^)]*\)','',k['title']).strip()
            r=await c.fetchrow("SELECT concept_id FROM aii.concept_onto WHERE name=$1",name)
            if r: cb[n]=r['concept_id']
    def match(name):
        n=norm(name)
        if not n: return None
        if n in cb: return cb[n]
        cjk=bool(re.search(r'[一-鿿]',n))
        best=None
        for cn in cb:
            # 英文: 后缀整词匹配; 中文: 子串互含(≥2字, 映射↔映射与函数)
            if cjk:
                ok = len(n)>=2 and (n in cn or (len(cn)>=2 and cn in n))
            else:
                ok = len(cn)>=6 and (n==cn or n.endswith(' '+cn))
            if ok and (best is None or len(cn)>len(best)): best=cn
        return cb.get(best) if best else None
    # tables
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.directed_edge_v2(
        substrate_id text, src_concept_id bigint, dst_concept_id bigint, relation_type text,
        evidence_count int, source_kus text, PRIMARY KEY(substrate_id,src_concept_id,dst_concept_id,relation_type));""")
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.ku_internal_logic(
        substrate_id text, ku_id text, src_name text, dst_name text, relation_type text);""")
    await c.execute("DELETE FROM aii.directed_edge_v2 WHERE substrate_id=$1",SUB)
    await c.execute("DELETE FROM aii.ku_internal_logic WHERE substrate_id=$1",SUB)
    rows=await c.fetch("SELECT ku_id,src_name,dst_name,relation_type FROM aii.concept_readout_edge WHERE substrate_id=$1",SUB)
    from collections import defaultdict
    cedge=defaultdict(lambda:[0,set()]); internal=0
    for r in rows:
        s=match(r['src_name']); d=match(r['dst_name'])
        if s and d and s!=d:   # 概念级: 两端都规范概念 → 接概念图
            cedge[(s,d,r['relation_type'])][0]+=1; cedge[(s,d,r['relation_type'])][1].add(r['ku_id'])
        else:                  # KU内部逻辑(命题/步骤/结果)→ 留KU内, 不污染概念图
            await c.execute("INSERT INTO aii.ku_internal_logic VALUES($1,$2,$3,$4,$5)",SUB,r['ku_id'],r['src_name'],r['dst_name'],r['relation_type']); internal+=1
    for (s,d,rt),(n,kset) in cedge.items():
        await c.execute("INSERT INTO aii.directed_edge_v2 VALUES($1,$2,$3,$4,$5,$6)",SUB,s,d,rt,n,','.join(list(kset)[:3]))
    print(f"readout raw={len(rows)} | concept-level edges={len(cedge)} | KU-internal logic={internal}",flush=True)
    # retire signal-method dirty edges
    sig=await c.fetchval("SELECT count(*) FROM aii.concept_directed_edge WHERE substrate_id=$1",SUB)
    await c.execute("DELETE FROM aii.concept_directed_edge WHERE substrate_id=$1",SUB)
    print(f"retired signal-method edges: {sig}",flush=True)
    await c.close()
asyncio.run(go())
