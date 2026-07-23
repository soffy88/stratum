"""候选粗筛 — 从 A仓 ku_onto 向量近邻挖"可能同点"的 KU 对(判同的输入)。
BGE-M3 跨语种对齐, 高相似捞候选(含跨书/跨语言); 高相似≠同一, 由判同定夺。
非静默截断: 超 cap 时报告丢弃数(设计红线)。
"""

from __future__ import annotations

import numpy as np
from pgvector.asyncpg import register_vector


async def ku_candidates(
    conn, *, sim=0.88, cap=400, substrates=None, cross_book_only=False, exclude=None
):
    """返回 (candidates, dropped)。candidate={a_id,b_id,a_book,b_book,sim}, 按 sim 降序取 cap 个。
    exclude: 已入 B仓 的 raw_ku_id 集合(幂等: 不再作候选)。"""
    await register_vector(conn)
    where, args = "WHERE embedding IS NOT NULL AND is_quarantined IS NOT TRUE", []
    if substrates:
        where += " AND substrate_id = ANY($1::text[])"
        args.append(list(substrates))
    rows = await conn.fetch(
        f"SELECT ku_id, substrate_id, title, embedding FROM aii.ku_onto {where}", *args
    )
    if exclude:
        rows = [r for r in rows if r["ku_id"] not in exclude]
    if not rows:
        return [], 0
    ids = [r["ku_id"] for r in rows]
    books = [r["substrate_id"] for r in rows]
    V = np.array([np.asarray(r["embedding"], dtype=np.float32) for r in rows])
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
    S = V @ V.T
    n = len(ids)
    triu = []
    for i in range(n):
        row = S[i]
        for j in range(i + 1, n):
            if row[j] >= sim and not (cross_book_only and books[i] == books[j]):
                triu.append((float(row[j]), i, j))
    triu.sort(reverse=True)
    out = [
        {"a_id": ids[i], "b_id": ids[j], "a_book": books[i], "b_book": books[j], "sim": round(s, 3)}
        for s, i, j in triu[:cap]
    ]
    return out, max(0, len(triu) - cap)
