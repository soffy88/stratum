"""Agent execution — wires to omodul when available, stubs otherwise."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from stratum.common import jwt_auth, user_agent_runs_dir, ensure_dir

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# ── Optional omodul imports ───────────────────────────────────────────────────
try:
    from omodul.knowledge.agents.builtin.daily_digest import DailyDigestAgent
    from omodul.knowledge.agents.builtin.knowledge_curator import KnowledgeCuratorAgent
    from omodul.knowledge.agents.builtin.translation_worker import TranslationWorkerAgent
    from omodul.knowledge.agents.registry import get_agent

    _HAS_AGENTS = True
except ImportError:
    _HAS_AGENTS = False


async def _run_omodul_agent(agent_name: str, params: dict, user_id: str) -> dict:
    """Dispatch to omodul agent registry."""
    out_dir = ensure_dir(user_agent_runs_dir(user_id))
    try:
        agent_cls = get_agent(agent_name)
    except Exception:
        raise HTTPException(404, f"Unknown agent: {agent_name}")

    from omodul.knowledge.agents.base import AgentContext

    context = AgentContext(user_id=user_id, corpus_id=f"user_{user_id}")
    agent = agent_cls()
    result = await asyncio.to_thread(asyncio.run, agent.run(params, context))
    return {
        "agent_name": agent_name,
        "status": "completed",
        "output": result.output if hasattr(result, "output") else str(result),
        "citations": [c.model_dump() for c in (result.citations or [])]
        if hasattr(result, "citations")
        else [],
    }


@router.post("/{agent_name}/run")
async def agent_run(agent_name: str, params: dict = {}, user_id: str = Depends(jwt_auth)):
    _KNOWN = {
        "daily_digest",
        "knowledge_curator",
        "translation_worker",
        "lint_bot",
        "audio_generator",
        "reading_companion",
        "weekly_review",
    }
    if agent_name not in _KNOWN:
        raise HTTPException(404, f"Unknown agent: {agent_name}")

    if not _HAS_AGENTS:
        # omodul agents not installed — return informative stub
        return {
            "agent_name": agent_name,
            "status": "not_implemented",
            "message": "omodul agent runtime not yet available in this environment",
        }

    return await _run_omodul_agent(agent_name, params or {}, user_id)


@router.get("/{agent_name}/runs")
async def list_agent_runs(agent_name: str, user_id: str = Depends(jwt_auth)):
    from stratum.db import query

    return query(
        "SELECT id, status, started_at, completed_at FROM agent_runs "
        "WHERE user_id = %(uid)s AND agent_name = %(name)s "
        "ORDER BY started_at DESC",
        {"uid": user_id, "name": agent_name},
    )
