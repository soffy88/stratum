"""AII 概念存储层操作: 向量标记(方案A) + 概念语义归一 + 本性收敛.

依据 AII-CONCEPT-STORAGE-001 / AII-CONCEPT-NATURE-001.

★向量标记机制 = 方案A (硬分组), 实测结论 (m2_marker):
  概念向量存 concept_onto.vector / 本性向量存统一本性表 invariant.vector /
  KU 存 ku_onto.embedding. 比相似度时 WHERE/分组
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
            # ★把 dup 的 level/discipline/invariant_id 带到 canonical (canonical 空才补)
            d = await conn.fetchrow(
                """SELECT (array_agg(level) FILTER (WHERE level IS NOT NULL))[1] level,
                          (array_agg(discipline) FILTER (WHERE discipline IS NOT NULL))[1] discipline,
                          (array_agg(invariant_id) FILTER (WHERE invariant_id IS NOT NULL))[1] invariant_id
                   FROM aii.concept_onto WHERE concept_id = ANY($1)""", dup_ids)
            await conn.execute(
                """UPDATE aii.concept_onto SET
                     level=COALESCE(level,$2), discipline=COALESCE(discipline,$3),
                     invariant_id=COALESCE(invariant_id,$4)
                   WHERE concept_id=$1""",
                can_id, d["level"], d["discipline"], d["invariant_id"])
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


async def _converge_core(conn, llm, *, candidate_threshold: float, concurrency: int,
                         restrict_new) -> dict:
    """本性同一收敛核心: ★向量低阈筛候选 + LLM 判同一 → 并查集合并(传递性自动处理).

    操作对象 = 统一本性表 aii.invariant (单本性 is_concept=false + 本性概念 is_concept=true 同表).
    restrict_new=None        → 全量(所有对两两筛).
    restrict_new=set(ids)    → 增量(候选只取"≥1 端是新"的对, 跳过存量×存量——它们已converge过).
    ★传递性: 新 X 同时同源于存量 A、B → 并查集 {A,X,B} 同分量 → 三者合并成一个(成员全合并, 概念改指).
    ★red line: 余弦只筛候选, LLM 判 yes 才合并, 绝不靠余弦直接判同源. 跨学科不隔离. <2 行 no-op.
    """
    rows = await conn.fetch(
        "SELECT id, statement, vector, member_concept_ids FROM aii.invariant")
    n = len(rows)
    if n < 2:
        return {"invariants": n, "candidates": 0, "judged_same": 0, "merged": 0, "groups": []}

    ids = [r["id"] for r in rows]
    stmts = [r["statement"] for r in rows]

    def _members(v):
        v = json.loads(v) if isinstance(v, str) else (v or [])
        return [str(x) for x in v]
    members = [_members(r["member_concept_ids"]) for r in rows]
    vecs = np.asarray([[float(x) for x in r["vector"]] for r in rows])

    restrict = {str(x) for x in restrict_new} if restrict_new is not None else None
    # ① 向量低阈筛候选; 增量: 至少一端是新 (跳过存量×存量, 不重算)
    candidates: list[tuple] = []
    for i, j in combinations(range(n), 2):
        if restrict is not None and str(ids[i]) not in restrict and str(ids[j]) not in restrict:
            continue
        if _cos(vecs[i], vecs[j]) >= candidate_threshold:
            candidates.append((i, j))

    # ② LLM 判同源 (并发)
    sem = asyncio.Semaphore(concurrency)

    async def judge(i, j):
        async with sem:
            prompt = _INV_JUDGE_TMPL.format(a=stmts[i] or "", b=stmts[j] or "")
            try:
                resp = await llm(messages=[{"role": "user", "content": prompt}],
                                 system=_INV_JUDGE_SYS, max_tokens=60)
                same = _parse_same(resp)
            except Exception:
                same = False
            return (i, j, same)

    judged = await asyncio.gather(*[judge(i, j) for i, j in candidates]) if candidates else []
    yes_pairs = [(i, j) for i, j, same in judged if same]

    # ③ yes 对并查集 → 连通分量 → 挂载合并
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

    merged = 0
    report = []
    async with conn.transaction():
        for grp in groups:
            keep = max(grp, key=lambda i: len(members[i]))   # 成员最多的本性行作保留
            drop = [i for i in grp if i != keep]
            keep_id = ids[keep]
            drop_ids = [ids[i] for i in drop]
            all_members: list[str] = []
            for i in grp:
                for m in members[i]:
                    if m not in all_members:
                        all_members.append(m)
            # 被并行的概念 invariant_id 改指保留行 + keep 行更新 member/is_concept + 删被并行
            await conn.execute(
                "UPDATE aii.concept_onto SET invariant_id=$1 WHERE invariant_id = ANY($2)",
                keep_id, drop_ids)
            await conn.execute(
                "UPDATE aii.invariant SET member_concept_ids=$1::jsonb, is_concept=$2 WHERE id=$3",
                json.dumps(all_members), len(all_members) >= 2, keep_id)
            await conn.execute("DELETE FROM aii.invariant WHERE id = ANY($1)", drop_ids)
            merged += len(drop)
            cnames = await conn.fetch(
                "SELECT name, discipline FROM aii.concept_onto WHERE concept_id = ANY($1)",
                [int(m) for m in all_members])
            report.append({"statement": stmts[keep][:55],
                           "members": [f"{r['name']}({r['discipline']})" for r in cnames]})

    return {"invariants": n, "candidates": len(candidates), "judged_same": len(yes_pairs),
            "merged": merged, "groups": report}


async def converge_invariants(conn, llm, *, candidate_threshold: float = 0.45,
                              concurrency: int = 5) -> dict:
    """全量收敛 (首次建库 / 全量重算用): 所有 invariant 两两筛候选 O(N²)."""
    return await _converge_core(conn, llm, candidate_threshold=candidate_threshold,
                                concurrency=concurrency, restrict_new=None)


async def converge_invariants_incremental(conn, llm, new_invariant_ids, *,
                                          candidate_threshold: float = 0.45,
                                          concurrency: int = 5) -> dict:
    """增量收敛 (飞轮摄新书用): 只比 新×全量(含新), 跳过存量×存量(已converge), O(M×N).
    ★传递性由并查集处理: 新本性桥接两个存量本性 → 三者并查集同分量 → 合并成一个.
    new_invariant_ids: 本批新 invariant 的 id 列表.
    """
    return await _converge_core(conn, llm, candidate_threshold=candidate_threshold,
                                concurrency=concurrency, restrict_new=new_invariant_ids)


async def query_invariant_siblings(conn, concept_name: str) -> list[dict]:
    """本性同一查询: 给一个概念名, 返回与它【本性同一】(invariant-identity)的其他概念.

    逻辑: concept → invariant_id → 共享同一 invariant 节点的其他概念 → 排除自己.
    ★本性同一不单独建边/表 — 同一 invariant_id 即本性同一 (统一本性表的成员关系).
    例: query("边际成本") → [导数(math), 导函数(math)] (本性同一: 瞬时变化率, 跨学科).
    返回 [{"name":..., "discipline":...}], 无同一概念则空列表.
    """
    return [dict(r) for r in await conn.fetch(
        """SELECT c2.name, c2.discipline
           FROM aii.concept_onto c1
           JOIN aii.concept_onto c2 ON c1.invariant_id = c2.invariant_id
           WHERE c1.name = $1 AND c2.name <> c1.name
                 AND c1.invariant_id IS NOT NULL
           ORDER BY c2.discipline, c2.name""",
        concept_name)]


# ─────────────────────────────────────────────────────────────────────────────
# 决策记录: converge_invariants 暂【手动触发 + 待增量化】, 不接 auto_ingest 自动跑.
#   原因: (1) 现仅 2 本书, 手动可控; (2) 全量 converge 是 O(N²) 候选对 + 每对一次 LLM,
#         书多了成本爆炸. 接自动前需先设计【增量 converge】: 只比"新书 invariant ×
#         存量 invariant", 不全量重算 (新书 invariant 数 × 存量数, 而非 (总数)²).
#   触发点: 摄新书后, 需要时手动跑 converge_invariants; 增量版做好再接 auto_ingest.
# ─────────────────────────────────────────────────────────────────────────────
