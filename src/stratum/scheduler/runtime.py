"""Live APScheduler instance for user-created scheduled_jobs_sl rows.

APScheduler was an installed-but-unused dependency; scheduled_jobs_sl rows were
pure CRUD state with no automatic trigger — cron_expression was decorative,
only POST .../run-now actually executed a job. This wires a real
AsyncIOScheduler into the FastAPI lifespan and keeps it in sync with the CRUD
routes (stratum/api/routers/scheduled_jobs.py calls sync_job/remove_job
directly on create/update/delete, rather than polling — immediate effect, no
staleness window).
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _job_id(job_id: str) -> str:
    return f"scheduled_jobs_sl:{job_id}"


async def _run_job(job_id: str, agent_name: str, user_id: str) -> None:
    from stratum.api.routers.agents import agent_run

    try:
        await agent_run(agent_name, {}, user_id)
    except Exception:
        log.exception("scheduled job %s (agent=%s user=%s) failed", job_id, agent_name, user_id)


def sync_job(job: dict) -> None:
    """Add or replace this job's APScheduler entry from its current DB row.
    No-ops (removes any existing entry) if disabled or the cron expression is invalid."""
    aps_id = _job_id(job["id"])
    if scheduler.get_job(aps_id):
        scheduler.remove_job(aps_id)

    if not job.get("enabled", True):
        return
    try:
        trigger = CronTrigger.from_crontab(
            job["cron_expression"], timezone=job.get("timezone") or "Asia/Shanghai"
        )
    except Exception:
        log.warning(
            "scheduled job %s has invalid cron_expression=%r, not scheduled",
            job["id"],
            job.get("cron_expression"),
        )
        return

    scheduler.add_job(
        _run_job,
        trigger=trigger,
        id=aps_id,
        args=[job["id"], job["agent_name"], job["user_id"]],
        replace_existing=True,
        misfire_grace_time=3600,  # a missed tick (e.g. container restart) still fires within the hour
    )


def remove_job(job_id: str) -> None:
    aps_id = _job_id(job_id)
    if scheduler.get_job(aps_id):
        scheduler.remove_job(aps_id)


async def load_all_enabled_jobs() -> int:
    """Called once at app startup — schedules every currently-enabled row."""
    from stratum.db import query

    rows = query("SELECT * FROM scheduled_jobs_sl WHERE enabled = true", limit=10000)
    for row in rows:
        sync_job(row)
    return len(rows)
