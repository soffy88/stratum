"""Stratum Scheduler — executes enabled scheduled jobs via APScheduler."""

import asyncio
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Ensure stratum package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from stratum.db import insert, query
from stratum.common import generate_ulid

DATA_DIR = Path(os.environ.get("STRATUM_DATA_DIR", "/data/stratum/scheduler"))

# ── Optional omodul imports ───────────────────────────────────────────────────
try:
    from omodul.knowledge.process_inbox import process_inbox

    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False

# ── Optional content poller ───────────────────────────────────────────────────
HEVI_CONTENT_REPO = os.environ.get("HEVI_CONTENT_REPO", "")


def _load_jobs() -> list[dict]:
    return query("SELECT * FROM scheduled_jobs WHERE enabled = TRUE", limit=500)


async def _execute_job(job: dict) -> None:
    job_id = job["id"]
    user_id = job.get("user_id", "system")
    agent_name = job.get("agent_name", "unknown")
    out_dir = DATA_DIR / "users" / user_id / "agent_runs"
    out_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(UTC).isoformat()
    status = "failed"
    error = None

    try:
        if not _HAS_OMODUL:
            raise RuntimeError("omodul not installed")

        # Route to correct agent
        if agent_name == "knowledge_curator":
            inbox_dir = DATA_DIR / "users" / user_id / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            result = await process_inbox(inbox_dir=inbox_dir)
            status = "completed"
        else:
            # Other agents not yet wired — mark as skipped
            status = "skipped"

    except Exception as exc:
        error = {"error_message": str(exc)}

    insert(
        "scheduled_job_runs",
        {
            "id": generate_ulid(),
            "job_id": job_id,
            "status": status,
            "started_at": started,
            "completed_at": datetime.now(UTC).isoformat(),
            "error": error,
        },
    )
    print(f"[scheduler] job={job_id} agent={agent_name} status={status}")


async def _poll_hevi_content() -> None:
    """Pull new Hevi content from git repo."""
    if not HEVI_CONTENT_REPO:
        return
    print(f"[scheduler] polling hevi content from {HEVI_CONTENT_REPO}")
    # Full implementation: git pull + parse markdown + upsert platform_content
    # Placeholder until oprim.content_git_poller is implemented


async def main() -> None:
    scheduler = AsyncIOScheduler()

    jobs = _load_jobs()
    for job in jobs:
        cron = job.get("cron_expression", "0 8 * * *")
        try:
            scheduler.add_job(
                _execute_job,
                CronTrigger.from_crontab(cron),
                args=[job],
                id=job["id"],
                replace_existing=True,
            )
        except Exception as e:
            print(f"[scheduler] failed to add job {job['id']}: {e}")

    # Content poller — every 5 minutes
    scheduler.add_job(_poll_hevi_content, CronTrigger.from_crontab("*/5 * * * *"))

    scheduler.start()
    print(f"[scheduler] started with {len(jobs)} user job(s)")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
