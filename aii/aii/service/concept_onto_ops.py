"""AII 概念存储层操作: 向量标记(方案A) + 概念语义归一 + 本性收敛.

依据 AII-CONCEPT-STORAGE-001 / AII-CONCEPT-NATURE-001.

★向量标记机制 = 方案A (硬分组), 实测结论 (m2_marker):
  概念向量存 concept_onto.vector / 本性存 concept_onto.nature_vector(及
  nature_concept.vector) / KU 存 ku_onto.embedding. 比相似度时 WHERE/分组
  只在同类型内比 → 跨类型永不参与计算 → 0 误判, 由构造保证, 无需调权重.
  (实测: 向量内追加标记维=实现B 需 M>=5 才拉开, 且会把同类相似度抬到 ~0.98
   摧毁语义归一所需的类内区分度 → 弃用.)

所有向量同一套 BGE-M3 1024 维 (oprim.vector_encode provider='default'),
与 ku_onto.embedding 同空间, 可直接比较.
"""
from __future__ import annotations

import json
from itertools import combinations

import numpy as np
from oprim import vector_encode


def _cos(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _encode(texts: list[str]) -> np.ndarray:
    """同 KU 一套 1024 维向量 (带 concept 类型语义, 类型隔离靠存储位置=方案A)."""
    return np.asarray(vector_encode(texts=texts, provider="default"))


def _union_groups(items: list, vecs: np.ndarray, threshold: float) -> list[list[int]]:
    """对 vecs 按余弦 >= threshold 做并查集分组, 返回 size>=2 的组(下标)."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in combinations(range(n), 2):
        if _cos(vecs[i], vecs[j]) >= threshold:
            parent[find(i)] = find(j)
    from collections import defaultdict
    g = defaultdict(list)
    for i in range(n):
        g[find(i)].append(i)
    return [v for v in g.values() if len(v) > 1]


async def vectorize_and_normalize(conn, *, substrate_id: str, discipline: str,
                                  threshold: float = 0.90) -> dict:
    """里程碑3: 给 substrate 的概念算向量并填 vector/discipline, 然后语义归一.

    归一规则 (★同 discipline 内才比, 同名+不同 discipline 不合):
      - 同 discipline 内向量相似度 >= threshold → 同一概念 → 合并(保留 canonical,
        被合并的名进 aliases, ku_concept_onto 链接改指 canonical, 删重复行).
      - < threshold → 不同概念, 各自独立.
    返回 stats.
    """
    rows = await conn.fetch(
        """SELECT DISTINCT c.concept_id, c.name FROM aii.ku_concept_onto kc
           JOIN aii.concept_onto c ON kc.concept_id = c.concept_id
           JOIN aii.ku_onto k ON kc.ku_id = k.ku_id AND k.substrate_id = $1
           ORDER BY c.name""",
        substrate_id,
    )
    cids = [r["concept_id"] for r in rows]
    names = [r["name"] for r in rows]
    if not cids:
        return {"before": 0, "after": 0, "merged": 0, "groups": []}

    vecs = _encode(names)
    # 填 vector + discipline (方案A: 存在 concept_onto.vector = 概念类型)
    for cid, vec in zip(cids, vecs):
        await conn.execute(
            "UPDATE aii.concept_onto SET vector = $1, discipline = $2 WHERE concept_id = $3",
            vec.tolist(), discipline, cid,
        )

    # link 数用于选 canonical (最中心的留)
    link_cnt = {r["concept_id"]: r["n"] for r in await conn.fetch(
        "SELECT concept_id, count(*) n FROM aii.ku_concept_onto GROUP BY 1")}

    groups = _union_groups(cids, vecs, threshold)
    merged_total = 0
    group_report = []
    async with conn.transaction():
        for grp in groups:
            members = [(cids[i], names[i]) for i in grp]
            # canonical = 链接最多, 平手取名字最短(最泛)
            canonical = max(members, key=lambda m: (link_cnt.get(m[0], 0), -len(m[1])))
            can_id, can_name = canonical
            dups = [m for m in members if m[0] != can_id]
            dup_ids = [d[0] for d in dups]
            # KU 链接改指 canonical (冲突跳过), 再删重复概念(级联删其旧链接)
            await conn.execute(
                """INSERT INTO aii.ku_concept_onto(ku_id, concept_id)
                   SELECT ku_id, $1 FROM aii.ku_concept_onto WHERE concept_id = ANY($2)
                   ON CONFLICT DO NOTHING""",
                can_id, dup_ids,
            )
            # 别名归并
            await conn.execute(
                "UPDATE aii.concept_onto SET aliases = aliases || $1::jsonb WHERE concept_id = $2",
                json.dumps([d[1] for d in dups]), can_id,
            )
            await conn.execute(
                "DELETE FROM aii.concept_onto WHERE concept_id = ANY($1)", dup_ids)
            merged_total += len(dups)
            group_report.append({"canonical": can_name, "merged": [d[1] for d in dups]})

    return {"before": len(cids), "after": len(cids) - merged_total,
            "merged": merged_total, "groups": group_report}


async def converge_natures(conn, *, threshold: float = 0.90) -> dict:
    """里程碑5: 本性收敛. 对有 nature_vector 的抽象概念, 按余弦收敛:
      - >=2 概念本性向量收敛 → 凝结 1 个 nature_concept, 相关概念 nature_concept_id 指向它
        (→ 这些概念之间成立"本性同源"强联系).
      - 单个未收敛 → 留作该概念自己的 nature, 不进 nature_concept 表.
    ★本性跨学科收敛 (同源即连, 不按 discipline 隔离 — 这正是本性维度的意义).
    空 nature → no-op (不报错).
    """
    rows = await conn.fetch(
        """SELECT concept_id, nature, nature_vector FROM aii.concept_onto
           WHERE nature_vector IS NOT NULL""")
    if len(rows) < 2:
        return {"natures": len(rows), "condensed": 0, "groups": []}

    cids = [r["concept_id"] for r in rows]
    natures = [r["nature"] for r in rows]
    vecs = np.asarray([[float(x) for x in r["nature_vector"]] for r in rows])
    groups = _union_groups(cids, vecs, threshold)

    condensed = 0
    report = []
    async with conn.transaction():
        for grp in groups:
            member_ids = [cids[i] for i in grp]
            centroid = np.mean(vecs[grp], axis=0)
            statement = next((natures[i] for i in grp if natures[i]), "(unspecified nature)")
            nc_id = await conn.fetchval(
                """INSERT INTO aii.nature_concept(statement, vector, member_concept_ids)
                   VALUES ($1, $2, $3::jsonb) RETURNING id""",
                statement, centroid.tolist(), json.dumps([str(m) for m in member_ids]),
            )
            await conn.execute(
                "UPDATE aii.concept_onto SET nature_concept_id = $1 WHERE concept_id = ANY($2)",
                nc_id, member_ids,
            )
            condensed += 1
            report.append({"nature_concept": str(nc_id), "members": len(member_ids)})

    return {"natures": len(rows), "condensed": condensed, "groups": report}
