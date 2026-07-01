"""Scheduled jobs routes: CRUD + list runs."""
import os
import json
from typing import Optional
from datetime import datetime, timezone

import duckdb
import ulid as ulid_mod
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.scheduled_job import ScheduledJobDAO

router = APIRouter()


def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn


class CreateJobRequest(BaseModel):
    name: str
    agent_name: str
    agent_params: dict = {}
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    enabled: bool = True


class JobItem(BaseModel):
    id: str
    name: str
    agent_name: str
    cron_expression: str
    timezone: str
    enabled: bool
    created_at: Optional[datetime] = None


class UpdateJobRequest(BaseModel):
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    name: Optional[str] = None


@router.get("/scheduled_jobs")
async def list_jobs(request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    jobs = ScheduledJobDAO(db).list_jobs(corpus_id=corpus_id)
    items = [JobItem(id=j.id, name=j.name, agent_name=j.agent_name,
                     cron_expression=j.cron_expression, timezone=j.timezone,
                     enabled=j.enabled, created_at=j.created_at) for j in jobs]
    return {"items": items, "total": len(items)}


@router.post("/scheduled_jobs", response_model=JobItem)
async def create_job(req: CreateJobRequest, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    user_id = request.state.user_id
    job_id = str(ulid_mod.ULID())
    now = datetime.now(timezone.utc)
    db.execute("""
        INSERT INTO scheduled_jobs (id, user_id, corpus_id, name, agent_name, agent_params, cron_expression, timezone, enabled, notify_on_completion, notify_on_failure, max_runtime_seconds, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, FALSE, FALSE, 300, ?, ?)
    """, (job_id, user_id, corpus_id, req.name, req.agent_name, json.dumps(req.agent_params),
          req.cron_expression, req.timezone, req.enabled, now, now))
    return JobItem(id=job_id, name=req.name, agent_name=req.agent_name,
                   cron_expression=req.cron_expression, timezone=req.timezone,
                   enabled=req.enabled, created_at=now)


@router.put("/scheduled_jobs/{job_id}", response_model=JobItem)
async def update_job(job_id: str, req: UpdateJobRequest, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    # Verify ownership
    row = db.execute("SELECT id FROM scheduled_jobs WHERE id = ? AND corpus_id = ?", (job_id, corpus_id)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    sets, params = [], []
    if req.enabled is not None:
        sets.append("enabled = ?"); params.append(req.enabled)
    if req.cron_expression:
        sets.append("cron_expression = ?"); params.append(req.cron_expression)
    if req.name:
        sets.append("name = ?"); params.append(req.name)
    if sets:
        sets.append("updated_at = ?"); params.append(datetime.now(timezone.utc))
        params.append(job_id); params.append(corpus_id)
        db.execute(f"UPDATE scheduled_jobs SET {', '.join(sets)} WHERE id = ? AND corpus_id = ?", params)
    # Fetch updated
    jobs = ScheduledJobDAO(db).list_jobs(corpus_id=corpus_id)
    job = next((j for j in jobs if j.id == job_id), None)
    return JobItem(id=job.id, name=job.name, agent_name=job.agent_name,
                   cron_expression=job.cron_expression, timezone=job.timezone,
                   enabled=job.enabled, created_at=job.created_at)


@router.delete("/scheduled_jobs/{job_id}")
async def delete_job(job_id: str, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    row = db.execute("SELECT id FROM scheduled_jobs WHERE id = ? AND corpus_id = ?", (job_id, corpus_id)).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    db.execute("DELETE FROM scheduled_jobs WHERE id = ? AND corpus_id = ?", (job_id, corpus_id))
    return {"status": "deleted"}
