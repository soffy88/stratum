"""AII 概念存储层操作: 向量标记(方案A) + 概念语义归一 + 本性收敛.

依据 AII-CONCEPT-STORAGE-001 / AII-CONCEPT-NATURE-001.

★向量标记机制 = 方案A (硬分组), 实测结论 (m2_marker):
  概念向量存 concept_onto.vector / 本性存 concept_onto.invariant_vector(及
  invariant_concept.vector) / KU 存 ku_onto.embedding. 比相似度时 WHERE/分组
  只在同类型内比 → 跨类型永不参与计算 → 0 误判, 由构造保证, 无需调权重.
  (实测: 向量内追加标记维=实现B 需 M>=5 才拉开, 且会把同类相似度抬到 ~0.98
   摧毁语义归一所需的类内区分度 → 弃用.)

所有向量同一套 BGE-M3 1024 维 (oprim.vector_encode provider='default'),
与 ku_onto.embedding 同空间, 可直接比较.
"""
from __future__ import annotations

import asyncio
import json
import re
from itertools import combinations

import numpy as np
from oprim import vector_encode


def _cos(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _encode(texts: list[str]) -> np.ndarray:
    """同 KU 一套 1024 维向量 (带 concept 类型语义, 类型隔离靠存储位置=方案A)."""
    return np.asarray(vector_encode(texts=texts, provider="default"))


def _union_groups(items: list, vecs: np.ndarray, threshold: float, forbid=None) -> list[list[int]]:
    """对 vecs 按余弦 >= threshold 做并查集分组, 返回 size>=2 的组(下标).

    forbid(i,j) -> bool: 若返回 True 则禁止 i,j 合并(如不同学科的同名概念).
    """
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in combinations(range(n), 2):
        if forbid is not None and forbid(i, j):
            continue
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
    # 填 vector; discipline 用 COALESCE — ★保留路A的每概念 discipline, 只给没填的补书级默认
    for cid, vec in zip(cids, vecs):
        await conn.execute(
            "UPDATE aii.concept_onto SET vector = $1, discipline = COALESCE(discipline, $2) "
            "WHERE concept_id = $3",
            vec.tolist(), discipline, cid,
        )

    # link 数用于选 canonical (最中心的留)
    link_cnt = {r["concept_id"]: r["n"] for r in await conn.fetch(
        "SELECT concept_id, count(*) n FROM aii.ku_concept_onto GROUP BY 1")}

    # ★每概念 discipline → 禁止跨学科同名误合 (供给弹性 vs 需求弹性)
    disc_by_cid = {r["concept_id"]: r["discipline"] for r in await conn.fetch(
        "SELECT concept_id, discipline FROM aii.concept_onto WHERE concept_id = ANY($1)", cids)}
    disciplines = [disc_by_cid.get(c) for c in cids]

    def _forbid(i, j):
        a, b = disciplines[i], disciplines[j]
        return bool(a and b and a != b)

    groups = _union_groups(cids, vecs, threshold, forbid=_forbid)
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
            # ★把 dup 的 level/discipline/invariant/invariant_vector 带到 canonical (canonical 空才补)
            d = await conn.fetchrow(
                """SELECT (array_agg(level) FILTER (WHERE level IS NOT NULL))[1] level,
                          (array_agg(discipline) FILTER (WHERE discipline IS NOT NULL))[1] discipline,
                          (array_agg(invariant) FILTER (WHERE invariant IS NOT NULL))[1] invariant,
                          (array_agg(invariant_vector) FILTER (WHERE invariant_vector IS NOT NULL))[1] invariant_vector
                   FROM aii.concept_onto WHERE concept_id = ANY($1)""", dup_ids)
            await conn.execute(
                """UPDATE aii.concept_onto SET
                     level=COALESCE(level,$2), discipline=COALESCE(discipline,$3),
                     invariant=COALESCE(invariant,$4), invariant_vector=COALESCE(invariant_vector,$5)
                   WHERE concept_id=$1""",
                can_id, d["level"], d["discipline"], d["invariant"], d["invariant_vector"])
            await conn.execute(
                "DELETE FROM aii.concept_onto WHERE concept_id = ANY($1)", dup_ids)
            merged_total += len(dups)
            group_report.append({"canonical": can_name, "merged": [d[1] for d in dups]})

    return {"before": len(cids), "after": len(cids) - merged_total,
            "merged": merged_total, "groups": group_report}


_INV_JUDGE_SYS = ("You judge whether two stated invariants describe the SAME underlying intrinsic law "
                  "(the same 道 / necessary tendency) — possibly across different domains or languages. "
                  "You only say same=true when the intrinsic law is genuinely the same. Output valid JSON only.")

_INV_JUDGE_TMPL = """\
Two invariants (each = a concept's intrinsic LAW / necessary tendency, NOT its definition):

[A] {a}
[B] {b}

Do A and B describe the SAME underlying invariant (same 道), even if worded differently, in different
languages, or from different fields? Cross-domain sameness COUNTS — e.g. a derivative's "instantaneous
rate of change" and marginal cost's "change from one more unit" are the SAME invariant (rate of change
at a point). But merely sharing a topic is NOT enough — the intrinsic law itself must be the same
(e.g. "resources are limited, forcing trade-offs" vs "a function is smooth/differentiable" → different laws → false).

Output JSON: {{"same": true or false}}"""


def _parse_same(resp) -> bool:
    txt = ""
    for blk in resp.get("content", []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += blk.get("text", "")
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    if not m:
        return False
    try:
        return json.loads(m.group(0)).get("same") is True
    except Exception:
        return False


async def converge_invariants(conn, llm, *, candidate_threshold: float = 0.45,
                              concurrency: int = 5) -> dict:
    """里程碑5(升级): 本性同源 = ★向量低阈筛候选 + LLM 判同一 (复用 cross_chunk_link 套路).

    纯余弦判同源对跨学科太弱 (导数↔边际仅 0.517). 改为:
      ① invariant_vector 余弦 >= candidate_threshold(默认0.45) → 候选对 (只筛范围, 不判定).
      ② 每候选对 LLM 判 "是不是同一个道(intrinsic law)?" — yes/no.
      ③ LLM 判 yes 的对 → 并查集连通 → 每组凝结 1 个 invariant_concept,
         成员概念 invariant_concept_id 指向它 (本性同源连接). LLM 判 no → 不凝结.
    ★red line: 余弦只筛候选, LLM 判 yes 才凝结, 绝不靠余弦直接判同源.
    跨学科收敛 (同源即连, 不按 discipline 隔离). 空 invariant → no-op.
    """
    rows = await conn.fetch(
        """SELECT concept_id, name, invariant, invariant_vector FROM aii.concept_onto
           WHERE invariant_vector IS NOT NULL""")
    n = len(rows)
    if n < 2:
        return {"invariants": n, "candidates": 0, "judged_same": 0, "condensed": 0, "groups": []}

    cids = [r["concept_id"] for r in rows]
    names = [r["name"] for r in rows]
    invs = [r["invariant"] for r in rows]
    vecs = np.asarray([[float(x) for x in r["invariant_vector"]] for r in rows])

    # ① 向量低阈筛候选 (只筛范围)
    candidates = [(i, j) for i, j in combinations(range(n), 2)
                  if _cos(vecs[i], vecs[j]) >= candidate_threshold]

    # ② LLM 判同源 (并发)
    sem = asyncio.Semaphore(concurrency)

    async def judge(i, j):
        async with sem:
            prompt = _INV_JUDGE_TMPL.format(a=invs[i] or "", b=invs[j] or "")
            try:
                resp = await llm(messages=[{"role": "user", "content": prompt}],
                                 system=_INV_JUDGE_SYS, max_tokens=60)
                same = _parse_same(resp)
            except Exception:
                same = False
            return (i, j, same)

    judged = await asyncio.gather(*[judge(i, j) for i, j in candidates]) if candidates else []
    yes_pairs = [(i, j) for i, j, same in judged if same]

    # ③ yes 对并查集 → 连通分量 → 凝结
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for i, j in yes_pairs:
        parent[find(i)] = find(j)
    from collections import defaultdict
    comp = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)
    groups = [g for g in comp.values() if len(g) > 1]

    condensed = 0
    report = []
    async with conn.transaction():
        for grp in groups:
            member_ids = [cids[i] for i in grp]
            centroid = np.mean(vecs[grp], axis=0)
            statement = next((invs[i] for i in grp if invs[i]), "(unspecified invariant)")
            nc_id = await conn.fetchval(
                """INSERT INTO aii.invariant_concept(statement, vector, member_concept_ids)
                   VALUES ($1, $2, $3::jsonb) RETURNING id""",
                statement, centroid.tolist(), json.dumps([str(m) for m in member_ids]))
            await conn.execute(
                "UPDATE aii.concept_onto SET invariant_concept_id = $1 WHERE concept_id = ANY($2)",
                nc_id, member_ids)
            condensed += 1
            report.append({"statement": statement[:60], "members": [names[i] for i in grp]})

    return {"invariants": n, "candidates": len(candidates), "judged_same": len(yes_pairs),
            "condensed": condensed, "groups": report}
