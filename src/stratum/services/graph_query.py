"""B 仓概念图遍历检索 — graphify 模式(graphify 启发②)。

不是向量检索: 真图遍历。两种查询:
  - explain(concept): seed 概念 → BFS hop 扩散排名, 返回层级邻居 + 每概念挂载 KU 数
  - path(src, dst): 最短路径(双向 BFS, max_hops 限制), hop-by-hop 可解释

数据源: aii_refined(rf schema) refined_concept + refined_directed_edge + refined_ku_concept。
纯确定性, 零 LLM。图小(1.2K 边), 全量加载内存 BFS 即可。
"""
from __future__ import annotations

import os
from collections import deque
from typing import Any

import psycopg2

REFINED_DSN = os.getenv(
    "REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)


class BGraph:
    """B 仓概念图(内存邻接表)。"""

    def __init__(self) -> None:
        self.adj: dict[int, set[int]] = {}      # concept_id → neighbors
        self.names: dict[int, str] = {}         # concept_id → name
        self.name_id: dict[str, int] = {}       # name(lower) → concept_id
        self.ku_counts: dict[int, int] = {}     # concept_id → KU 数

    def load(self) -> None:
        conn = psycopg2.connect(REFINED_DSN)
        with conn.cursor() as cur:
            cur.execute("SELECT concept_id, name FROM rf.refined_concept WHERE name IS NOT NULL")
            for cid, name in cur.fetchall():
                self.names[cid] = name
                self.name_id.setdefault(str(name).lower(), cid)
            cur.execute(
                "SELECT src_concept, dst_concept FROM rf.refined_directed_edge"
                " WHERE src_concept IS NOT NULL AND dst_concept IS NOT NULL")
            for s, d in cur.fetchall():
                self.adj.setdefault(s, set()).add(d)
                self.adj.setdefault(d, set()).add(s)
            cur.execute(
                "SELECT concept_id, count(*) FROM rf.refined_ku_concept GROUP BY 1")
            for cid, n in cur.fetchall():
                self.ku_counts[cid] = n
        conn.close()

    def resolve(self, name: str) -> int | None:
        return self.name_id.get(name.strip().lower())

    def explain(self, concept: str, max_hops: int = 3, top_k: int = 20) -> dict[str, Any]:
        """seed 概念 → BFS hop 扩散。返回 {concept, hops:[{hop, neighbors:[...]}]}"""
        seed = self.resolve(concept)
        if seed is None:
            return {"concept": concept, "found": False, "hops": []}
        seen = {seed}
        frontier = [seed]
        hops: list[dict] = []
        for hop in range(1, max_hops + 1):
            nxt: list[int] = []
            items: list[dict] = []
            for cid in frontier:
                for nb in sorted(self.adj.get(cid, ())):
                    if nb in seen:
                        continue
                    seen.add(nb)
                    nxt.append(nb)
                    items.append({
                        "concept_id": nb,
                        "name": self.names.get(nb, f"#{nb}"),
                        "ku_count": self.ku_counts.get(nb, 0),
                    })
            items.sort(key=lambda x: -x["ku_count"])
            hops.append({"hop": hop, "count": len(items),
                         "neighbors": items[:top_k]})
            frontier = nxt
            if not frontier:
                break
        return {
            "concept": concept,
            "found": True,
            "seed_id": seed,
            "seed_ku_count": self.ku_counts.get(seed, 0),
            "total_reached": len(seen) - 1,
            "hops": hops,
        }

    def path(self, src: str, dst: str, max_hops: int = 8) -> dict[str, Any]:
        """最短路径(双向 BFS)。返回 hop-by-hop 概念链。"""
        s = self.resolve(src)
        d = self.resolve(dst)
        if s is None or d is None:
            return {"found": False, "reason": "concept not found",
                    "src_found": s is not None, "dst_found": d is not None}
        if s == d:
            return {"found": True, "hops": 0, "path": [self.names.get(s)]}
        # 双向 BFS
        fwd_prev: dict[int, int] = {s: None}
        bwd_prev: dict[int, int] = {d: None}
        fwd_q, bwd_q = deque([s]), deque([d])
        meet: int | None = None
        for _ in range(max_hops // 2 + 1):
            # 扩展前向
            for _ in range(len(fwd_q)):
                u = fwd_q.popleft()
                for v in self.adj.get(u, ()):
                    if v in fwd_prev:
                        continue
                    fwd_prev[v] = u
                    if v in bwd_prev:
                        meet = v
                        break
                    fwd_q.append(v)
                if meet:
                    break
            if meet:
                break
            for _ in range(len(bwd_q)):
                u = bwd_q.popleft()
                for v in self.adj.get(u, ()):
                    if v in bwd_prev:
                        continue
                    bwd_prev[v] = u
                    if v in fwd_prev:
                        meet = v
                        break
                    bwd_q.append(v)
                if meet:
                    break
            if meet:
                break
        if meet is None:
            return {"found": False, "reason": f"no path within {max_hops} hops",
                    "src": src, "dst": dst}
        # 重建路径
        path_ids: list[int] = []
        x = meet
        while x is not None:
            path_ids.append(x)
            x = fwd_prev[x]
        path_ids.reverse()
        x = bwd_prev[meet]
        while x is not None:
            path_ids.append(x)
            x = bwd_prev[x]
        return {
            "found": True,
            "hops": len(path_ids) - 1,
            "src": src,
            "dst": dst,
            "path": [self.names.get(i, f"#{i}") for i in path_ids],
        }


_graph: BGraph | None = None


def get_graph() -> BGraph:
    global _graph
    if _graph is None:
        g = BGraph()
        g.load()
        _graph = g
    return _graph


if __name__ == "__main__":
    import sys
    g = get_graph()
    if len(sys.argv) >= 3 and sys.argv[1] == "path":
        print(g.path(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) >= 2:
        r = g.explain(sys.argv[1])
        print(f"概念: {sys.argv[1]} | 命中: {r['found']} | 扩散: {r.get('total_reached', 0)}")
        for h in r.get("hops", []):
            print(f"  hop{h['hop']}: {[n['name'] for n in h['neighbors'][:8]]}")
    else:
        print("用法: graph_query.py <概念名> | graph_query.py path <A> <B>")
