"""Scheduler builtin job definitions (Phase 15 P1-B1).

All 12 agents (3 omodul workflows + 5 Agent-class + researcher + 3 native) are
activated — no 501 stubs remain (obase v0.9.0 activated audio_generator TTS).

NOTE: BUILTIN_JOBS below is reference documentation only. Real scheduling is
DB-driven: users create rows in scheduled_jobs_sl (CRUD router keeps APScheduler
in sync via runtime.sync_job). New users get two native defaults seeded
automatically on first list (see scheduled_jobs.py `list_jobs`):
  - daily_digest_simple  08:00 Asia/Shanghai (日报, native, no omodul)
  - knowledge_lint       02:00 Asia/Shanghai (Lint, native, no omodul)
These are omodul-free so they work on any deployment.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# 3O 平台包仅部署于容器 /opt/platform（dev 副本在 /platform），本机可能没有。
# 必须保证 import 本模块不崩；平台缺失时 execute_builtin_job 返回 status='failed'。
try:
    from omodul.daily_digest_workflow import (
        DailyDigestConfig,
        DailyDigestInput,
        daily_digest_workflow,
    )
    from omodul.weekly_review_workflow import (
        WeeklyReviewConfig,
        WeeklyReviewInput,
        weekly_review_workflow,
    )
    from omodul.process_inbox_substrate import InboxConfig, InboxInput, process_inbox_substrate

    _HAS_OMODUL = True
except ImportError:  # pragma: no cover — 平台包仅部署于容器
    _HAS_OMODUL = False
    DailyDigestConfig = DailyDigestInput = daily_digest_workflow = None
    WeeklyReviewConfig = WeeklyReviewInput = weekly_review_workflow = None
    InboxConfig = InboxInput = process_inbox_substrate = None

BUILTIN_JOBS: list[dict[str, Any]] = [
    {
        "name": "daily_digest",
        "cron": "0 8 * * *",  # 每天 08:00 Asia/Shanghai
        "timezone": "Asia/Shanghai",
        "agent_name": "daily_digest",
        "config": {},
    },
    {
        "name": "weekly_review",
        "cron": "0 9 * * 1",  # 每周一 09:00 Asia/Shanghai
        "timezone": "Asia/Shanghai",
        "agent_name": "weekly_review",
        "config": {"time_window_days": 7},
    },
    {
        "name": "knowledge_curator",
        "cron": "0 */6 * * *",  # 每 6 小时
        "timezone": "Asia/Shanghai",
        "agent_name": "knowledge_curator",
        "config": {},
    },
]


def _output_dir(user_id: str, job_name: str) -> Path:
    return Path.home() / ".stratum" / "users" / user_id / "agent_runs" / job_name


def execute_builtin_job(job: dict[str, Any], user_id: str = "system") -> dict:
    """Run a builtin job synchronously. Called by APScheduler or run-now."""
    name = job["agent_name"]

    # 3 个内置 job 全部依赖 omodul 平台包——缺失时直接返回失败，不触碰文件系统
    if not _HAS_OMODUL:
        return {
            "status": "failed",
            "error": f"omodul platform package unavailable (no /opt/platform); job '{name}' requires it",
        }

    out_dir = _output_dir(user_id, name)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)

    if name == "daily_digest":
        from stratum.utils.user_id_hash import hash_user_id

        cfg = DailyDigestConfig(
            digest_date=str(now.date()),
            user_id_hash=hash_user_id(user_id),
            corpus_id=f"user_{user_id}",
            max_items=job.get("config", {}).get("max_items", 20),
            llm_provider="qwen3",
            llm_model="qwen3-max",
        )
        inp = DailyDigestInput(recent_substrate_ids=[])
        return daily_digest_workflow(config=cfg, input_data=inp, output_dir=out_dir)

    if name == "weekly_review":
        cfg = WeeklyReviewConfig(
            llm_provider="qwen3",
            llm_model="qwen3-max",
            time_window_days=job.get("config", {}).get("time_window_days", 7),
        )
        inp = WeeklyReviewInput(
            activities=[],
            window_start_utc=now - timedelta(days=7),
            window_end_utc=now,
        )
        return weekly_review_workflow(config=cfg, input_data=inp, output_dir=out_dir)

    if name == "knowledge_curator":
        from stratum.utils.user_id_hash import hash_user_id

        cfg = InboxConfig(
            llm_provider="qwen3",
            llm_model="qwen3-max",
            user_id_hash=hash_user_id(user_id),
            corpus_id=f"user_{user_id}",
            file_path=Path(""),
            file_checksum="",
        )
        inp = InboxInput()
        return process_inbox_substrate(config=cfg, input_data=inp, output_dir=out_dir)

    return {"status": "failed", "error": f"Unknown builtin job: {name}"}
