import asyncio, asyncpg, os, json, re
from collections import defaultdict
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB=os.getenv('SUBSTRATE','microecon_en_full_v2')
STOP=set("the a an of in to for and or with on at by from as is are be its their this that which when then due will can may shift change increase decrease higher lower more less".split())
def toks(s): return frozenset(w for w in re.sub(r'[^a-z0-9 ]',' ',s.lower()).split() if w not in STOP and len(w)>1)
def cmap_for(nodes):
    nodes=list(set(nodes)); par={n:n for n in nodes}
    def find(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    T={n:toks(n) for n in nodes}
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            a,b=nodes[i],nodes[j]; ta,tb=T[a],T[b]
            if not ta or not tb: continue
            if ta<=tb or tb<=ta or len(ta&tb)/len(ta|tb)>=0.6: par[find(a)]=find(b)
    grp=defaultdict(list)
    for n in nodes: grp[find(n)].append(n)
    m={}
    for g in grp.values():
        c=min(g,key=len)         # 最短为规范名
        for n in g: m[n]=c
    return m
def chains(edges):
    adj=defaultdict(list); ind=defaultdict(int); nd=set()
    for s,d in edges:
        if d not in adj[s]: adj[s].append(d)
        ind[d]+=1; nd|={s,d}
    for n in nd: ind.setdefault(n,0)
    src=[n for n in nd if ind[n]==0] or list(nd)[:1]; out=[]
    def dfs(n,p,seen):
        if n in seen or not adj[n]: out.append(p); return
        for m in adj[n]: dfs(m,p+[m],seen|{n})
    for s in src: dfs(s,[s],set())
    out=[c for c in out if len(c)>=3]; out.sort(key=len,reverse=True); kept=[]
    for c in out:
        if not any(' > '.join(c) in ' > '.join(k) for k in kept): kept.append(c)
    return kept[:6]
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows=await c.fetch("SELECT ku_id,src_name,dst_name,relation_type FROM aii.ku_internal_logic WHERE substrate_id=$1",SUB)
    byku=defaultdict(list)
    for r in rows: byku[r['ku_id']].append((r['src_name'],r['dst_name'],r['relation_type']))
    nb=na=ch0=ch1=0
    for ku,rels in byku.items():
        nodes=[x for s,d,_ in rels for x in (s,d)]
        cm=cmap_for(nodes); nb+=len(set(nodes)); na+=len(set(cm.values()))
        norm=[(cm[s],cm[d],t) for s,d,t in rels if cm[s]!=cm[d]]
        ch_before=chains([(s,d) for s,d,t in rels if t=='derives'])
        chs=chains(list({(s,d) for s,d,t in norm if t=='derives'}))
        ch0+=len(ch_before); ch1+=len(chs)
        decomp=defaultdict(list)
        for s,d,t in norm:
            if t=='subsumes' and d not in decomp[s]: decomp[s].append(d)
        prereq=[[s,d] for s,d,t in norm if t=='prerequisite']
        await c.execute("UPDATE aii.ku_logic_structure SET causal_chains=$3,decomposition=$4,prerequisites=$5 WHERE substrate_id=$1 AND ku_id=$2",
            SUB,ku,json.dumps(chs,ensure_ascii=False),json.dumps(decomp,ensure_ascii=False),json.dumps(prereq,ensure_ascii=False))
    pct = f"{100*(nb-na)//nb}%" if nb else "n/a"
    print(f"node norm: distinct nodes {nb}->{na} (-{nb-na}, {pct}); chains {ch0}->{ch1}",flush=True)
    await c.close()
asyncio.run(go())
