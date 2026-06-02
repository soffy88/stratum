"""Scheduler builtin job definitions (Phase 15 P1-B1).

3 real workflows registered as cron jobs.
4 stub agents (translation_worker/reading_companion/lint_bot/audio_generator)
NOT registered — they return 501; running them on schedule would always fail.
reading_companion is manual-only (no cron).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from omodul import (
    DailyDigestConfig,
    DailyDigestInput,
    InboxConfig,
    InboxInput,
    WeeklyReviewConfig,
    WeeklyReviewInput,
    daily_digest_workflow,
    process_inbox_substrate,
    weekly_review_workflow,
)

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
    out_dir = _output_dir(user_id, name)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)

    if name == "daily_digest":
        from stratum.common import sha256_hex

        cfg = DailyDigestConfig(
            digest_date=str(now.date()),
            user_id_hash=sha256_hex(user_id)[:16],
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
        from stratum.common import sha256_hex

        cfg = InboxConfig(
            llm_provider="qwen3",
            llm_model="qwen3-max",
            user_id_hash=sha256_hex(user_id)[:16],
            corpus_id=f"user_{user_id}",
            file_path=Path(""),
            file_checksum="",
        )
        inp = InboxInput()
        return process_inbox_substrate(config=cfg, input_data=inp, output_dir=out_dir)

    return {"status": "failed", "error": f"Unknown builtin job: {name}"}
