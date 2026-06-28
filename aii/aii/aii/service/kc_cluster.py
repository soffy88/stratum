"""KC 聚类持久化: ★Louvain(吃边) → kc_onto.

CC 验证得到的两个真相 (必须遵守):
  ① 用 Louvain (networkx, 吃 edge_onto 的边), 不用 community_cluster
     —— 后者是 embedding k-means, 不吃边, 对跨块真边视而不见.
  ② 不用原始连通分量 —— 枢纽 KU 桥接会塌成巨簇 (实测 95 节点);
     Louvain 按模块度把它拆回主题子团 (实测 [20,20,13,11,...]).

grade ≤ 成员 KU (成员皆 unverified → kc 也 unverified), 永不最高级.
synthesis_marker 标 "AII综合,非原文断言".
"""
from __future__ import annotations

import json
import re

import networkx as nx


_LABEL_SYS = "You name and summarize a cluster of related knowledge units. Output valid JSON only."
_LABEL_TMPL = """\
These knowledge-unit titles all belong to one cluster from an economics textbook:

{titles}

Output JSON: {{"label": "<2-5 word topic label>", "summary": "<one sentence: what this cluster covers>"}}"""


def _parse(resp) -> dict:
    txt = ""
    for blk in resp.get("content", []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += blk.get("text", "")
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


async def cluster_and_persist(conn, llm, *, substrate_id: str,
                              resolution: float = 1.0, min_size: int = 2) -> dict:
    """在 substrate 的 KU→KU 图上跑 Louvain, 每社区写一条 kc_onto."""
    ku = await conn.fetch(
        "SELECT ku_id, title FROM aii.ku_onto WHERE substrate_id=$1", substrate_id)
    title_of = {r["ku_id"]: r["title"] for r in ku}
    edges = await conn.fetch("""
        SELECT e.src_id, e.dst_id FROM aii.edge_onto e
        JOIN aii.ku_onto s ON e.src_id=s.ku_id AND s.substrate_id=$1
        JOIN aii.ku_onto d ON e.dst_id=d.ku_id AND d.substrate_id=$1""", substrate_id)

    G = nx.Graph()
    G.add_nodes_from(title_of.keys())
    for e in edges:
        if e["src_id"] != e["dst_id"]:
            G.add_edge(e["src_id"], e["dst_id"])

    # ★Louvain (吃边), 不用连通分量
    communities = [c for c in nx.community.louvain_communities(G, resolution=resolution, seed=42)
                   if len(c) >= min_size]

    persisted = 0
    sizes = []
    for comm in sorted(communities, key=len, reverse=True):
        members = list(comm)
        titles = [title_of.get(m, "") for m in members]
        try:
            resp = await llm(
                messages=[{"role": "user",
                           "content": _LABEL_TMPL.format(titles="\n".join(f"- {t}" for t in titles[:15]))}],
                system=_LABEL_SYS, max_tokens=120)
            lab = _parse(resp)
        except Exception:
            lab = {}
        await conn.execute("""
            INSERT INTO aii.kc_onto
              (substrate_id, level, community_label, summary, member_ku_ids, grade, synthesis_marker)
            VALUES ($1, 1, $2, $3, $4::jsonb, 'unverified', 'AII综合,非原文断言')""",
            substrate_id, lab.get("label"), lab.get("summary"),
            json.dumps(members))
        persisted += 1
        sizes.append(len(members))

    return {"communities": persisted, "sizes": sorted(sizes, reverse=True),
            "covered": G.number_of_nodes() - len([x for x in G if G.degree(x) == 0]),
            "total_ku": G.number_of_nodes(), "edges": G.number_of_edges()}
