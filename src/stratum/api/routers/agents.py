"""Agent execution — wires to omodul workflow functions."""

import asyncio
from datetime import date, timezone, datetime

from fastapi import APIRouter, Depends, HTTPException

from stratum.common import jwt_auth, user_agent_runs_dir, sha256_hex, ensure_dir

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

try:
    from omodul.daily_digest_workflow import (
        daily_digest_workflow,
        DailyDigestConfig,
        DailyDigestInput,
    )

    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False

_KNOWN_AGENTS = {"daily_digest", "knowledge_curator", "translation_worker"}


async def _run_daily_digest(params: dict, user_id: str) -> dict:
    out_dir = ensure_dir(user_agent_runs_dir(user_id))
    config = DailyDigestConfig(
        digest_date=date.today(),
        user_id_hash=sha256_hex(user_id)[:16],
        corpus_id=f"user_{user_id}",
        max_items=params.get("max_items", 20),
        llm_provider=params.get("llm_provider", "qwen3"),
        llm_model=params.get("llm_model", "qwen3-max"),
    )
    input_data = DailyDigestInput(
        recent_substrate_ids=params.get("recent_substrate_ids", []),
    )
    result = await asyncio.to_thread(
        daily_digest_workflow,
        config=config,
        input_data=input_data,
        output_dir=out_dir,
    )
    return {
        "agent_name": "daily_digest",
        "status": result.get("status", "unknown"),
        "findings": result["findings"].model_dump() if result.get("findings") else None,
        "report_fingerprint": result.get("fingerprint"),
        "error": result.get("error"),
    }


@router.post("/{agent_name}/run")
async def agent_run(agent_name: str, params: dict = {}, user_id: str = Depends(jwt_auth)):
    if agent_name not in _KNOWN_AGENTS:
        raise HTTPException(404, f"Unknown agent: {agent_name}")

    if not _HAS_OMODUL:
        return {
            "agent_name": agent_name,
            "status": "not_implemented",
            "message": "omodul not available in this environment",
        }

    if agent_name == "daily_digest":
        return await _run_daily_digest(params or {}, user_id)

    # knowledge_curator / translation_worker — stub (workflows not yet in omodul 1.14)
    return {
        "agent_name": agent_name,
        "status": "not_implemented",
        "message": f"{agent_name} workflow not yet available",
    }


@router.get("/{agent_name}/runs")
async def list_agent_runs(agent_name: str, user_id: str = Depends(jwt_auth)):
    from stratum.db import query

    return query(
        "SELECT id, status, started_at, completed_at FROM agent_runs "
        "WHERE user_id = %(uid)s AND agent_name = %(name)s "
        "ORDER BY started_at DESC",
        {"uid": user_id, "name": agent_name},
    )
