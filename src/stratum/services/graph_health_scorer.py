"""Graph Health Scorer — Connector 风格的知识图谱健康评分系统 (0-100 分).

对标 My Brain Is Full Crew Connector Agent 的图谱健康评分公式。

评分维度:
  1. 孤立率 (Orphan Rate) — 25% 权重
  2. 平均链接密度 (Link Density) — 20% 权重
  3. MOC 覆盖率 (MOC Coverage) — 20% 权重
  4. 聚类连通性 (Cluster Connectivity) — 15% 权重
  5. 死端率 (Dead-end Rate) — 10% 权重
  6. 双向链接率 (Reciprocal Link Rate) — 10% 权重

输出:
  - 总分 (0-100)
  - 各维度得分
  - Top 10 最活跃实体
  - Top 10 孤立实体
  - 可操作改进建议
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """单个评分维度的结果."""
    name: str
    weight: float
    raw_value: float
    score: float  # 0-100
    detail: str = ""


@dataclass
class GraphHealthReport:
    """完整的图谱健康报告."""
    timestamp: float
    total_score: float
    dimensions: list[DimensionScore]
    total_entities: int
    total_relations: int
    total_substrates: int
    orphan_count: int
    dead_end_count: int
    top_connected: list[dict[str, Any]]
    top_orphans: list[dict[str, Any]]
    clusters: list[dict[str, Any]]
    recommendations: list[str]
    trend: str = ""  # "improving" | "stable" | "declining"


# ── Dimension 1: Orphan Rate (孤立率) — 25% ──────────────────────────────────

def _score_orphan_rate(conn) -> DimensionScore:
    """计算孤立实体的比例。理想值 < 5%."""
    # 统计没有任何关系的实体数量
    orphan_rows = conn.execute("""
        SELECT COUNT(*) FROM graph_entities e
        WHERE NOT EXISTS (
            SELECT 1 FROM graph_relations r
            WHERE r.source_entity_id = e.id OR r.target_entity_id = e.id
        )
    """).fetchone()
    orphan_count = orphan_rows[0] if orphan_rows else 0

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM graph_entities"
    ).fetchone()
    total = total_rows[0] if total_rows else 0

    orphan_pct = (orphan_count / total * 100) if total > 0 else 0
    score = max(0, 100 - orphan_pct * 5)

    return DimensionScore(
        name="orphan_rate",
        weight=0.25,
        raw_value=orphan_pct,
        score=score,
        detail=f"{orphan_count}/{total} entities orphaned ({orphan_pct:.1f}%)",
    )


# ── Dimension 2: Link Density (链接密度) — 20% ──────────────────────────────

def _score_link_density(conn) -> DimensionScore:
    """计算平均每个实体的关系数。理想值 3-5."""
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM graph_entities"
    ).fetchone()
    total = total_rows[0] if total_rows else 0

    total_rel_rows = conn.execute(
        "SELECT COUNT(DISTINCT source_entity_id, target_entity_id) FROM graph_relations"
    ).fetchone()
    total_rels = total_rel_rows[0] if total_rel_rows else 0

    density = total_rels / total if total > 0 else 0

    # 3-5 最佳
    if 3 <= density <= 5:
        score = 100
    elif density < 3:
        score = max(0, density / 3 * 100)
    else:
        score = max(0, 100 - (density - 5) * 10)

    return DimensionScore(
        name="link_density",
        weight=0.20,
        raw_value=density,
        score=score,
        detail=f"{total_rels}/{total} relations ({density:.1f} per entity)",
    )


# ── Dimension 3: MOC Coverage (目录覆盖率) — 20% ─────────────────────────────

def _score_moc_coverage(conn) -> DimensionScore:
    """计算可从 MOC (Map of Content) 到达的实体比例。理想值 > 90%."""
    # MOC 实体: entity_type='moc' 或 name 包含 'MOC'/'index'/'map'
    moc_rows = conn.execute("""
        SELECT COUNT(*) FROM graph_entities
        WHERE entity_type IN ('moc', 'index', 'map')
           OR name ILIKE '%index%'
           OR name ILIKE '%overview%'
    """).fetchone()
    moc_count = moc_rows[0] if moc_rows else 0

    # 有 source_substrate_ids 的实体被认为是 "有组织归属" 的
    covered_rows = conn.execute("""
        SELECT COUNT(*) FROM graph_entities
        WHERE source_substrate_ids::text != '[]'
          AND source_substrate_ids IS NOT NULL
    """).fetchone()
    covered = covered_rows[0] if covered_rows else 0

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM graph_entities"
    ).fetchone()
    total = total_rows[0] if total_rows else 0

    coverage_pct = (covered / total * 100) if total > 0 else 0
    score = coverage_pct  # 直接映射

    return DimensionScore(
        name="moc_coverage",
        weight=0.20,
        raw_value=coverage_pct,
        score=score,
        detail=f"{covered}/{total} entities covered by MOCs ({coverage_pct:.1f}%)",
    )


# ── Dimension 4: Cluster Connectivity (聚类连通性) — 15% ─────────────────────

def _score_cluster_connectivity(conn) -> DimensionScore:
    """计算图的连通分量数。理想值 1 个连通分量."""
    # 使用简单的 BFS 计算连通分量数
    entity_rows = conn.execute(
        "SELECT id FROM graph_entities"
    ).fetchall()
    all_ids = {r[0] for r in entity_rows}

    if not all_ids:
        return DimensionScore(
            name="cluster_connectivity",
            weight=0.15,
            raw_value=0,
            score=100,
            detail="no entities",
        )

    # 构建邻接表
    adj: dict[str, set[str]] = {eid: set() for eid in all_ids}
    rel_rows = conn.execute(
        "SELECT source_entity_id, target_entity_id FROM graph_relations"
    ).fetchall()
    for src, tgt in rel_rows:
        if src in adj and tgt in adj:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # BFS 计算连通分量
    visited = set()
    clusters = []

    for eid in all_ids:
        if eid in visited:
            continue
        # BFS from eid
        queue = [eid]
        cluster = set()
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    queue.append(neighbor)
        clusters.append(cluster)

    num_clusters = len(clusters)
    giant_component = max(len(c) for c in clusters) if clusters else 0
    giant_pct = giant_component / len(all_ids) * 100 if all_ids else 100

    # 分数: 单分量 100 分，每个额外分量扣 10 分
    score = max(0, 100 - (num_clusters - 1) * 10)

    cluster_info = [
        {"size": len(c), "is_giant": len(c) == giant_component}
        for c in sorted(clusters, key=len, reverse=True)[:5]
    ]

    return DimensionScore(
        name="cluster_connectivity",
        weight=0.15,
        raw_value=num_clusters,
        score=score,
        detail=f"{num_clusters} clusters, giant={giant_component} ({giant_pct:.0f}%)",
    ), cluster_info


# ── Dimension 5: Dead-end Rate (死端率) — 10% ────────────────────────────────

def _score_dead_end(conn) -> DimensionScore:
    """计算只有入边没有出边的实体比例。理想值 < 10%."""
    dead_rows = conn.execute("""
        SELECT COUNT(*) FROM graph_entities e
        WHERE EXISTS (
            SELECT 1 FROM graph_relations r WHERE r.target_entity_id = e.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM graph_relations r WHERE r.source_entity_id = e.id
        )
    """).fetchone()
    dead_end_count = dead_rows[0] if dead_rows else 0

    total_rows = conn.execute(
        "SELECT COUNT(*) FROM graph_entities"
    ).fetchone()
    total = total_rows[0] if total_rows else 0

    dead_pct = (dead_end_count / total * 100) if total > 0 else 0
    score = max(0, 100 - dead_pct * 5)

    return DimensionScore(
        name="dead_end_rate",
        weight=0.10,
        raw_value=dead_pct,
        score=score,
        detail=f"{dead_end_count}/{total} dead-end entities ({dead_pct:.1f}%)",
    )


# ── Dimension 6: Reciprocal Link Rate (双向链接率) — 10% ─────────────────────

def _score_reciprocal(conn) -> DimensionScore:
    """计算双向关系的比例。理想值 > 50%."""
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM graph_relations"
    ).fetchone()
    total = total_rows[0] if total_rows else 0

    if total == 0:
        return DimensionScore(
            name="reciprocal_rate",
            weight=0.10,
            raw_value=0,
            score=0,
            detail="no relations",
        )

    # 双向: A→B 且 B→A
    reciprocal_rows = conn.execute("""
        SELECT COUNT(DISTINCT r1.source_entity_id, r1.target_entity_id)
        FROM graph_relations r1
        JOIN graph_relations r2
          ON r1.source_entity_id = r2.target_entity_id
         AND r1.target_entity_id = r2.source_entity_id
    """).fetchone()
    reciprocal_count = reciprocal_rows[0] if reciprocal_rows else 0
    reciprocal_pct = reciprocal_count / total * 100

    score = min(100, reciprocal_pct * 2)  # 50% → 100 分

    return DimensionScore(
        name="reciprocal_rate",
        weight=0.10,
        raw_value=reciprocal_pct,
        score=score,
        detail=f"{reciprocal_count}/{total} reciprocal ({reciprocal_pct:.1f}%)",
    )


# ── Top Connected Entities ───────────────────────────────────────────────────

def _top_connected(conn, limit: int = 10) -> list[dict[str, Any]]:
    """返回连接数最多的 Top-N 实体."""
    rows = conn.execute("""
        SELECT e.id, e.name, e.entity_type, e.mention_count,
               COUNT(DISTINCT r.id) AS relation_count
        FROM graph_entities e
        LEFT JOIN graph_relations r ON r.source_entity_id = e.id OR r.target_entity_id = e.id
        GROUP BY e.id, e.name, e.entity_type, e.mention_count
        HAVING COUNT(DISTINCT r.id) > 0
        ORDER BY relation_count DESC
        LIMIT %s
    """, (limit,)).fetchall()

    return [
        {
            "entity_id": r[0],
            "name": r[1],
            "type": r[2],
            "mention_count": r[3],
            "relation_count": r[4],
        }
        for r in rows
    ]


# ── Top Orphan Entities ──────────────────────────────────────────────────────

def _top_orphans(conn, limit: int = 10) -> list[dict[str, Any]]:
    """返回孤立实体的 Top-N (高 mention_count 优先建议)."""
    rows = conn.execute("""
        SELECT id, name, entity_type, mention_count
        FROM graph_entities
        WHERE NOT EXISTS (
            SELECT 1 FROM graph_relations r
            WHERE r.source_entity_id = id OR r.target_entity_id = id
        )
        ORDER BY mention_count DESC
        LIMIT %s
    """, (limit,)).fetchall()

    return [
        {
            "entity_id": r[0],
            "name": r[1],
            "type": r[2],
            "mention_count": r[3],
        }
        for r in rows
    ]


# ── Recommendations Generator ────────────────────────────────────────────────

def _generate_recommendations(dimensions: list[DimensionScore]) -> list[str]:
    """根据各维度得分生成可操作建议."""
    recs = []

    for d in dimensions:
        if d.score < 50:
            if d.name == "orphan_rate":
                recs.append(
                    f"[CRITICAL] 孤立率过高 ({d.raw_value:.1f}%) — 运行 graph_builder 重新提取实体关系"
                )
            elif d.name == "link_density":
                recs.append(
                    f"[HIGH] 链接密度偏低 ({d.raw_value:.1f}/实体) — 增加 KG 抽取粒度或降低置信度阈值"
                )
            elif d.name == "moc_coverage":
                recs.append(
                    f"[HIGH] MOC 覆盖率低 ({d.raw_value:.1f}%) — 确保新入库 substrate 的实体有明确归属"
                )
            elif d.name == "cluster_connectivity":
                recs.append(
                    f"[MEDIUM] 图谱分裂为 {int(d.raw_value)} 个独立簇 — 添加跨域桥梁关系"
                )
            elif d.name == "dead_end_rate":
                recs.append(
                    f"[LOW] 死端率偏高 ({d.raw_value:.1f}%) — 增加实体的外向关系"
                )
            elif d.name == "reciprocal_rate":
                recs.append(
                    f"[LOW] 双向链接率低 ({d.raw_value:.1f}%) — 双向关系增强语义一致性"
                )

    if not recs:
        recs.append("图谱健康状态良好，暂无紧急改进项")

    return recs


# ── Main Entry ───────────────────────────────────────────────────────────────

def compute_graph_health(
    user_id: str | None = None,
    include_clusters: bool = True,
) -> GraphHealthReport:
    """计算完整的知识图谱健康评分报告.

    Args:
        user_id: Optional user filter (not yet implemented)
        include_clusters: Whether to compute cluster connectivity (expensive BFS)

    Returns:
        GraphHealthReport with total score, dimension breakdowns, and recommendations.
    """
    with get_conn() as conn:
        # Compute all dimensions
        dim_orphan = _score_orphan_rate(conn)
        dim_density = _score_link_density(conn)
        dim_moc = _score_moc_coverage(conn)
        dim_dead = _score_dead_end(conn)
        dim_recip = _score_reciprocal(conn)

        if include_clusters:
            result = _score_cluster_connectivity(conn)
            dim_cluster = result[0]
            cluster_info = result[1]
        else:
            dim_cluster = DimensionScore(
                name="cluster_connectivity", weight=0.15, raw_value=1, score=100,
                detail="skipped",
            )
            cluster_info = []

        dimensions = [dim_orphan, dim_density, dim_moc, dim_cluster, dim_dead, dim_recip]

        # Weighted total
        total_score = sum(d.score * d.weight for d in dimensions)

        # Top connected & orphans
        top_connected = _top_connected(conn)
        top_orphans = _top_orphans(conn)

        # Stats
        total_entities = conn.execute("SELECT COUNT(*) FROM graph_entities").fetchone()[0]
        total_relations = conn.execute("SELECT COUNT(*) FROM graph_relations").fetchone()[0]
        total_substrates = conn.execute("SELECT COUNT(*) FROM substrates").fetchone()[0]

    # Generate recommendations
    recommendations = _generate_recommendations(dimensions)

    report = GraphHealthReport(
        timestamp=time.time(),
        total_score=round(total_score, 2),
        dimensions=dimensions,
        total_entities=total_entities,
        total_relations=total_relations,
        total_substrates=total_substrates,
        orphan_count=int(dim_orphan.raw_value * total_entities / 100) if total_entities else 0,
        dead_end_count=int(dim_dead.raw_value * total_entities / 100) if total_entities else 0,
        top_connected=top_connected,
        top_orphans=top_orphans,
        clusters=cluster_info,
        recommendations=recommendations,
    )

    logger.info(
        "graph_health: score=%.1f entities=%d relations=%d orphans=%d",
        total_score, total_entities, total_relations,
        int(dim_orphan.raw_value * total_entities / 100) if total_entities else 0,
    )
    return report


def compute_graph_health_dict(**kwargs) -> dict[str, Any]:
    """便捷版本: 返回 dict 而非 dataclass."""
    report = compute_graph_health(**kwargs)

    return {
        "timestamp": report.timestamp,
        "total_score": report.total_score,
        "dimensions": [
            {
                "name": d.name,
                "weight": d.weight,
                "raw_value": d.raw_value,
                "score": d.score,
                "detail": d.detail,
            }
            for d in report.dimensions
        ],
        "statistics": {
            "total_entities": report.total_entities,
            "total_relations": report.total_relations,
            "total_substrates": report.total_substrates,
            "orphan_count": report.orphan_count,
            "dead_end_count": report.dead_end_count,
        },
        "top_connected": report.top_connected[:10],
        "top_orphans": report.top_orphans[:10],
        "clusters": report.clusters[:5],
        "recommendations": report.recommendations,
        "trend": report.trend,
    }
