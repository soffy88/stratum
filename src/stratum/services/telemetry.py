"""Telemetry — 可观测性指标 (对标 OpenViking Telemetry).

收集并暴露:
  - 检索轨迹统计 (命中率, 深度分布, token 消耗)
  - Layer 生成统计 (L0/L1 质量分布, 生成耗时)
  - Session 统计 (平均长度, 记忆提取量, token 消耗)
  - 目录树统计 (节点数, 深度分布)

Prometheus-compatible metrics endpoint available at /api/v1/metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)


def get_all_metrics() -> dict[str, Any]:
    """Collect all telemetry metrics."""
    metrics: dict[str, Any] = {}

    try:
        metrics["layers"] = _layer_metrics()
    except Exception as exc:
        metrics["layers"] = {"error": str(exc)}

    try:
        metrics["retrieval"] = _retrieval_metrics()
    except Exception as exc:
        metrics["retrieval"] = {"error": str(exc)}

    try:
        metrics["sessions"] = _session_metrics()
    except Exception as exc:
        metrics["sessions"] = {"error": str(exc)}

    try:
        metrics["memories"] = _memory_metrics()
    except Exception as exc:
        metrics["memories"] = {"error": str(exc)}

    try:
        metrics["directory"] = _directory_metrics()
    except Exception as exc:
        metrics["directory"] = {"error": str(exc)}

    metrics["collected_at"] = time.time()
    return metrics


def _layer_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        sl_count = conn.execute(
            "SELECT count(DISTINCT substrate_id) FROM substrate_layers WHERE layer='L0'"
        ).fetchone()[0]
        sl_total = conn.execute("SELECT count(*) FROM substrate_layers").fetchone()[0]
        kl_count = conn.execute(
            "SELECT count(DISTINCT ku_id) FROM ku_layers WHERE layer='L0'"
        ).fetchone()[0]
        kl_total = conn.execute("SELECT count(*) FROM ku_layers").fetchone()[0]

        # Token stats
        avg_l0_tokens = conn.execute(
            "SELECT COALESCE(AVG(token_count), 0) FROM substrate_layers WHERE layer='L0'"
        ).fetchone()[0]
        avg_l1_tokens = conn.execute(
            "SELECT COALESCE(AVG(token_count), 0) FROM substrate_layers WHERE layer='L1'"
        ).fetchone()[0]

    total_substrates = 0
    try:
        with get_conn() as conn:
            total_substrates = conn.execute("SELECT count(*) FROM substrates").fetchone()[0]
    except Exception:
        pass

    return {
        "substrates_with_layers": sl_count,
        "total_substrates": total_substrates,
        "coverage_pct": round(sl_count / max(total_substrates, 1) * 100, 1),
        "substrate_layer_rows": sl_total,
        "kus_with_layers": kl_count,
        "ku_layer_rows": kl_total,
        "avg_l0_tokens": round(float(avg_l0_tokens), 0),
        "avg_l1_tokens": round(float(avg_l1_tokens), 0),
    }


def _retrieval_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT count(*) FROM retrieval_trajectories").fetchone()[0]
        avg_ms = conn.execute(
            "SELECT COALESCE(AVG(total_ms), 0) FROM retrieval_trajectories"
        ).fetchone()[0]
        avg_results = conn.execute(
            "SELECT COALESCE(AVG(result_count), 0) FROM retrieval_trajectories"
        ).fetchone()[0]

        # Recent 100 trajectories
        recent = conn.execute(
            "SELECT total_ms, result_count FROM retrieval_trajectories ORDER BY created_at DESC LIMIT 100"
        ).fetchall()

    latencies = [r[0] for r in recent if r[0]]
    return {
        "total_queries": total,
        "avg_latency_ms": round(float(avg_ms), 1),
        "avg_result_count": round(float(avg_results), 1),
        "p50_latency_ms": sorted(latencies)[len(latencies)//2] if latencies else 0,
        "p95_latency_ms": sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0,
    }


def _session_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT count(*) FROM agent_sessions").fetchone()[0]
        active = conn.execute(
            "SELECT count(*) FROM agent_sessions WHERE status='active'"
        ).fetchone()[0]
        avg_messages = conn.execute(
            "SELECT COALESCE(AVG(message_count), 0) FROM agent_sessions"
        ).fetchone()[0]
        avg_commits = conn.execute(
            "SELECT COALESCE(AVG(commit_count), 0) FROM agent_sessions"
        ).fetchone()[0]
        total_archives = conn.execute("SELECT count(*) FROM session_archives").fetchone()[0]

    return {
        "total_sessions": total,
        "active_sessions": active,
        "avg_messages_per_session": round(float(avg_messages), 1),
        "avg_commits_per_session": round(float(avg_commits), 1),
        "total_archives": total_archives,
    }


def _memory_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT count(*) FROM long_term_memories").fetchone()[0]
        by_type = conn.execute(
            "SELECT memory_type, count(*) FROM long_term_memories GROUP BY memory_type"
        ).fetchall()
        avg_conf = conn.execute(
            "SELECT COALESCE(AVG(confidence), 0) FROM long_term_memories"
        ).fetchone()[0]

    return {
        "total_memories": total,
        "by_type": {r[0]: r[1] for r in by_type},
        "avg_confidence": round(float(avg_conf), 3),
    }


def _directory_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT count(*) FROM context_directory").fetchone()[0]
        by_type = conn.execute(
            "SELECT node_type, count(*) FROM context_directory GROUP BY node_type"
        ).fetchall()
        max_depth = conn.execute(
            "SELECT COALESCE(MAX(depth), 0) FROM context_directory"
        ).fetchone()[0]

    return {
        "total_nodes": total,
        "by_type": {r[0]: r[1] for r in by_type},
        "max_depth": max_depth,
    }


def format_prometheus(metrics: dict[str, Any]) -> str:
    """Format metrics as Prometheus exposition format."""
    lines = []

    # Layer metrics
    lm = metrics.get("layers", {})
    if isinstance(lm, dict) and "error" not in lm:
        lines.append(f'stratum_substrates_with_layers {lm.get("substrates_with_layers", 0)}')
        lines.append(f'stratum_total_substrates {lm.get("total_substrates", 0)}')
        lines.append(f'stratum_layer_coverage_pct {lm.get("coverage_pct", 0)}')
        lines.append(f'stratum_avg_l0_tokens {lm.get("avg_l0_tokens", 0)}')

    # Retrieval metrics
    rm = metrics.get("retrieval", {})
    if isinstance(rm, dict) and "error" not in rm:
        lines.append(f'stratum_total_queries {rm.get("total_queries", 0)}')
        lines.append(f'stratum_avg_latency_ms {rm.get("avg_latency_ms", 0)}')
        lines.append(f'stratum_p50_latency_ms {rm.get("p50_latency_ms", 0)}')

    # Session metrics
    sm = metrics.get("sessions", {})
    if isinstance(sm, dict) and "error" not in sm:
        lines.append(f'stratum_total_sessions {sm.get("total_sessions", 0)}')
        lines.append(f'stratum_active_sessions {sm.get("active_sessions", 0)}')

    # Memory metrics
    mm = metrics.get("memories", {})
    if isinstance(mm, dict) and "error" not in mm:
        lines.append(f'stratum_total_memories {mm.get("total_memories", 0)}')

    return "\n".join(lines) + "\n"
