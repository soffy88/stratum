import asyncio, asyncpg, os, re
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'
def norm(t):
    t=re.sub(r'\([^)]*\)','',t).lower().strip(); t=re.sub(r'[^a-z0-9\s/&-]','',t)
    return re.sub(r's\b','',re.sub(r'\s+',' ',t).strip())
# 有向信号(语言信号, 确定性): A [signal] B
PREREQ=re.compile(r'\b(?:based on|builds? on|build upon|relies on|rely on|depends on|requires?|presupposes?|derived from|rests on|grounded in|founded on|premised on)\b',re.I)
SUBSUM=re.compile(r'\b(?:includes?|consists? of|comprises?|composed of|made up of|divided into|categor\w+ into|types of|forms of|encompasses?|subsumes?)\b',re.I)
DERIV =re.compile(r'\b(?:leads? to|results? in|gives? rise to|produces?|causes?|derives?|yields?|implies?|therefore|thus result)\b',re.I)
SIGS=[('prerequisite',PREREQ),('subsumes',SUBSUM),('derives',DERIV)]
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.concept_directed_edge(
        substrate_id text, src_concept_id bigint, dst_concept_id bigint, relation_type text,
        evidence_count int, PRIMARY KEY(substrate_id,src_concept_id,dst_concept_id,relation_type));""")
    await c.execute("DELETE FROM aii.concept_directed_edge WHERE substrate_id=$1",SUB)
    kus=await c.fetch(f"SELECT title,natural_text FROM aii.ku_onto WHERE substrate_id='{SUB}'")
    # concept vocab + id
    canon={}
    for k in kus:
        n=norm(k['title'])
        if n and n not in canon: canon[n]=re.sub(r'\s*\([^)]*\)','',k['title']).strip()
    cid={}
    for n,name in canon.items():
        r=await c.fetchrow("SELECT concept_id FROM aii.concept_onto WHERE name=$1",name)
        if r: cid[n]=r['concept_id']
    phrases=[(n,re.compile(r'(?<![a-z])'+re.escape(n)+r'(?:e?s)?(?![a-z])',re.I)) for n in canon if len(n)>=6]
    from collections import Counter
    edges=Counter()
    PROX=55
    NEG=re.compile(r'(?:not|n.t|never|exclud\w*|without|rather than|unlike|as opposed to|instead of|ignore\w*|omit\w*)\W*$',re.I)
    for k in kus:
        for sent in re.split(r'(?<=[.!?])\s+', k['natural_text'] or ''):
            for rtype,sig in SIGS:
                for m in sig.finditer(sent):
                    if NEG.search(sent[max(0,m.start()-30):m.start()]): continue
                    # nearest concept before / after the signal, within PROX chars
                    before=[(mm.end(),n) for n,rx in phrases for mm in rx.finditer(sent) if 0<=m.start()-mm.end()<=PROX]
                    after =[(mm.start(),n) for n,rx in phrases for mm in rx.finditer(sent) if 0<=mm.start()-m.end()<=PROX]
                    if not before or not after: continue
                    A=max(before)[1]; B=min(after)[1]
                    if A==B: continue
                    # direction: prereq → src=B(prereq) dst=A; subsumes/derives → src=A dst=B
                    src,dst=(B,A) if rtype=='prerequisite' else (A,B)
                    if src in cid and dst in cid and cid[src]!=cid[dst]:
                        edges[(cid[src],cid[dst],rtype)]+=1
    for (s,d,rt),n in edges.items():
        await c.execute("INSERT INTO aii.concept_directed_edge VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",SUB,s,d,rt,n)
    print(f"directed edges: {len(edges)}", flush=True)
    await c.close()
asyncio.run(go())
