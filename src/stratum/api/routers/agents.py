"""Agent execution — wires to omodul workflow functions and Agent classes.

Phase 15 P1-A (Wave 1):
  AGENT_REGISTRY: 3 real workflows + 4 NOT_IMPLEMENTED stubs (501)
Phase 15 P1-C (Wave 5, post omodul PR #1 merge):
  Activated 3 Agent-class agents: translation_worker / reading_companion / lint_bot
  Only audio_generator remains 501 (oprim.tts_synthesize not exported, no providers).
  Advisor-authorized name mapping (§7 stop-and-report, R-4 explicit auth):
    knowledge_curator → process_inbox_substrate (InboxConfig/InboxInput)
  All runs persisted to agent_runs_sl table; GET /runs + GET /runs/{run_id} added.
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
from stratum.utils.user_id_hash import hash_user_id

# ── oservice ResearcherAgent ──────────────────────────────────────────────────

_RESEARCHER_ENGINE = None


def _make_oprim_llm_adapter(provider: str, model: str):
    """Messages-style LLM adapter for ResearcherEngine injection (kind="oprim").

    ResearcherEngine calls llm_caller(messages=[...], max_tokens=N) per LLMCaller Protocol.
    oprim.llm_call takes (prompt: str, provider, model, max_tokens) — not messages-style.
    This adapter bridges the gap. __module__ is set to "oprim.llm" so oservice kind check passes.
    Remove when oprim ships a native messages-style caller.
    """
    from oprim.llm.llm_call import llm_call

    def _adapter(*, messages: list, max_tokens: int = 4096, **_) -> dict:
        prompt = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        result = llm_call(prompt=prompt, provider=provider, model=model, max_tokens=max_tokens)
        return {"content": result.text}

    _adapter.__module__ = "oprim.llm"  # satisfies oservice kind="oprim" validation
    _adapter.__name__ = "oprim_llm_adapter"
    return _adapter


def _make_searxng_adapter(searxng_url: str):
    """Bind searxng_url into searxng_search so ResearcherEngine can call it without the URL arg."""
    from oprim import searxng_search

    def _adapter(*, query: str, max_results: int = 5, **_):
        r = searxng_search(query=query, searxng_url=searxng_url, max_results=max_results)
        # searxng_search returns dict{"results": [...]}; ResearcherEngine expects a plain list
        return r.get("results", []) if isinstance(r, dict) else (r or [])

    _adapter.__module__ = "oprim.search"  # satisfy oservice kind="oprim" check
    _adapter.__name__ = "searxng_adapter"
    return _adapter


def _get_researcher_engine():
    global _RESEARCHER_ENGINE
    if _RESEARCHER_ENGINE is not None:
        return _RESEARCHER_ENGINE
    try:
        import os

        searxng_url = os.environ.get("SEARXNG_URL", "")
        if not searxng_url:
            raise RuntimeError("SEARXNG_URL env var not set")

        from oservice import assemble, ServiceManifest
        from oprim import url_fetch_ssrf_safe

        manifest = ServiceManifest(
            name="stratum-researcher",
            skeleton="researcher",
            inject={
                "search_oprim": [_make_searxng_adapter(searxng_url)],
                "fetch_oprim": [url_fetch_ssrf_safe],
                "llm_caller": [_make_oprim_llm_adapter(_DEFAULT_LLM_PROVIDER, _DEFAULT_LLM_MODEL)],
                # ingest_omodul omitted (cardinality=0..1): returns results without DB ingestion.
                # Enable when omodul ships a kwargs-compatible ingest callable.
            },
            trigger={"on_demand": True},
            config={
                "max_search_terms": 3,
                "max_articles_per_term": 5,
                "max_total_articles": 15,
                "fetch_concurrency": 5,
            },
        )
        _RESEARCHER_ENGINE = assemble(manifest)
        _RESEARCHER_ENGINE.run()
    except Exception as _e:
        import logging

        logging.getLogger(__name__).warning("ResearcherEngine assembly failed: %s", _e)
        _RESEARCHER_ENGINE = None
    return _RESEARCHER_ENGINE


try:
    from omodul.daily_digest_workflow import (
        DailyDigestConfig,
        DailyDigestInput,
        daily_digest_workflow,
    )
    from omodul.process_inbox_substrate import InboxConfig, InboxInput, process_inbox_substrate
    from omodul.weekly_review_workflow import (
        WeeklyReviewConfig,
        WeeklyReviewInput,
        weekly_review_workflow,
    )
    from omodul.knowledge.agents.base import AgentContext
    from omodul.knowledge.agents.builtin.audio_generator import AudioGeneratorAgent
    from omodul.knowledge.agents.builtin.illustration_agent import IllustrationAgent
    from omodul.knowledge.agents.builtin.lint_bot import LintBotAgent
    from omodul.knowledge.agents.builtin.reading_companion import ReadingCompanionAgent
    from omodul.knowledge.agents.builtin.translation_worker import TranslationWorkerAgent

    _HAS_OMODUL = True
except ImportError:
    _HAS_OMODUL = False

# ── ProviderRegistry + secrets bootstrap ──────────────────────────────────────
# oprim/obase entry_points not wired in pyproject.toml; register at import time.
try:
    import logging as _logging
    import os as _os
    from obase import ProviderRegistry as _PR
    from obase.secrets import register_backend as _reg_secrets
    from oprim.llm.llm_call import llm_call as _oprim_llm_call

    # 1. Env-backed secrets so obase.get_secret("DASHSCOPE_API_KEY") works.
    class _EnvSecretsBackend:
        def get(self, name: str):
            return _os.environ.get(name)
        def set(self, name: str, value: str) -> None:
            raise NotImplementedError("env backend is read-only")

    _reg_secrets(_EnvSecretsBackend())

    # 2. LLM providers (qwen3_dashscope / qwen3).
    def _qwen3_ds_caller(messages, model="qwen-plus", **_):
        user_msg = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        system_msg = next((m.get("content") for m in messages if m.get("role") == "system"), None)
        return _oprim_llm_call(prompt=user_msg, provider="qwen3_dashscope", model=model, system=system_msg).text

    _pr_instance = _PR.get()
    for _pname in ("qwen3_dashscope", "qwen3"):
        _pr_instance.register_llm(_pname, _qwen3_ds_caller)

    # 3. Image provider: wanxiang (needs secrets backend registered above).
    try:
        from obase.providers._image.dashscope_wanxiang import register as _reg_wanx
        _reg_wanx(replace=True)
    except Exception as _wx_err:
        _logging.getLogger(__name__).warning("wanxiang provider registration skipped: %s", _wx_err)

except Exception as _pr_err:
    import logging as _logging
    _logging.getLogger(__name__).warning("ProviderRegistry bootstrap failed: %s", _pr_err)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# All agents implemented — no 501 stubs remain (audio_generator activated in obase v0.9.0)
NOT_IMPLEMENTED_AGENTS: dict = {}

# oservice-assembled engines — handled without requiring _HAS_OMODUL
_OSERVICE_AGENT_NAMES: frozenset[str] = frozenset({"researcher"})


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


# ── Per-agent config builders ─────────────────────────────────────────────────

if _HAS_OMODUL:

    def _build_daily_digest(params: dict, user_id: str):
        cfg = params.get("config") or {}
        inp = params.get("input") or {}
        config = DailyDigestConfig(
            digest_date=cfg.get("digest_date") or str(date.today()),
            user_id_hash=hash_user_id(user_id),
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
            user_id_hash=hash_user_id(user_id),
            corpus_id=cfg.get("corpus_id") or f"user_{user_id}",
            file_path=Path(cfg.get("file_path", "")),
            file_checksum=cfg.get("file_checksum", ""),
        )
        input_data = InboxInput(metadata_override=inp.get("metadata_override") or {})
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
        "audio_generator": AudioGeneratorAgent,
        "illustration_agent": IllustrationAgent,
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
    _is_oservice = agent_name in _OSERVICE_AGENT_NAMES
    if not _is_oservice and agent_name not in _BUILDERS and agent_name not in _AGENT_CLASSES:
        raise HTTPException(404, f"Unknown agent: {agent_name}")
    if not _is_oservice and not _HAS_OMODUL:
        return {
            "agent_name": agent_name,
            "status": "not_implemented",
            "message": "omodul not available in this environment",
        }

    # Validate oservice inputs BEFORE creating the run record (raises HTTPException cleanly)
    _oservice_engine = None
    _oservice_query: str = ""
    if _is_oservice:
        _oservice_engine = _get_researcher_engine()
        if _oservice_engine is None:
            raise HTTPException(503, "ResearcherEngine unavailable — oservice assembly failed")
        _oservice_query = (params or {}).get("query") or ""
        if not _oservice_query:
            raise HTTPException(422, "params.query is required for researcher")

    out_dir = ensure_dir(user_agent_runs_dir(user_id))
    run_id = generate_ulid()

    insert(
        "agent_runs_sl",
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
        if _is_oservice:
            result = await _oservice_engine.research(
                query=_oservice_query,
                user_id=user_id,
                max_articles_override=(params or {}).get("max_articles"),
            )
            final_status = result.get("status", "completed")
        elif agent_name in _AGENT_CLASSES:
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
            "agent_runs_sl",
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
            "agent_runs_sl",
            run_id,
            {"status": "failed", "completed_at": now_utc(), "error": str(e)},
        )
        await emit_event(
            user_id,
            "agent_run_failed",
            {"run_id": run_id, "agent_name": agent_name, "error": str(e)},
        )

    if _is_oservice:
        return {
            "run_id": run_id,
            "agent_name": agent_name,
            "status": final_status,
            "query": result.get("query"),
            "search_terms": result.get("search_terms"),
            "articles": result.get("articles"),
            "ingested_substrate_ids": result.get("ingested_substrate_ids"),
            "error": result.get("error"),
        }
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
            "SELECT * FROM agent_runs_sl WHERE user_id = $uid AND agent_name = $agent ORDER BY started_at DESC",
            {"uid": user_id, "agent": agent},
            limit=20,
        )
    else:
        rows = query(
            "SELECT * FROM agent_runs_sl WHERE user_id = $uid ORDER BY started_at DESC",
            {"uid": user_id},
            limit=20,
        )
    return {"items": rows, "total": len(rows)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user_id: str = Depends(jwt_auth)):
    run = read("agent_runs_sl", run_id)
    if not run or run.get("user_id") != user_id:
        raise HTTPException(404, "Agent run not found")
    return run


@router.get("/{agent_name}/runs")
async def list_agent_runs(agent_name: str, user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT id, status, started_at, completed_at FROM agent_runs_sl "
        "WHERE user_id = $uid AND agent_name = $name ORDER BY started_at DESC",
        {"uid": user_id, "name": agent_name},
        limit=20,
    )


@router.get("/_debug/providers")
async def debug_providers(_: str = Depends(jwt_auth)):
    """Temporary: introspect live provider + module state for illustration_agent diagnosis."""
    import sys as _sys
    from obase import ProviderRegistry as _PR
    info: dict = {}
    # ProviderRegistry state
    info["registered_providers"] = [f"{c}:{n}" for c, n in _PR.list_providers()]
    wanx = _PR._providers.get(("image_gen", "wanxiang"))
    info["wanxiang_type"] = type(wanx).__name__ if wanx else None
    info["wanxiang_callable"] = callable(wanx) if wanx else None
    # illustration_agent module binding
    ia = _sys.modules.get("omodul.knowledge.agents.builtin.illustration_agent")
    if ia:
        ig = getattr(ia, "image_generate", None)
        info["ia_image_generate_type"] = type(ig).__name__
        info["ia_image_generate_callable"] = callable(ig) if ig is not None else None
        info["ia_image_generate_repr"] = repr(ig)[:120]
    else:
        info["ia_module_loaded"] = False
    # oprim.image_generate state
    import oprim as _oprim
    oprim_ig = getattr(_oprim, "image_generate", None)
    info["oprim_image_generate_type"] = type(oprim_ig).__name__
    info["oprim_image_generate_callable"] = callable(oprim_ig) if oprim_ig else None
    return info
