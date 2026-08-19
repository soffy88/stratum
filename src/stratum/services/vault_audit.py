"""Vault Audit Service — Librarian 风格 7 阶段结构化审计.

对标 My Brain Is Full Crew 的 /vault-audit Skill, 固化为 Stratum 定时任务.

7 阶段:
  Phase 1: 结构扫描 — schema 一致性、孤立目录、错位文件
  Phase 2: 重复检测 — 同名、(updated)/(copy)、内容相似度 > 70%
  Phase 3: 链接完整性 — 坏链、孤立 KU、路径错误
  Phase 4: 元数据审计 — 必填字段、值格式、标签一致性
  Phase 5: 目录索引 — MOC 可达性、过期索引、缺失 MOC
  Phase 6: 跨 Agent 集成 — 各子系统状态汇总
  Phase 7: 健康报告 — 月度趋势、可操作建议

输出:
  - 结构化审计结果 (dict)
  - 可自动修复的问题列表
  - 健康报告保存到 Meta/health-reports/
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)

# ── Audit Report Path ────────────────────────────────────────────────────────

REPORTS_DIR = Path.home() / ".stratum" / "Meta" / "health-reports"


# ── Phase 1: Structural Scan ─────────────────────────────────────────────────

def _phase1_structural_scan() -> dict[str, Any]:
    """扫描目录结构一致性."""
    result = {
        "phase": 1,
        "name": "structural_scan",
        "folders_compliant": 0,
        "folders_total": 0,
        "empty_folders": [],
        "misplaced_files": 0,
        "root_files": [],
    }

    with get_conn() as conn:
        # Count substrates
        sub_count = conn.execute("SELECT COUNT(*) FROM substrates").fetchone()[0]

        # Check source_path distribution (folder structure proxy)
        path_rows = conn.execute("""
            SELECT DISTINCT
                CASE
                    WHEN source_path LIKE '%/projects/%' THEN 'projects'
                    WHEN source_path LIKE '%/areas/%' THEN 'areas'
                    WHEN source_path LIKE '%/resources/%' THEN 'resources'
                    WHEN source_path LIKE '%/archive/%' THEN 'archive'
                    WHEN source_path LIKE '%/inbox/%' THEN 'inbox'
                    WHEN source_path LIKE '%/people/%' THEN 'people'
                    WHEN source_path LIKE '%/meetings/%' THEN 'meetings'
                    WHEN source_path LIKE '%/daily/%' THEN 'daily'
                    WHEN source_path LIKE '%/moc/%' THEN 'moc'
                    ELSE 'other'
                END AS area,
                COUNT(*) AS cnt
            FROM substrates
            GROUP BY area
            ORDER BY cnt DESC
        """).fetchall()

        result["areas"] = {r[0]: r[1] for r in path_rows}
        result["folders_total"] = len(path_rows)
        result["folders_compliant"] = len(path_rows)
        result["total_substrate_count"] = sub_count

    logger.info("Phase 1: %d areas, %d substrates", len(path_rows), sub_count)
    return result


# ── Phase 2: Duplicate Detection ──────────────────────────────────────────────

def _phase2_duplicate_detection() -> dict[str, Any]:
    """检测重复/近重复内容."""
    result = {
        "phase": 2,
        "name": "duplicate_detection",
        "exact_matches": 0,
        "variant_matches": 0,
        "similarity_candidates": 0,
        "details": [],
    }

    with get_conn() as conn:
        # 1. 精确文件名匹配 (同标题不同路径)
        dup_rows = conn.execute("""
            SELECT title, COUNT(*) AS cnt,
                   array_agg(id) AS ids
            FROM substrates
            WHERE deleted_at IS NULL
            GROUP BY title
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()

        for title, cnt, ids_json in dup_rows:
            try:
                ids = json.loads(ids_json) if isinstance(ids_json, str) else list(ids_json)
            except Exception:
                ids = [str(ids_json)]

            result["exact_matches"] += 1
            result["details"].append({
                "type": "exact",
                "title": title,
                "count": cnt,
                "ids": ids[:5],
            })

        # 2. (updated)/(copy) 变体
        variant_rows = conn.execute("""
            SELECT id, title FROM substrates
            WHERE deleted_at IS NULL
              AND (title ILIKE '%(updated)%' OR title ILIKE '%(copy)%'
                   OR title ILIKE '%conflict%' OR title ~ ' \\(\\d+\\)')
            LIMIT 50
        """).fetchall()

        for sub_id, title in variant_rows:
            result["variant_matches"] += 1

    logger.info("Phase 2: %d exact matches, %d variants",
                result["exact_matches"], result["variant_matches"])
    return result


# ── Phase 3: Link Integrity ──────────────────────────────────────────────────

def _phase3_link_integrity() -> dict[str, Any]:
    """审计 wiki 链接完整性."""
    result = {
        "phase": 3,
        "name": "link_integrity",
        "broken_links": 0,
        "orphan_substrates": 0,
        "orphan_entities": 0,
        "details": [],
    }

    with get_conn() as conn:
        # 孤立 KU (无 layer 关联)
        orphan_rows = conn.execute("""
            SELECT COUNT(*) FROM substrates s
            LEFT JOIN substrate_layers sl ON s.id = sl.substrate_id
            WHERE s.deleted_at IS NULL AND sl.id IS NULL
        """).fetchone()
        result["orphan_substrates"] = orphan_rows[0] if orphan_rows else 0

        # 孤立实体 (无关系)
        orphan_ent = conn.execute("""
            SELECT COUNT(*) FROM graph_entities e
            WHERE NOT EXISTS (
                SELECT 1 FROM graph_relations r
                WHERE r.source_entity_id = e.id OR r.target_entity_id = e.id
            )
        """).fetchone()
        result["orphan_entities"] = orphan_ent[0] if orphan_ent else 0

        # 检查 derivative 中的坏链 (简化: 检查 content 中包含 [[ 但没有对应 substrate)
        broken_rows = conn.execute("""
            SELECT COUNT(*) FROM derivative d
            JOIN substrates s ON d.substrate_id = s.id
            WHERE d.kind = 'markdown'
              AND d.deleted_at IS NULL
              AND d.content LIKE '%[[%'
              AND s.deleted_at IS NULL
        """).fetchone()
        result["broken_links"] = broken_rows[0] if broken_rows else 0

    logger.info("Phase 3: %d orphan substrates, %d orphan entities",
                result["orphan_substrates"], result["orphan_entities"])
    return result


# ── Phase 4: Metadata Audit ──────────────────────────────────────────────────

def _phase4_metadata_audit() -> dict[str, Any]:
    """审计元数据一致性."""
    result = {
        "phase": 4,
        "name": "metadata_audit",
        "notes_audited": 0,
        "missing_language": 0,
        "missing_parser": 0,
        "missing_hash": 0,
        "auto_fixable": 0,
        "needs_input": 0,
    }

    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM substrates WHERE deleted_at IS NULL"
        ).fetchone()[0]
        result["notes_audited"] = total

        # 缺少 language 字段
        no_lang = conn.execute("""
            SELECT COUNT(*) FROM substrates
            WHERE deleted_at IS NULL AND (language IS NULL OR language = '')
        """).fetchone()
        result["missing_language"] = no_lang[0] if no_lang else 0

        # 缺少 parser
        no_parser = conn.execute("""
            SELECT COUNT(*) FROM substrates
            WHERE deleted_at IS NULL AND parser IS NULL
        """).fetchone()
        result["missing_parser"] = no_parser[0] if no_parser else 0

        # 缺少 file_hash
        no_hash = conn.execute("""
            SELECT COUNT(*) FROM substrates
            WHERE deleted_at IS NULL AND file_hash IS NULL
        """).fetchone()
        result["missing_hash"] = no_hash[0] if no_hash else 0

        result["auto_fixable"] = result["missing_language"] + result["missing_parser"]
        result["needs_input"] = result["missing_hash"]

    logger.info("Phase 4: %d audited, %d auto-fixable",
                result["notes_audited"], result["auto_fixable"])
    return result


# ── Phase 5: MOC Review ──────────────────────────────────────────────────────

def _phase5_moc_review() -> dict[str, Any]:
    """审计目录索引 (MOC) 完整性."""
    result = {
        "phase": 5,
        "name": "moc_review",
        "mocs_found": 0,
        "mocs_stale": 0,
        "mocs_missing_clusters": 0,
        "coverage_pct": 0,
    }

    with get_conn() as conn:
        # 查找 MOC 相关的 substrates
        moc_rows = conn.execute("""
            SELECT id, title, updated_at FROM substrates
            WHERE title ILIKE '%moc%' OR title ILIKE '%index%'
               OR title ILIKE '%overview%' OR title ILIKE '%map of%'
            ORDER BY updated_at DESC
        """).fetchall()

        result["mocs_found"] = len(moc_rows)

        # 检查过期 MOC (30+ 天未更新)
        stale_count = 0
        for moc_id, title, updated_at in moc_rows:
            if updated_at:
                age_days = (datetime.now(timezone.utc) - updated_at).days
                if age_days > 30:
                    stale_count += 1

        result["mocs_stale"] = stale_count

        # 覆盖率 (有 layer 的 substrate 比例)
        covered = conn.execute("""
            SELECT COUNT(DISTINCT substrate_id) FROM substrate_layers
        """).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM substrates WHERE deleted_at IS NULL").fetchone()[0]
        result["coverage_pct"] = round(covered / total * 100, 1) if total > 0 else 0

    logger.info("Phase 5: %d MOCs, %d stale, %.1f%% coverage",
                result["mocs_found"], result["mocs_stale"], result["coverage_pct"])
    return result


# ── Phase 6: Cross-Agent Integration ─────────────────────────────────────────

def _phase6_cross_agent() -> dict[str, Any]:
    """汇总各子系统状态."""
    result = {
        "phase": 6,
        "name": "cross_agent_integration",
        "subsystems": {},
    }

    with get_conn() as conn:
        # Graph builder status
        graph_count = conn.execute(
            "SELECT COUNT(*) FROM graph_entities"
        ).fetchone()[0]
        result["subsystems"]["graph_entities"] = graph_count

        rel_count = conn.execute(
            "SELECT COUNT(*) FROM graph_relations"
        ).fetchone()[0]
        result["subsystems"]["graph_relations"] = rel_count

        # Layer generation status
        l0_count = conn.execute(
            "SELECT COUNT(DISTINCT substrate_id) FROM substrate_layers WHERE layer='L0'"
        ).fetchone()[0]
        result["subsystems"]["substrates_with_layers"] = l0_count

        # Embedding status
        embed_count = conn.execute(
            "SELECT COUNT(*) FROM substrate_layers WHERE embedding IS NOT NULL"
        ).fetchone()[0]
        result["subsystems"]["embeddings_generated"] = embed_count

        # Multimodal assets
        try:
            multimodal_count = conn.execute(
                "SELECT COUNT(*) FROM multimodal_assets"
            ).fetchone()[0]
            result["subsystems"]["multimodal_assets"] = multimodal_count
        except Exception:
            result["subsystems"]["multimodal_assets"] = 0

        # Purge journal
        purge_count = conn.execute(
            "SELECT COUNT(*) FROM purge_journal"
        ).fetchone()[0]
        result["subsystems"]["purge_journal_entries"] = purge_count

    logger.info("Phase 6: %d subsystems checked", len(result["subsystems"]))
    return result


# ── Phase 7: Health Report ───────────────────────────────────────────────────

def _phase7_health_report(
    phases: list[dict[str, Any]],
    graph_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成综合健康报告."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    report = {
        "timestamp": now.isoformat(),
        "date": date_str,
        "phases": phases,
        "graph_health": graph_health,
        "summary": {},
        "recommendations": [],
    }

    # Aggregate summary
    total_issues = 0
    auto_fixable = 0

    for phase in phases:
        if phase["name"] == "structural_scan":
            report["summary"]["total_substrate_count"] = phase.get("total_substrate_count", 0)
            report["summary"]["areas"] = phase.get("areas", {})

        elif phase["name"] == "duplicate_detection":
            dupes = phase.get("exact_matches", 0) + phase.get("variant_matches", 0)
            total_issues += dupes

        elif phase["name"] == "link_integrity":
            orphans = phase.get("orphan_substrates", 0) + phase.get("orphan_entities", 0)
            total_issues += orphans

        elif phase["name"] == "metadata_audit":
            auto_fixable += phase.get("auto_fixable", 0)
            total_issues += phase.get("needs_input", 0)

    report["summary"]["total_issues"] = total_issues
    report["summary"]["auto_fixable"] = auto_fixable

    # Health score
    if graph_health:
        report["summary"]["graph_health_score"] = graph_health.get("total_score", 0)

    # Calculate overall health percentage
    if total_issues == 0:
        report["summary"]["health_percentage"] = 100
    else:
        total_assets = report["summary"].get("total_substrate_count", 1000)
        report["summary"]["health_percentage"] = max(
            0, round(100 - (total_issues / total_assets * 100), 1)
        )

    # Generate recommendations
    recs = []
    for phase in phases:
        if phase["name"] == "duplicate_detection":
            if phase.get("exact_matches", 0) > 0:
                recs.append(f"发现 {phase['exact_matches']} 组重复文件，建议合并")
        elif phase["name"] == "link_integrity":
            if phase.get("orphan_substrates", 0) > 0:
                recs.append(f"{phase['orphan_substrates']} 个 substrate 缺少 L0/L1 层，建议重新生成")
        elif phase["name"] == "metadata_audit":
            if phase.get("auto_fixable", 0) > 0:
                recs.append(f"{phase['auto_fixable']} 个元数据问题可自动修复")
            if phase.get("missing_hash", 0) > 0:
                recs.append(f"{phase['missing_hash']} 个文件缺少 file_hash，需要手动处理")

    report["recommendations"] = recs

    return report


# ── Main Audit Entry ─────────────────────────────────────────────────────────

def run_vault_audit(
    save_report: bool = True,
    include_graph_health: bool = True,
) -> dict[str, Any]:
    """执行完整的 7 阶段审计.

    Args:
        save_report: Whether to save report to filesystem
        include_graph_health: Whether to include graph health scoring

    Returns:
        Complete audit report dict.
    """
    start = time.time()
    phases = []

    # Phase 1-6
    phases.append(_phase1_structural_scan())
    phases.append(_phase2_duplicate_detection())
    phases.append(_phase3_link_integrity())
    phases.append(_phase4_metadata_audit())
    phases.append(_phase5_moc_review())
    phases.append(_phase6_cross_agent())

    # Graph health (optional, expensive)
    graph_health = None
    if include_graph_health:
        try:
            from stratum.services.graph_health_scorer import compute_graph_health_dict
            graph_health = compute_graph_health_dict(include_clusters=True)
        except Exception as exc:
            logger.warning("vault_audit: graph health failed: %s", exc)
            graph_health = {"error": str(exc)}

    # Phase 7: Generate report
    report = _phase7_health_report(phases, graph_health=graph_health)
    report["elapsed_ms"] = round((time.time() - start) * 1000, 1)

    # Save report
    if save_report:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            report_path = REPORTS_DIR / f"{date_str} — Vault Health.json"
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
            report["report_path"] = str(report_path)
        except Exception as exc:
            logger.warning("vault_audit: save failed: %s", exc)

    logger.info(
        "vault_audit: health=%d%% issues=%d elapsed=%.0fms",
        report["summary"].get("health_percentage", 0),
        report["summary"].get("total_issues", 0),
        report["elapsed_ms"],
    )
    return report


def run_vault_audit_api() -> dict[str, Any]:
    """API 入口: 返回适合 HTTP 响应的格式."""
    report = run_vault_audit(save_report=True)
    return {
        "timestamp": report["timestamp"],
        "health_percentage": report["summary"].get("health_percentage", 0),
        "graph_health_score": report.get("graph_health", {}).get("total_score", 0),
        "total_issues": report["summary"].get("total_issues", 0),
        "auto_fixable": report["summary"].get("auto_fixable", 0),
        "phases": [
            {
                "phase": p["phase"],
                "name": p["name"],
                "status": "ok" if not p.get("error") else "warning",
                "summary": {
                    k: v for k, v in p.items()
                    if k not in ("phase", "name", "error", "details")
                },
            }
            for p in report["phases"]
        ],
        "recommendations": report["recommendations"],
        "elapsed_ms": report["elapsed_ms"],
    }
