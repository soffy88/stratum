"""Knowledge Gap Analyzer — Seeker Missing Knowledge 模式的 Stratum 实现.

分析 KU 库在特定主题领域的覆盖缺口，推荐应创建的笔记.

功能:
  1. 领域覆盖分析 — 某主题下 KU 数量、深度、多样性
  2. 知识缺口发现 — 基于 L0/L1 层内容和 KG 关系推断缺失知识
  3. 过时内容标记 — 超过 90 天未更新的 KU 标记为过时
  4. 跨领域连接发现 — 识别可以建立桥梁的知识孤岛

对标 My Brain Is Full Crew Seeker Agent 的 Missing Knowledge Mode.
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
class GapAnalysis:
    """单一主题的知识缺口分析结果."""
    topic: str
    well_covered: list[dict[str, Any]]
    thin_coverage: list[dict[str, Any]]
    missing: list[dict[str, Any]]
    suggested_notes: list[dict[str, str]]
    total_ku: int
    health_score: float  # 0-100


# ── Topic Discovery ──────────────────────────────────────────────────────────

def discover_topics(top_k: int = 20) -> list[dict[str, Any]]:
    """从 KU 库中自动发现主题领域.

    方法:
      1. 从 graph_entities.entity_type 提取类型
      2. 从 substrate 的 source_path 提取目录结构
      3. 从 ku_layers 内容中提取高频主题词
    """
    topics = []

    with get_conn() as conn:
        # 1. Entity types as topic proxies
        type_rows = conn.execute("""
            SELECT entity_type, COUNT(*) AS cnt
            FROM graph_entities
            GROUP BY entity_type
            ORDER BY cnt DESC
            LIMIT %s
        """, (top_k // 2,)).fetchall()

        for ent_type, cnt in type_rows:
            topics.append({
                "topic": ent_type,
                "ku_count": cnt,
                "source": "entity_type",
            })

        # 2. Substrate source paths (directory structure)
        path_rows = conn.execute("""
            SELECT
                CASE
                    WHEN source_path LIKE '%math%' THEN 'mathematics'
                    WHEN source_path LIKE '%econ%' THEN 'economics'
                    WHEN source_path LIKE '%physics%' THEN 'physics'
                    WHEN source_path LIKE '%cs%' OR source_path LIKE '%computer%' THEN 'computer-science'
                    WHEN source_path LIKE '%bio%' OR source_path LIKE '%medicine%' THEN 'biology'
                    WHEN source_path LIKE '%chem%' THEN 'chemistry'
                    WHEN source_path LIKE '%phil%' THEN 'philosophy'
                    WHEN source_path LIKE '%hist%' THEN 'history'
                    WHEN source_path LIKE '%lang%' THEN 'linguistics'
                    ELSE 'general'
                END AS domain,
                COUNT(*) AS cnt
            FROM substrates
            WHERE deleted_at IS NULL
            GROUP BY domain
            ORDER BY cnt DESC
            LIMIT %s
        """, (top_k // 2,)).fetchall()

        for domain, cnt in path_rows:
            topics.append({
                "topic": domain,
                "ku_count": cnt,
                "source": "source_path",
            })

    # Deduplicate by topic name, prefer higher count
    unique: dict[str, dict] = {}
    for t in topics:
        key = t["topic"]
        if key not in unique or t["ku_count"] > unique[key]["ku_count"]:
            unique[key] = t

    return sorted(unique.values(), key=lambda x: x["ku_count"], reverse=True)


# ── Gap Analysis for Single Topic ────────────────────────────────────────────

def analyze_topic_gap(
    topic: str,
    include_suggestions: bool = True,
) -> GapAnalysis:
    """分析特定主题的知识覆盖情况.

    Args:
        topic: Subject/topic to analyze (e.g., "machine-learning", "calculus")
        include_suggestions: Whether to generate suggested notes

    Returns:
        GapAnalysis with covered/thin/missing breakdown.
    """
    analysis = GapAnalysis(
        topic=topic,
        well_covered=[],
        thin_coverage=[],
        missing=[],
        suggested_notes=[],
        total_ku=0,
        health_score=0,
    )

    with get_conn() as conn:
        # Find substrates related to this topic
        search_pattern = f"%{topic}%"

        # Substrates whose source_path or title matches the topic
        sub_rows = conn.execute("""
            SELECT s.id, s.title, s.source_path,
                   (SELECT COUNT(*) FROM substrate_layers sl
                    WHERE sl.substrate_id = s.id) AS layer_count,
                   s.updated_at
            FROM substrates s
            WHERE s.deleted_at IS NULL
              AND (s.title ILIKE %s OR s.source_path ILIKE %s)
            ORDER BY s.updated_at DESC
            LIMIT 50
        """, (search_pattern, search_pattern)).fetchall()

        analysis.total_ku = len(sub_rows)

        # Categorize by coverage depth
        for sub_id, title, path, layer_count, updated_at in sub_rows:
            item = {
                "id": sub_id,
                "title": title or "",
                "path": path or "",
                "layer_count": layer_count,
                "updated_at": str(updated_at) if updated_at else "",
            }

            if layer_count >= 2:
                analysis.well_covered.append(item)
            elif layer_count >= 1:
                analysis.thin_coverage.append(item)
            else:
                analysis.missing.append(item)

        # Calculate health score
        total = max(analysis.total_ku, 1)
        well_weight = len(analysis.well_covered) * 1.0
        thin_weight = len(analysis.thin_coverage) * 0.5
        analysis.health_score = min(100, (well_weight + thin_weight) / total * 100)

        # Stale content detection (90+ days)
        stale_ids = []
        for item in analysis.well_covered + analysis.thin_coverage:
            if item["updated_at"]:
                try:
                    from datetime import datetime, timezone, timedelta
                    upd = datetime.fromisoformat(item["updated_at"])
                    if upd.tzinfo is None:
                        upd = upd.replace(tzinfo=timezone.utc)
                    age = (datetime.now(timezone.utc) - upd).days
                    if age > 90:
                        stale_ids.append(item["id"])
                except Exception:
                    pass

        if stale_ids:
            analysis.missing.append({
                "id": "stale_count",
                "title": f"{len(stale_ids)} items > 90 days old",
                "path": "",
                "layer_count": 0,
                "updated_at": "",
            })

    # Generate suggested notes (LLM-free heuristic approach)
    if include_suggestions and analysis.total_ku > 0:
        analysis.suggested_notes = _suggest_missing_notes(topic, analysis, conn)

    logger.info(
        "knowledge_gap: topic=%s ku=%d well=%d thin=%d missing=%d score=%.0f",
        topic, analysis.total_ku,
        len(analysis.well_covered), len(analysis.thin_coverage),
        len(analysis.missing), analysis.health_score,
    )
    return analysis


def _suggest_missing_notes(
    topic: str,
    analysis: GapAnalysis,
    conn,
) -> list[dict[str, str]]:
    """基于启发式规则建议缺失笔记.

    逻辑:
      1. 检查同领域有 L2 (详细内容层) 但缺少 L1 (结构化概览) 的 KU
      2. 检查有关联实体但无交叉引用的 KU 对
      3. 建议 "桥梁笔记" 连接不同聚类
    """
    suggestions = []

    # 1. 缺少结构化概览的 KU
    if analysis.thin_coverage:
        for item in analysis.thin_coverage[:3]:
            suggestions.append({
                "title": f"[Bridge] {item['title'] or 'Topic Overview'} — Structured Overview",
                "purpose": f"为 {topic} 领域的 {item['title'] or '该笔记'} 生成 L1 结构化概览",
                "type": "enrichment",
            })

    # 2. 检查 KG 中与该 topic 相关的孤立实体
    orphan_rows = conn.execute("""
        SELECT name, entity_type, mention_count, source_substrate_ids
        FROM graph_entities
        WHERE entity_type ILIKE %s
          AND NOT EXISTS (
              SELECT 1 FROM graph_relations r
              WHERE r.source_entity_id = graph_entities.id
                 OR r.target_entity_id = graph_entities.id
          )
        ORDER BY mention_count DESC
        LIMIT 5
    """, (f"%{topic}%",)).fetchall()

    for name, etype, mc, sj in orphan_rows:
        suggestions.append({
            "title": f"[Connect] {name} — Link to {topic} Knowledge Graph",
            "purpose": f"将实体 '{name}' ({etype}, {mc} mentions) 加入 {topic} 知识图谱",
            "type": "connection",
        })

    # 3. 建议桥梁笔记 (连接两个不同的子主题)
    if len(analysis.well_covered) >= 2 and len(analysis.missing) >= 2:
        suggestions.append({
            "title": f"[Bridge] {topic} — Cross-Domain Integration",
            "purpose": f"连接 {topic} 领域内已覆盖和未覆盖的子主题",
            "type": "bridge",
        })

    return suggestions


# ── Comprehensive Gap Analysis ───────────────────────────────────────────────

def analyze_all_gaps(
    topic_filter: str | None = None,
    top_k: int = 20,
    include_suggestions: bool = True,
) -> dict[str, Any]:
    """对所有主题执行知识缺口分析.

    Args:
        topic_filter: Optional topic to filter (None = all topics)
        top_k: Number of top topics to analyze
        include_suggestions: Whether to generate note suggestions

    Returns:
        Comprehensive report with per-topic analysis and aggregate stats.
    """
    if topic_filter:
        topics = [{"topic": topic_filter, "ku_count": 0, "source": "manual"}]
    else:
        topics = discover_topics(top_k=top_k)

    analyses = []
    total_ku = 0
    total_score = 0

    for tp in topics:
        try:
            analysis = analyze_topic_gap(tp["topic"], include_suggestions=include_suggestions)
            analyses.append(analysis)
            total_ku += analysis.total_ku
            total_score += analysis.health_score
        except Exception as exc:
            logger.warning("knowledge_gap: failed for %s: %s", tp["topic"], exc)

    avg_score = total_score / len(analyses) if analyses else 0

    # Aggregate statistics
    all_well = sum(len(a.well_covered) for a in analyses)
    all_thin = sum(len(a.thin_coverage) for a in analyses)
    all_missing = sum(len(a.missing) for a in analyses)

    # Collect all suggestions
    all_suggestions = []
    for a in analyses:
        for s in a.suggested_notes:
            all_suggestions.append({
                "topic": a.topic,
                **s,
            })

    # Rank topics by health (ascending = most need improvement)
    weakest = sorted(analyses, key=lambda a: a.health_score)[:5]
    strongest = sorted(analyses, key=lambda a: a.health_score, reverse=True)[:5]

    return {
        "timestamp": time.time(),
        "topics_analyzed": len(analyses),
        "total_ku_analyzed": total_ku,
        "average_health_score": round(avg_score, 1),
        "aggregate_stats": {
            "well_covered": all_well,
            "thin_coverage": all_thin,
            "missing": all_missing,
        },
        "weakest_topics": [
            {
                "topic": a.topic,
                "score": round(a.health_score, 1),
                "ku_count": a.total_ku,
            }
            for a in weakest
        ],
        "strongest_topics": [
            {
                "topic": a.topic,
                "score": round(a.health_score, 1),
                "ku_count": a.total_ku,
            }
            for a in strongest
        ],
        "suggested_notes": all_suggestions[:20],
        "per_topic": [
            {
                "topic": a.topic,
                "health_score": round(a.health_score, 1),
                "ku_count": a.total_ku,
                "well_covered": len(a.well_covered),
                "thin_coverage": len(a.thin_coverage),
                "missing": len(a.missing),
                "suggestions": a.suggested_notes[:5],
            }
            for a in analyses
        ],
    }
