"""Agent execution — wires to omodul workflow functions and Agent classes.

Phase 15 P1-A (Wave 1):
  AGENT_REGISTRY: 3 real workflows + 4 NOT_IMPLEMENTED stubs (501)
Phase 15 P1-C (Wave 5, post omodul PR #1 merge):
  Activated 3 Agent-class agents: translation_worker / reading_companion / lint_bot
  Only audio_generator remains 501 (oprim.tts_synthesize not exported, no providers).
  Advisor-authorized name mapping (§7 stop-and-report, R-4 explicit auth):
    knowledge_curator → process_inbox_substrate (InboxConfig/InboxInput)
  All runs persisted to agent_runs table; GET /runs + GET /runs/{run_id} added.
"""

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

# LLM provider config — read from env, default to qwen3_dashscope (DASHSCOPE_API_KEY set).
# Valid oprim.llm.llm_call providers: "qwen3_dashscope", "claude".
# Set STRATUM_LLM_PROVIDER=claude to switch to Anthropic; future deepseek support: add to oprim.
_DEFAULT_LLM_PROVIDER: str = os.environ.get("STRATUM_LLM_PROVIDER", "qwen3_dashscope")
_DEFAULT_LLM_MODEL: str = os.environ.get("STRATUM_LLM_MODEL", "qwen-plus")

from stratum.changefeed import emit_event
from stratum.common import (
    ensure_dir,
    generate_ulid,
    jwt_auth,
    now_utc,
    sha256_hex,
    user_agent_runs_dir,
)
from stratum.db import insert, query, read, update

try:
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
    from omodul.knowledge.agents.base import AgentContext
    from omodul.knowledge.agents.builtin.lint_bot import LintBotAgent
    from omodul.knowledge.agents.builtin.reading_companion import ReadingCompanionAgent
    from omodul.knowledge.agents.builtin.translation_worker import TranslationWorkerAgent

    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Agents still unavailable — oprim external deps missing
NOT_IMPLEMENTED_AGENTS = {
    "audio_generator": "TTS oprim.tts_synthesize 未导出 + ProviderRegistry 0 providers, 等 oprim 经理人补",
}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ── Per-agent config builders ─────────────────────────────────────────────────

if _HAS_OMODUL:

    def _build_daily_digest(params: dict, user_id: str):
        cfg = params.get("config") or {}
        inp = params.get("input") or {}
        config = DailyDigestConfig(
            digest_date=cfg.get("digest_date") or str(date.today()),
            user_id_hash=sha256_hex(user_id)[:16],
            corpus_id=cfg.get("corpus_id") or f"user_{user_id}",
            max_items=cfg.get("max_items", 20),
            llm_provider=cfg.get("llm_provider", _DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", _DEFAULT_LLM_MODEL),
        )
        input_data = DailyDigestInput(
            recent_substrate_ids=inp.get("recent_substrate_ids", []),
        )
        return daily_digest_workflow, config, input_data

    def _build_weekly_review(params: dict, user_id: str):
        cfg = params.get("config") or {}
        inp = params.get("input") or {}
        now = _now_dt()
        config = WeeklyReviewConfig(
            llm_provider=cfg.get("llm_provider", _DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", _DEFAULT_LLM_MODEL),
            time_window_days=cfg.get("time_window_days", 7),
        )
        input_data = WeeklyReviewInput(
            activities=inp.get("activities", []),
            window_start_utc=inp.get("window_start_utc") or (now - timedelta(days=7)),
            window_end_utc=inp.get("window_end_utc") or now,
        )
        return weekly_review_workflow, config, input_data

    def _build_knowledge_curator(params: dict, user_id: str):
        cfg = params.get("config") or {}
        inp = params.get("input") or {}
        config = InboxConfig(
            llm_provider=cfg.get("llm_provider", _DEFAULT_LLM_PROVIDER),
            llm_model=cfg.get("llm_model", _DEFAULT_LLM_MODEL),
            user_id_hash=sha256_hex(user_id)[:16],
            corpus_id=cfg.get("corpus_id") or f"user_{user_id}",
            file_path=Path(cfg.get("file_path", "")),
            file_checksum=cfg.get("file_checksum", ""),
        )
        input_data = InboxInput(metadata_override=inp.get("metadata_override"))
        return process_inbox_substrate, config, input_data

    _BUILDERS = {
        "daily_digest": _build_daily_digest,
        "weekly_review": _build_weekly_review,
        "knowledge_curator": _build_knowledge_curator,
    }

    # Agent-class based agents (async run(params, context) → AgentResult)
    _AGENT_CLASSES: dict = {
        "translation_worker": TranslationWorkerAgent,
        "reading_companion": ReadingCompanionAgent,
        "lint_bot": LintBotAgent,
    }

else:
    _BUILDERS = {}
    _AGENT_CLASSES: dict = {}


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/{agent_name}/run")
async def agent_run(
    agent_name: str,
    params: dict = {},
    user_id: str = Depends(jwt_auth),
):
    if agent_name in NOT_IMPLEMENTED_AGENTS:
        raise HTTPException(501, NOT_IMPLEMENTED_AGENTS[agent_name])
    if agent_name not in _BUILDERS and agent_name not in _AGENT_CLASSES:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    if not _HAS_OMODUL:
        return {
            "agent_name": agent_name,
            "status": "not_implemented",
            "message": "omodul not available in this environment",
        }

    out_dir = ensure_dir(user_agent_runs_dir(user_id))
    run_id = generate_ulid()

    insert(
        "agent_runs",
        {
            "id": run_id,
            "user_id": user_id,
            "agent_name": agent_name,
            "params": params or {},
            "status": "running",
            "started_at": now_utc(),
        },
    )

    result: dict = {}
    final_status = "failed"
    try:
        if agent_name in _AGENT_CLASSES:
            # Agent-class path: async run(params, context) → AgentResult
            context = AgentContext(
                user_id=user_id,
                agent_run_id=run_id,
                invoked_at=_now_dt(),
            )
            agent = _AGENT_CLASSES[agent_name]()
            # Override LLM provider from env so agent doesn't use its hard-coded default
            agent.llm_provider = _DEFAULT_LLM_PROVIDER
            agent.llm_model = _DEFAULT_LLM_MODEL
            # Inject corpus_id so hybrid_search can scope to this user
            enriched_params = dict(params or {})
            enriched_params.setdefault("corpus_id", f"user_{user_id}")
            agent_result = await agent.run(enriched_params, context)
            final_status = "completed" if agent_result.success else "failed"
            citations = [
                {
                    "substrate_id": c.substrate_id,
                    "title": c.title,
                    "fragment_id": c.fragment_id,
                    "deep_link": c.deep_link,
                }
                for c in (agent_result.citations or [])
            ]
            result = {
                "status": final_status,
                "findings": agent_result.output,
                "citations": citations,
                "error": agent_result.error,
                "trace": [
                    {"step": s.step_num, "tool": s.tool_name, "duration_ms": s.duration_ms}
                    for s in (agent_result.trace or [])
                ],
            }
        else:
            # Workflow path: sync fn(config, input_data, output_dir) → dict
            workflow_fn, config, input_data = _BUILDERS[agent_name](params or {}, user_id)
            result = await asyncio.to_thread(
                workflow_fn, config=config, input_data=input_data, output_dir=out_dir
            )
            final_status = result.get("status", "failed")

        err = result.get("error")
        if isinstance(err, dict):
            err = err.get("error_message") or str(err)
        update(
            "agent_runs",
            run_id,
            {
                "status": final_status,
                "completed_at": now_utc(),
                "trace": result.get("trace"),
                "citations": result.get("citations"),
                "files_generated": result.get("files_generated"),
                "error": err,
            },
        )
        event_type = "agent_run_completed" if final_status == "completed" else "agent_run_failed"
        await emit_event(user_id, event_type, {"run_id": run_id, "agent_name": agent_name})
    except Exception as e:
        final_status = "failed"
        result = {"error": str(e)}
        update(
            "agent_runs",
            run_id,
            {"status": "failed", "completed_at": now_utc(), "error": str(e)},
        )
        await emit_event(
            user_id,
            "agent_run_failed",
            {"run_id": run_id, "agent_name": agent_name, "error": str(e)},
        )

    return {
        "run_id": run_id,
        "agent_name": agent_name,
        "status": final_status,
        "findings": result.get("findings").model_dump()
        if hasattr(result.get("findings"), "model_dump")
        else result.get("findings"),
        "report_fingerprint": result.get("fingerprint"),
        "citations": result.get("citations"),
        "error": result.get("error"),
    }


@router.get("/runs")
async def list_runs(agent: str | None = None, user_id: str = Depends(jwt_auth)):
    if agent:
        rows = query(
            "SELECT * FROM agent_runs WHERE user_id = $uid AND agent_name = $agent ORDER BY started_at DESC",
            {"uid": user_id, "agent": agent},
            limit=20,
        )
    else:
        rows = query(
            "SELECT * FROM agent_runs WHERE user_id = $uid ORDER BY started_at DESC",
            {"uid": user_id},
            limit=20,
        )
    return {"items": rows, "total": len(rows)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user_id: str = Depends(jwt_auth)):
    run = read("agent_runs", run_id)
    if not run or run.get("user_id") != user_id:
        raise HTTPException(404, "Agent run not found")
    return run


@router.get("/{agent_name}/runs")
async def list_agent_runs(agent_name: str, user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT id, status, started_at, completed_at FROM agent_runs "
        "WHERE user_id = $uid AND agent_name = $name ORDER BY started_at DESC",
        {"uid": user_id, "name": agent_name},
        limit=20,
    )
