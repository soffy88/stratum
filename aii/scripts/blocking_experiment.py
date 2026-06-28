import asyncio, os, re
from pathlib import Path
from itertools import combinations
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv
load_dotenv(Path("/home/soffy/projects/AII/aii/.env"), override=True)
import asyncpg
SUB="microecon_en_ch3"
async def main():
    c=await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector; await register_vector(c)
    kus=await c.fetch(f"SELECT ku_id,embedding FROM aii.ku_onto WHERE substrate_id='{SUB}' AND embedding IS NOT NULL")
    cc=await c.fetch(f"""SELECT kc.ku_id,kc.concept_id FROM aii.ku_concept_onto kc
       JOIN aii.ku_onto k ON kc.ku_id=k.ku_id AND k.substrate_id='{SUB}'""")
    edges=await c.fetch(f"SELECT src_id,dst_id,relation_type,'' rel FROM aii.edge_onto WHERE substrate_id='{SUB}'")
    # known-real subset: contrasts + because-causal explains
    realrows=await c.fetch(f"""SELECT e.src_id,e.dst_id,e.relation_type rel, ka.natural_text sa, kb.natural_text sb
       FROM aii.edge_onto e JOIN aii.ku_onto ka ON e.src_id=ka.ku_id JOIN aii.ku_onto kb ON e.dst_id=kb.ku_id
       WHERE e.substrate_id='{SUB}'""")
    await c.close()
    ids=[r["ku_id"] for r in kus]
    idx={k:i for i,k in enumerate(ids)}
    E=np.array([[float(x) for x in r["embedding"]] for r in kus],dtype=np.float32)
    En=E/(np.linalg.norm(E,axis=1,keepdims=True)+1e-12)
    concepts=defaultdict(set)
    for r in cc: concepts[r["ku_id"]].add(r["concept_id"])
    n=len(ids); total=n*(n-1)//2
    def passes(a,b):  # blocking: shared>=1 OR sim>0.5
        if concepts[a] & concepts[b]: return True
        return float(En[idx[a]]@En[idx[b]])>0.5
    kept=0; shared_only=0; sim_only=0
    for a,b in combinations(ids,2):
        sh=bool(concepts[a]&concepts[b]); sm=float(En[idx[a]]@En[idx[b]])>0.5
        if sh or sm:
            kept+=1
            if sh and not sm: shared_only+=1
            if sm and not sh: sim_only+=1
    print(f"=== ① blocking on {total} pairs ({n} KU) ===")
    print(f"  kept(send to judge)={kept} ({100*kept/total:.0f}%)  kicked(zero-assoc)={total-kept} ({100*(total-kept)/total:.0f}%)")
    print(f"  kept via: shared-concept-only={shared_only}, sim>0.5-only={sim_only}, both={kept-shared_only-sim_only}")
    # ② no误杀: do existing real edges pass blocking?
    def epass(r):
        a,b=r["src_id"],r["dst_id"]
        if a in idx and b in idx: return passes(a,b)
        return None
    allp=[epass(r) for r in realrows]; allp=[x for x in allp if x is not None]
    contr=[r for r in realrows if r["rel"]=="contrasts_with"]
    caus=[r for r in realrows if r["rel"]=="explains" and re.search(r'\bbecause\b',(r["sa"]or'')+(r["sb"]or''),re.I)]
    cp=sum(1 for r in contr if epass(r)); kp=sum(1 for r in caus if epass(r))
    print(f"\n=== ② ★不误杀: existing edges passing blocking ===")
    print(f"  all edges: {sum(allp)}/{len(allp)} = {100*sum(allp)/max(len(allp),1):.0f}%")
    print(f"  contrasts: {cp}/{len(contr)} = {100*cp/max(len(contr),1):.0f}%")
    print(f"  because-causal: {kp}/{len(caus)} = {100*kp/max(len(caus),1):.0f}%")
    print(f"\n=== ③ save vs judge-all: {total}→{kept} judged, saved {100*(total-kept)/total:.0f}% LLM ===")
asyncio.run(main())
