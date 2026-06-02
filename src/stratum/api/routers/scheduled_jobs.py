"""Scheduled jobs CRUD (Phase 15 P1-B2).

POST   /api/v1/scheduled-jobs          create
GET    /api/v1/scheduled-jobs          list user's jobs
PUT    /api/v1/scheduled-jobs/{id}     update (name / cron / enabled)
DELETE /api/v1/scheduled-jobs/{id}     hard-delete (no deleted_at in schema)
POST   /api/v1/scheduled-jobs/{id}/run-now   manual trigger
GET    /api/v1/scheduled-jobs/{id}/runs      run history
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import execute, insert, query, read, update

router = APIRouter(prefix="/api/v1/scheduled-jobs", tags=["scheduled_jobs"])


class JobCreate(BaseModel):
    name: str
    agent_name: str
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    max_items: int = 20


class JobUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    enabled: bool | None = None


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.post("")
async def create_job(body: JobCreate, user_id: str = Depends(jwt_auth)):
    jid = generate_ulid()
    insert(
        "scheduled_jobs",
        {
            "id": jid,
            "user_id": user_id,
            "name": body.name,
            "agent_name": body.agent_name,
            "cron_expression": body.cron_expression,
            "timezone": body.timezone,
            "enabled": body.enabled,
            "max_items": body.max_items,
            "created_at": now_utc(),
        },
    )
    return {"job_id": jid, "status": "created"}


@router.get("")
async def list_jobs(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT * FROM scheduled_jobs WHERE user_id = %(uid)s ORDER BY created_at DESC",
        {"uid": user_id},
    )


@router.get("/{job_id}")
async def get_job(job_id: str, user_id: str = Depends(jwt_auth)):
    job = read("scheduled_jobs", job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404, "Scheduled job not found")
    return job


@router.put("/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user_id: str = Depends(jwt_auth)):
    existing = read("scheduled_jobs", job_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "Scheduled job not found")
    changes = body.model_dump(exclude_none=True)
    if changes:
        update("scheduled_jobs", job_id, changes)
    return {"job_id": job_id, "status": "updated"}


@router.delete("/{job_id}")
async def delete_job(job_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("scheduled_jobs", job_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "Scheduled job not found")
    # Hard delete: scheduled_jobs has no deleted_at column
    execute(
        "DELETE FROM scheduled_jobs WHERE id = %(jid)s AND user_id = %(uid)s",
        {"jid": job_id, "uid": user_id},
    )
    return {"job_id": job_id, "status": "deleted"}


# ── Run-now + history ─────────────────────────────────────────────────────────


@router.post("/{job_id}/run-now")
async def run_job_now(job_id: str, user_id: str = Depends(jwt_auth)):
    """手动触发 — 复用 agents.agent_run 逻辑 (同步)."""
    job = read("scheduled_jobs", job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404, "Scheduled job not found")

    from stratum.api.routers.agents import agent_run

    return await agent_run(job["agent_name"], {}, user_id)


@router.get("/{job_id}/runs")
async def list_job_runs(job_id: str, user_id: str = Depends(jwt_auth)):
    """Return agent_runs triggered via this scheduled job's run-now or cron."""
    job = read("scheduled_jobs", job_id)
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404, "Scheduled job not found")
    return query(
        "SELECT * FROM scheduled_job_runs WHERE job_id = %(jid)s ORDER BY started_at DESC",
        {"jid": job_id},
        limit=50,
    )
