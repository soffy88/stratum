#!/usr/bin/env python3
"""trajectory_logs 埋点助手 — 飞轮失败事件结构化落库(轻量, 失败静默)。

设计: 只记录失败/降级事件(成功不记, 防噪音); 任何异常吞掉, 绝不影响主流程。

用法(飞轮 asyncio 环境):
    from traj_log import traj_log
    await traj_log("misc", "synth", "llm_timeout", "ReadTimeout after 5 retries",
                   {"book": "xxx", "chapter": 3}, "failed")

表: aii.trajectory_logs(ts, flywheel, phase, failure_mode, error_sig, context, outcome)
"""
from __future__ import annotations

import asyncio
import os

import asyncpg

_DSN = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
_INSERT = (
    "INSERT INTO aii.trajectory_logs"
    " (flywheel, phase, failure_mode, error_sig, context, outcome)"
    " VALUES ($1, $2, $3, $4, $5::jsonb, $6)"
)


async def traj_log(
    flywheel: str,
    phase: str,
    failure_mode: str,
    error_sig: str,
    context: dict | None = None,
    outcome: str = "failed",
) -> None:
    """异步写一条轨迹(任何失败静默, 不抛给调用方)。"""
    try:
        conn = await asyncpg.connect(_DSN, timeout=5)
        try:
            await conn.execute(
                _INSERT,
                flywheel, phase, failure_mode,
                (error_sig or "")[:300],
                __import__("json").dumps(context or {}, ensure_ascii=False),
                outcome,
            )
        finally:
            await conn.close()
    except Exception:  # noqa: BLE001 — 埋点绝不影响主流程
        pass


def traj_log_sync(
    flywheel: str,
    phase: str,
    failure_mode: str,
    error_sig: str,
    context: dict | None = None,
    outcome: str = "failed",
) -> None:
    """同步版(非 asyncio 环境用)。"""
    try:
        asyncio.run(traj_log(flywheel, phase, failure_mode, error_sig, context, outcome))
    except Exception:  # noqa: BLE001
        pass
