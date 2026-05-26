"""Agent routes: run agent, list runs."""
import os
import json
from typing import Optional
from datetime import datetime

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.agent_run import AgentRunDAO

router = APIRouter()


def get_db():
    conn = duckdb.connect(os.path.expanduser("~/.stratum/meta.duckdb"))
    try:
        yield conn
    finally:
        conn.close()


class RunAgentRequest(BaseModel):
    params: dict = {}


class AgentRunItem(BaseModel):
    id: str
    agent_name: str
    status: str
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RunAgentResponse(BaseModel):
    agent_run: AgentRunItem
    message: str = "Agent execution is not available in this environment"


@router.post("/agents/{agent_name}/run", response_model=RunAgentResponse)
async def run_agent(agent_name: str, req: RunAgentRequest, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    user_id = request.state.user_id

    # In production, this would call omodul agent registry.
    # For now, return a stub indicating the agent would be invoked.
    import ulid as ulid_mod
    run_id = str(ulid_mod.ULID())
    now = datetime.utcnow()
    db.execute("""
        INSERT INTO agent_runs (id, user_id, corpus_id, agent_name, params, status, started_at, total_input_tokens, total_output_tokens, cost_usd)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, 0, 0, 0.0)
    """, (run_id, user_id, corpus_id, agent_name, json.dumps(req.params), now))

    return RunAgentResponse(
        agent_run=AgentRunItem(id=run_id, agent_name=agent_name, status="pending", started_at=now),
    )


@router.get("/agents/runs")
async def list_agent_runs(request: Request, agent: Optional[str] = None, limit: int = 20, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    runs = AgentRunDAO(db).list_runs(corpus_id=corpus_id, limit=limit)
    if agent:
        runs = [r for r in runs if r.agent_name == agent]
    items = [AgentRunItem(id=r.id, agent_name=r.agent_name, status=r.status,
                          output=r.output, started_at=r.started_at,
                          completed_at=r.completed_at, error_message=r.error_message) for r in runs]
    return {"items": items, "total": len(items)}
