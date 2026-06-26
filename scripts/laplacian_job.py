"""持续 Laplacian 作业: 算谱指标+社区+中心 → 存快照(laplacian_snapshot)+持久化谱社区(spectral_community)
+ 对比上次快照(谱演化). 可复跑/排程(图增长时增量追踪). Usage: laplacian_job.py"""
import asyncio, asyncpg, os, json, numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import laplacian, connected_components
from scipy.sparse.linalg import eigsh
from scipy.cluster.vq import kmeans2
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB="microecon_en_full_v2"; K=22
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.laplacian_snapshot(
        run_id bigserial PRIMARY KEY, substrate_id text, run_ts timestamptz DEFAULT now(),
        n_nodes int, n_edges int, n_components int, fiedler real, n_communities int, hubs jsonb);""")
    await c.execute("""CREATE TABLE IF NOT EXISTS aii.spectral_community(
        substrate_id text, community_id int, concept_name text, PRIMARY KEY(substrate_id,community_id,concept_name));""")
    cooc=await c.fetch("""SELECT cs.name s, cd.name d, count(*) w
        FROM aii.ku_concept_onto a JOIN aii.ku_concept_onto b ON a.concept_id<b.concept_id AND a.ku_id=b.ku_id
        JOIN aii.ku_onto k ON a.ku_id=k.ku_id AND k.substrate_id=$1
        JOIN aii.concept_onto cs ON a.concept_id=cs.concept_id JOIN aii.concept_onto cd ON b.concept_id=cd.concept_id
        GROUP BY 1,2 HAVING count(*)>=2""",SUB)
    edges=await c.fetch("""SELECT cs.name s, cd.name d FROM aii.directed_edge_v2 e
        JOIN aii.concept_onto cs ON e.src_concept_id=cs.concept_id JOIN aii.concept_onto cd ON e.dst_concept_id=cd.concept_id
        WHERE e.substrate_id=$1""",SUB)
    nodes=sorted({x for e in cooc for x in (e['s'],e['d'])} | {x for e in edges for x in (e['s'],e['d'])})
    idx={n:i for i,n in enumerate(nodes)}; N=len(nodes)
    A=sp.lil_matrix((N,N))
    for e in cooc: A[idx[e['s']],idx[e['d']]]=e['w']; A[idx[e['d']],idx[e['s']]]=e['w']
    for e in edges: A[idx[e['s']],idx[e['d']]]+=2; A[idx[e['d']],idx[e['s']]]+=2
    A=A.tocsr()
    ncomp,lab=connected_components(A,directed=False); sizes=np.bincount(lab)
    big=np.argmax(sizes); mask=lab==big; sub=A[mask][:,mask]; subnodes=[n for n,m in zip(nodes,mask) if m]
    L=laplacian(sub,normed=True); vals,vecs=eigsh(L,k=K+1,which='SM'); fiedler=float(vals[1])
    cent,clab=kmeans2(vecs[:,1:K+1],K,minit='++',seed=3)
    deg=np.asarray(A.sum(1)).ravel(); hubs=[{"c":nodes[i],"deg":int(deg[i])} for i in np.argsort(-deg)[:8]]
    ncomm=len(set(clab))
    # diff vs last
    last=await c.fetchrow("SELECT * FROM aii.laplacian_snapshot WHERE substrate_id=$1 ORDER BY run_id DESC LIMIT 1",SUB)
    # write snapshot
    await c.execute("INSERT INTO aii.laplacian_snapshot(substrate_id,n_nodes,n_edges,n_components,fiedler,n_communities,hubs) VALUES($1,$2,$3,$4,$5,$6,$7)",
        SUB,N,len(edges),int(ncomp),fiedler,ncomm,json.dumps(hubs,ensure_ascii=False))
    # persist communities
    await c.execute("DELETE FROM aii.spectral_community WHERE substrate_id=$1",SUB)
    for n,cl in zip(subnodes,clab):
        await c.execute("INSERT INTO aii.spectral_community VALUES($1,$2,$3) ON CONFLICT DO NOTHING",SUB,int(cl),n)
    print(f"snapshot: nodes={N} edges={len(edges)} components={ncomp} fiedler={fiedler:.4f} communities={ncomm}")
    if last:
        print(f"Δ vs last: nodes {last['n_nodes']}->{N}({N-last['n_nodes']:+d}), edges {last['n_edges']}->{len(edges)}({len(edges)-last['n_edges']:+d}), "
              f"components {last['n_components']}->{ncomp}, fiedler {last['fiedler']:.4f}->{fiedler:.4f}({fiedler-last['fiedler']:+.4f})")
    else:
        print("(first snapshot — baseline; 后续运行将追踪谱演化)")
    await c.close()
asyncio.run(go())
