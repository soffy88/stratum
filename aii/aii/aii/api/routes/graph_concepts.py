"""B仓知识网络可视化 — 视图1(概念判同审查) 只读接口。AII-BREPO-VIZ-SPEC-001 步骤1。

只读 rf.refined_concept / rf.refined_directed_edge / rf.decision_ledger, 不写 B仓任何表。
连接模式跟随 learning.py 的 REFINED_DSN 裸连接(asyncpg 一连接一库, 无池)。

risk_flag 判据(v1 实际能落地的部分, 详见实施计划里的数据缺口说明):
  - alias_count >= ALIAS_RISK_THRESHOLD: 真实可算, "某概念挂了一堆别名"是错合信号。
  - decision 命中低置信 verdict: refined_concept.decision_id 目前全为 NULL, 这段查询是
    防御性写好的, 现在不会命中任何数据, 一旦上游流程开始回填 decision_id 会自动生效。
  "跨discipline的合并"判据在 Layer1 现有 schema 下不可计算(discipline 是单一标签,
  refined_ku 没有学科字段可 join), 不在 v1 risk_flag 里实现。
"""

import json
import os

import asyncpg
import igraph as ig
import leidenalg
import networkx as nx
from fastapi import APIRouter, Query

from aii.api._envelope import success_response, error_response

router = APIRouter()

REFINED_DSN = os.getenv(
    "REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)

ALIAS_RISK_THRESHOLD = 3

# decision_ledger.verdict 里标记低置信/candidate 的关键词(关4/低置信路径), 目前
# refined_concept.decision_id 全为 NULL 故这条判据恒不命中, 见模块 docstring。
_LOW_CONFIDENCE_MARKERS = ("关4", "candidate", "低置信")


def _jsonb(v, default):
    """asyncpg 在这条 REFINED_DSN 连接上不解码 jsonb, 一律回原始字符串——跟随
    learning.py 的既有写法(`json.loads(v) if isinstance(v, str) else (v or default)`)。"""
    return json.loads(v) if isinstance(v, str) else (v or default)


def _is_low_confidence(verdict) -> bool:
    verdict = _jsonb(verdict, None)
    if not verdict:
        return False
    text = " ".join(str(v) for v in verdict.values())
    return any(m in text for m in _LOW_CONFIDENCE_MARKERS)


@router.get("/graph/concepts")
async def graph_concepts(
    discipline: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    risk_only: bool = False,
):
    conn = await asyncpg.connect(REFINED_DSN)
    try:
        rows = await conn.fetch(
            """
            SELECT c.concept_id, c.name, c.name_zh, c.discipline, c.aliases, c.discriminative,
                   c.decision_id,
                   jsonb_array_length(coalesce(c.aliases, '[]'::jsonb)) AS alias_count,
                   d.verdict
            FROM rf.refined_concept c
            LEFT JOIN rf.decision_ledger d ON d.decision_id = c.decision_id
            WHERE ($1::text IS NULL OR c.discipline = $1)
            ORDER BY alias_count DESC
            LIMIT $2
            """,
            discipline,
            limit,
        )

        nodes = []
        for r in rows:
            alias_count = r["alias_count"] or 0
            low_conf = _is_low_confidence(r["verdict"])
            risk_flag = alias_count >= ALIAS_RISK_THRESHOLD or low_conf
            if risk_only and not risk_flag:
                continue
            nodes.append(
                {
                    "id": r["concept_id"],
                    "label": r["name"],
                    "label_zh": r["name_zh"],
                    "discipline": r["discipline"],
                    "alias_count": alias_count,
                    "aliases": _jsonb(r["aliases"], []),
                    "risk_flag": risk_flag,
                    "discriminative": _jsonb(r["discriminative"], None),
                }
            )

        concept_ids = [n["id"] for n in nodes]
        edges = []
        if concept_ids:
            edge_rows = await conn.fetch(
                """
                SELECT edge_id, src_concept, dst_concept, relation_type, strength, grade
                FROM rf.refined_directed_edge
                WHERE src_concept = ANY($1::bigint[]) OR dst_concept = ANY($1::bigint[])
                """,
                concept_ids,
            )
            node_id_set = set(concept_ids)
            edges = [
                {
                    "id": e["edge_id"],
                    "source": e["src_concept"],
                    "target": e["dst_concept"],
                    "relation_type": e["relation_type"],
                    "strength": e["strength"],
                    "grade": e["grade"],
                }
                for e in edge_rows
                # 两端都在返回的节点集合里才保留边(risk_only 过滤后节点集合会变小)
                if e["src_concept"] in node_id_set and e["dst_concept"] in node_id_set
            ]
    finally:
        await conn.close()

    return success_response({"nodes": nodes, "edges": edges, "truncated": len(rows) >= limit})


def _normalize_discipline(d: str | None) -> str | None:
    """★2026-07-19 实测发现的数据缺口: rf.refined_concept.discipline 大多数取值
    根本不是干净的学科分类, 是 per-book/per-substrate 的哈希/ULID(如
    "econ_zh_2726f38224"/"01KVABDEXD2V985Q9GZWFWPERW"/"mankiw_principles_econ_10e"),
    只有少数(economics/math/physics/经济学/economics-law)是真学科标签。不归一的话,
    "cross_disc"会把"同一学科、不同书"错判成"跨学科"(实测: Scarcity/Demand Curve
    这些纯经济学概念全部被误判为 invariant_candidate=true)。

    这里只做粗归一(合并明显同义变体), 不是完整数据清洗——归一不到的哈希/ULID类
    值原样返回, 残余噪声仍在, cross_disc/invariant_candidate 因此只能当【弱信号】,
    比 God node 本身的中心性信号更不可靠, 使用时需要知道这层局限。
    """
    if not d:
        return None
    dl = d.lower()
    if "econ" in dl or "经济" in d or "mankiw" in dl:
        return "economics"
    if dl == "math" or "数学" in d:
        return "math"
    if "physic" in dl or "物理" in d:
        return "physics"
    if "law" in dl:
        return "law"
    return d


@router.get("/graph/god-nodes")
async def graph_god_nodes(
    min_centrality: float = Query(0.0, ge=0.0, le=1.0),
    cross_disc_only: bool = False,
    limit: int = Query(50, ge=1, le=500),
):
    """God node 检测(AII-KNOWLEDGE-FIRST-SPEC-001 改进一)——把可视化从"审查"升级为
    "本性路径B候选自动发现器"。★只是候选提示, 不是本性认定——高中心性≠有本性,
    是否真有本性仍走 AII-INVARIANT-LAYER-001 四关判据+三层互证+人工确认(原则二)。

    中心性必须在【全图】上算(不受 discipline/risk_only 过滤, 那是局部子集会算错),
    所以这里不接受 graph_concepts 的过滤参数, 直接查全部 concept+edge。

    disciplines 用邻居概念的 discipline 集合近似"跨学科"(Layer1 现有 schema 下,
    refined_ku 没有学科字段, 没法像 SPEC 设想的那样按 KU/超边算, 见 graph_concepts
    模块 docstring 同一条数据缺口)——概念本身的 discipline 是单一标签, 但如果它连接
    的邻居概念横跨多个学科, 这个概念本身就是"多学科都在用"的候选信号。★discipline
    原始值质量差(见 _normalize_discipline), cross_disc 只做过粗归一, 仍是弱信号。
    """
    conn = await asyncpg.connect(REFINED_DSN)
    try:
        concepts = await conn.fetch(
            "SELECT concept_id, name, name_zh, discipline FROM rf.refined_concept"
        )
        edges = await conn.fetch("SELECT src_concept, dst_concept FROM rf.refined_directed_edge")
    finally:
        await conn.close()

    disc_by_id = {c["concept_id"]: c["discipline"] for c in concepts}
    norm_disc_by_id = {cid: _normalize_discipline(d) for cid, d in disc_by_id.items()}
    g = nx.DiGraph()
    g.add_nodes_from(disc_by_id.keys())
    for e in edges:
        if e["src_concept"] in disc_by_id and e["dst_concept"] in disc_by_id:
            g.add_edge(e["src_concept"], e["dst_concept"])

    if g.number_of_nodes() == 0:
        return success_response({"god_nodes": [], "graph_size": 0})

    in_degree = dict(g.in_degree())
    # God node 直觉是"被连接的总量", 不特别区分方向——度中心性/介数在无向图上算。
    undirected = g.to_undirected()
    degree_centrality = nx.degree_centrality(undirected)
    betweenness = nx.betweenness_centrality(undirected)

    by_id = {c["concept_id"]: c for c in concepts}
    results = []
    for cid, dc in degree_centrality.items():
        if dc < min_centrality:
            continue
        own_disc = disc_by_id.get(cid)
        own_norm = norm_disc_by_id.get(cid)
        neighbor_norms = {norm_disc_by_id.get(n) for n in undirected.neighbors(cid)}
        neighbor_norms.discard(None)
        all_norms = neighbor_norms | ({own_norm} if own_norm else set())
        cross_disc = len(all_norms) >= 2
        if cross_disc_only and not cross_disc:
            continue
        c = by_id[cid]
        results.append(
            {
                "concept_id": cid,
                "label": c["name"],
                "label_zh": c["name_zh"],
                "discipline": own_disc,
                "centrality": round(dc, 4),
                "betweenness": round(betweenness.get(cid, 0.0), 4),
                "in_degree": in_degree.get(cid, 0),
                "disciplines": sorted(all_norms),
                # ★候选提示, 不是认定——见函数 docstring 红线。discipline 原始数据脏
                # (见 _normalize_discipline), 这是弱信号, 不是可靠的跨学科判据。
                "invariant_candidate": cross_disc,
            }
        )

    results.sort(key=lambda r: r["centrality"], reverse=True)
    return success_response({"god_nodes": results[:limit], "graph_size": g.number_of_nodes()})


@router.get("/graph/communities")
async def graph_communities(
    resolution: float = Query(1.0, gt=0.0, le=5.0),
    min_size: int = Query(2, ge=1),
):
    """Leiden 社区检测(AII-KNOWLEDGE-FIRST-SPEC-001 改进二)——★只读预览, 不写
    rf.refined_theme_kc / refined_kc_member。

    实施范围说明(2026-07-19 跟用户确认过): 这两张表目前是空的、完全没有任何 B仓
    管道往里写(不是"换算法", 是"从零建"), 且 SPEC 开头的全局红线是"三个改进都
    只读 B/C 仓数据"——而 SPEC §2 描述的"社区划分→写入refined_theme_kc"本身就
    跟这条红线矛盾。选择先做只读预览: 用 Leiden 现场算一遍社区划分给 Wiki 看,
    不落库、不需要 LLM 命名主题、不影响任何下游——真要把结果固化成 refined_theme_kc
    是后续单独决定的事(需要人工审过结果+决定主题命名方案, 见 SPEC §2.2 的
    "★social标签"和红线3)。

    ★resolution 不自动调优——社区好坏没有客观裁判(原则二: 留人), 这个参数只能
    由调用方(前端滑块/人工)传入手动试, 接口本身绝不基于任何反馈自动搜索最优值。

    ★孤立概念(无边)在 Leiden 下各自成单例社区, 不强行并入别的社区——跟"宁碎片
    不错合"的精神一致, min_size 过滤只是不在返回列表里展示太小的社区(仍然是
    "过滤展示", 不是"强行合并"), 单例社区被过滤掉时体现在 singleton_count 里,
    不是被这个接口悄悄抹除。
    """
    conn = await asyncpg.connect(REFINED_DSN)
    try:
        concepts = await conn.fetch(
            "SELECT concept_id, name, name_zh, discipline FROM rf.refined_concept"
        )
        edges = await conn.fetch(
            "SELECT src_concept, dst_concept, strength FROM rf.refined_directed_edge"
        )
    finally:
        await conn.close()

    id_list = [c["concept_id"] for c in concepts]
    idx_of = {cid: i for i, cid in enumerate(id_list)}
    by_id = {c["concept_id"]: c for c in concepts}

    g = ig.Graph()
    g.add_vertices(len(id_list))
    edge_pairs: list[tuple[int, int]] = []
    weights: list[float] = []
    seen: set[tuple[int, int]] = set()
    for e in edges:
        s, t = e["src_concept"], e["dst_concept"]
        if s not in idx_of or t not in idx_of or s == t:
            continue
        # 无向简单图: 同一对概念不管方向出现几次边, 只算一条(避免平行边重复计权)。
        key = tuple(sorted((idx_of[s], idx_of[t])))
        if key in seen:
            continue
        seen.add(key)
        edge_pairs.append(key)
        weights.append(float(e["strength"] or 1.0))
    g.add_edges(edge_pairs)
    if weights:
        g.es["weight"] = weights

    if g.vcount() == 0:
        return success_response(
            {"communities": [], "resolution": resolution, "total_concepts": 0, "singleton_count": 0}
        )

    partition = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        resolution_parameter=resolution,
        weights="weight" if weights else None,
        # ★固定 seed——Wiki 审查同一个 resolution 的结果应该是稳定的, 不能"刷新一下
        # 又变了", 那样没法审(实测不设 seed 时同参数连续调用会得到略微不同的划分,
        # modularity 相近但社区边界有差异)。resolution 本身仍是人工可调的旋钮,
        # 只是"给定 resolution → 结果确定", 不是自动调参, 不违反红线2。
        seed=42,
    )

    communities = []
    singleton_count = 0
    for comm_idx, member_indices in enumerate(partition):
        if len(member_indices) < 2:
            singleton_count += 1
        if len(member_indices) < min_size:
            continue
        members = [id_list[i] for i in member_indices]
        disciplines = sorted({by_id[m]["discipline"] for m in members if by_id[m]["discipline"]})
        communities.append(
            {
                "community_id": comm_idx,
                "size": len(members),
                "members": [
                    {"concept_id": m, "label": by_id[m]["name"], "label_zh": by_id[m]["name_zh"]}
                    for m in members
                ],
                "disciplines": disciplines,
            }
        )
    communities.sort(key=lambda c: c["size"], reverse=True)

    return success_response(
        {
            "communities": communities,
            "resolution": resolution,
            "total_concepts": len(id_list),
            "singleton_count": singleton_count,
            "modularity": round(partition.modularity, 4),
        }
    )


@router.get("/graph/themes")
async def graph_themes():
    """已固化主题(rf.refined_theme_kc, AII-KNOWLEDGE-FIRST-SPEC-001 改进二)的读接口
    ——供前端"按主题染色"视图用。★只读, 不写任何表(固化本身由 scripts/build_theme_kc.py
    离线跑, 这里只把固化结果连同概念归属吐给前端)。

    概念归属直接读 rf.refined_kc_concept(migrations/refined/0005)——那是 build_theme_kc.py
    固化当时如实写下的聚类产物。此前这里是"每次请求重跑一遍 Leiden, 再按 size 降序的
    位置去对齐 kc_id", 概念图一变就会静默错位染色(把 A 主题的颜色刷到 B 主题的概念上),
    唯一护栏"cluster数量==theme行数"挡不住"数量没变而边界变了"。现在不重算不对齐。

    ★stale 判据也随之变实: 不再是猜数量对不对得上, 而是看固化后概念图有没有新增概念/
    新增边(created_at 晚于主题固化时间)。有 → stale=true 提示重跑 build_theme_kc.py,
    但已有的染色仍然是固化当时的真实归属, 不是错位的猜测。
    """
    conn = await asyncpg.connect(REFINED_DSN)
    try:
        theme_rows = await conn.fetch(
            """
            SELECT kc_id, theme_name, theme_name_en, summary, summary_zh, source_books, created_at, grade
            FROM rf.refined_theme_kc
            WHERE is_current = true
            ORDER BY kc_id
            """
        )
        if not theme_rows:
            return success_response({"themes": [], "concept_theme": {}, "stale": False})

        kc_ids = [r["kc_id"] for r in theme_rows]
        member_rows = await conn.fetch(
            "SELECT kc_id, concept_id FROM rf.refined_kc_concept WHERE kc_id = ANY($1::bigint[])",
            kc_ids,
        )
        # 固化后新增的概念(还没被任何一版聚类覆盖)——不是错位, 是"这些点还没有主题"。
        newer_concepts = await conn.fetchval(
            "SELECT count(*) FROM rf.refined_concept WHERE created_at > $1",
            max(r["created_at"] for r in theme_rows if r["created_at"]),
        )
    finally:
        await conn.close()

    concept_theme: dict[int, int] = {}
    size_by_kc: dict[int, int] = {}
    for r in member_rows:
        concept_theme[r["concept_id"]] = r["kc_id"]
        size_by_kc[r["kc_id"]] = size_by_kc.get(r["kc_id"], 0) + 1

    # 有主题行却一条概念成员都没有 = 这批主题是 0005 迁移之前固化的旧数据, 概念归属
    # 当年没存下来。★不退回"重算+猜对齐"那条老路(那正是本次要拆掉的错位来源), 如实
    # 报 stale 并让 concept_theme 为空——宁可不染色, 不给可能错的颜色。
    legacy_no_members = not member_rows

    themes = [
        {
            "kc_id": r["kc_id"],
            "theme_name": r["theme_name"],
            "theme_name_en": r["theme_name_en"],
            "summary": r["summary"],
            "summary_zh": r["summary_zh"],
            "source_books": _jsonb(r["source_books"], []),
            "size": size_by_kc.get(r["kc_id"], 0),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "grade": r["grade"],
        }
        for r in theme_rows
    ]

    return success_response(
        {
            "themes": themes,
            "concept_theme": concept_theme,
            "stale": legacy_no_members or bool(newer_concepts),
            "stale_reason": (
                "主题KC固化于 rf.refined_kc_concept 之前, 概念归属未存——请重跑 scripts/build_theme_kc.py"
                if legacy_no_members
                else (
                    f"固化后新增了 {newer_concepts} 个概念, 尚未归入任何主题——可重跑 scripts/build_theme_kc.py"
                    if newer_concepts
                    else None
                )
            ),
        }
    )


@router.get("/graph/node/{concept_id}")
async def graph_node_detail(concept_id: int):
    conn = await asyncpg.connect(REFINED_DSN)
    try:
        row = await conn.fetchrow(
            """
            SELECT c.concept_id, c.name, c.name_zh, c.discipline, c.level, c.aliases,
                   c.discriminative, c.sources, c.decision_id, c.created_at,
                   d.decision_type, d.verdict, d.model
            FROM rf.refined_concept c
            LEFT JOIN rf.decision_ledger d ON d.decision_id = c.decision_id
            WHERE c.concept_id = $1
            """,
            concept_id,
        )
        if row is None:
            return error_response("NOT_FOUND", f"concept_id={concept_id} 不存在")

        edges = await conn.fetch(
            """
            SELECT edge_id, src_concept, dst_concept, relation_type, strength, grade
            FROM rf.refined_directed_edge
            WHERE src_concept = $1 OR dst_concept = $1
            """,
            concept_id,
        )
    finally:
        await conn.close()

    return success_response(
        {
            "id": row["concept_id"],
            "label": row["name"],
            "label_zh": row["name_zh"],
            "discipline": row["discipline"],
            "level": row["level"],
            "aliases": _jsonb(row["aliases"], []),
            "discriminative": _jsonb(row["discriminative"], None),
            "sources": _jsonb(row["sources"], None),
            "decision": (
                {
                    "decision_id": row["decision_id"],
                    "decision_type": row["decision_type"],
                    "verdict": _jsonb(row["verdict"], None),
                    "model": row["model"],
                }
                if row["decision_id"]
                else None
            ),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "edges": [
                {
                    "id": e["edge_id"],
                    "source": e["src_concept"],
                    "target": e["dst_concept"],
                    "relation_type": e["relation_type"],
                    "strength": e["strength"],
                    "grade": e["grade"],
                }
                for e in edges
            ],
        }
    )
