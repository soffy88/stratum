import asyncio, asyncpg, os, numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import laplacian, connected_components
from scipy.sparse.linalg import eigsh
from scipy.cluster.vq import kmeans2
from dotenv import load_dotenv; load_dotenv('aii/.env',override=True)
SUB='microecon_en_full_v2'
async def go():
    c=await asyncpg.connect(os.getenv('DATABASE_URL'))
    edges=await c.fetch("""SELECT cs.name s, cd.name d FROM aii.directed_edge_v2 e
        JOIN aii.concept_onto cs ON e.src_concept_id=cs.concept_id JOIN aii.concept_onto cd ON e.dst_concept_id=cd.concept_id
        WHERE e.substrate_id=$1""",SUB)
    await c.close()
    nodes=sorted({x for e in edges for x in (e['s'],e['d'])}); idx={n:i for i,n in enumerate(nodes)}
    N=len(nodes); print(f"concept graph: {N} nodes, {len(edges)} edges")
    A=sp.lil_matrix((N,N))
    for e in edges: A[idx[e['s']],idx[e['d']]]=1; A[idx[e['d']],idx[e['s']]]=1  # 对称化(社区结构)
    A=A.tocsr()
    ncomp,lab=connected_components(A,directed=False)
    sizes=np.bincount(lab); print(f"connected components: {ncomp} (largest={sizes.max()}, isolated/small={sum(sizes<=2)})")
    # 最大连通分量做谱分析
    big=np.argmax(sizes); mask=lab==big; sub=A[mask][:,mask]; subnodes=[n for n,m in zip(nodes,mask) if m]
    L=laplacian(sub,normed=True)
    k=8
    vals,vecs=eigsh(L,k=k+1,which='SM')
    print(f"algebraic connectivity (Fiedler λ2)={vals[1]:.4f} (越大越紧密)")
    # 谱聚类: 用前k特征向量 kmeans
    emb=vecs[:,1:k+1]
    cent,clab=kmeans2(emb,k,minit='++',seed=1)
    from collections import defaultdict
    comm=defaultdict(list)
    for n,cl in zip(subnodes,clab): comm[cl].append(n)
    print(f"\n=== 谱聚类 → {len([g for g in comm.values() if g])} 概念社区 ===")
    for cl,g in sorted(comm.items(),key=lambda x:-len(x[1])):
        if len(g)>=2: print(f"  社区{cl} ({len(g)}): {', '.join(g[:10])}")
    # 度中心性 top
    deg=np.asarray(A.sum(1)).ravel()
    top=np.argsort(-deg)[:10]
    print(f"\n=== 度中心枢纽概念 ===")
    for i in top: print(f"  {nodes[i]} (度={int(deg[i])})")
asyncio.run(go())
