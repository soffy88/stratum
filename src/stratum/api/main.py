"""Stratum Service Layer — FastAPI application.

Deployed as the `stratum-sl` container on port 9304 (this module's own comment
historically said 9303 — that was aspirational/stale; 9304 is what's actually
wired in deploy/docker-compose.yml and Dockerfile.sl). http_api/app.py remains
on 9302 as `stratum-api`.

Frontend routing (stratum-web/next.config.*, checked in that order):
  /api/aii/:path*  -> AII backend (:8101)
  /api/v1/:path*   -> this app (:9304) — the actively-developed surface;
                       nearly everything (documents, graph, feeds, billing,
                       agents SPEC2, etc.) lives here.
  /api/:path*      -> http_api/app.py (:9302) — catch-all fallback. Still load-
                       bearing for /api/auth/* (register/login/refresh — this
                       app has no auth routes at all) and /api/search (the
                       live search page calls this, not /api/v1/search).

Both apps also define modules named notes/agents/substrates/search/
scheduled_jobs — same names, materially different (simpler) implementations,
mounted at genuinely disjoint URL prefixes so there's no live routing
collision. But it's a real duplicate-name trap for anyone editing by filename
alone: check the prefix, not just the module name. Full consolidation onto one
app was assessed and deliberately deferred — http_api's /api/search is
actively used by the live search page today, so merging isn't a drop-in
rename; it needs a real migration pass with frontend verification, not an
ad-hoc edit.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from stratum.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from stratum.api.mcp import mcp_app
from stratum.db.run_migrations import run_migrations


def _register_providers() -> None:
    """Register 3O providers (LLM + TTS + image_gen) with obase ProviderRegistry at startup."""
    try:
        from obase.provider_registry import ProviderRegistry
        from oprim.llm.llm_call import llm_call

        import os, httpx as _httpx

        _ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://172.17.0.1:11435")
        _ollama_model = os.environ.get("STRATUM_LLM_MODEL", "qwen3.5:9b")

        def _qwen3(messages, **_):
            resp = _httpx.post(
                f"{_ollama_base}/api/chat",
                json={"model": _ollama_model, "messages": messages, "stream": False},
                timeout=300.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

        # replace=True: override oprim's DashScope auto-registration via entry points
        ProviderRegistry.register("llm", "qwen3", _qwen3, replace=True)
    except Exception:
        pass  # graceful — workflows fall back to failed status without LLM

    try:
        # obase v0.9.0: register edge_tts (TTS) + wanxiang (image_gen) providers.
        # Requires secrets backend so DASHSCOPE_API_KEY is readable by obase.secrets.
        import os

        from obase.providers import register_default_providers
        from obase.secrets import register_backend
        from obase.secrets.backends.env_file import EnvFileBackend

        env_path = os.environ.get("STRATUM_ENV_PATH", "/home/soffy/.config/keys/.env")
        if os.path.exists(env_path):
            register_backend(EnvFileBackend(env_path))
        register_default_providers()
    except Exception:
        pass  # graceful — audio/image agents fall back to failed status without providers


async def _feed_tracker_loop() -> None:
    """Run FeedTrackerEngine tick every hour. Errors are logged, never propagated."""
    from stratum.services.feed_tracker_service import run_feed_tracker_tick
    import logging

    log = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(3600)
        try:
            await run_feed_tracker_tick()
        except Exception:
            log.exception("feed_tracker_loop tick failed")


async def _folder_watcher_loop() -> None:
    from stratum.services.folder_watcher_service import folder_watcher_loop
    import logging as _log

    _l = _log.getLogger(__name__)
    try:
        await folder_watcher_loop()
    except Exception:
        _l.exception("folder_watcher_loop crashed")


async def _channel_watcher_loop() -> None:
    from stratum.services.channel_watcher_service import channel_watcher_loop
    import logging as _log

    _l = _log.getLogger(__name__)
    try:
        await channel_watcher_loop()
    except Exception:
        _l.exception("channel_watcher_loop crashed")


async def _source_watcher_loop() -> None:
    from stratum.services.source_watcher_service import source_watcher_loop
    import logging as _log

    _l = _log.getLogger(__name__)
    try:
        await source_watcher_loop()
    except Exception:
        _l.exception("source_watcher_loop crashed")


async def _aii_feedback_loop() -> None:
    from stratum.services.aii_feedback_service import aii_feedback_loop
    import logging as _log

    _l = _log.getLogger(__name__)
    try:
        await aii_feedback_loop()
    except Exception:
        _l.exception("aii_feedback_loop crashed")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    run_migrations()  # 启动时自动建表
    _register_providers()
    task = asyncio.create_task(_feed_tracker_loop())
    fw_task = asyncio.create_task(_folder_watcher_loop())
    cw_task = asyncio.create_task(_channel_watcher_loop())
    sw_task = asyncio.create_task(_source_watcher_loop())
    aii_task = asyncio.create_task(_aii_feedback_loop())

    from stratum.scheduler.runtime import scheduler, load_all_enabled_jobs

    n_jobs = await load_all_enabled_jobs()
    scheduler.start()
    logging.getLogger(__name__).info("scheduled_jobs_sl: %d job(s) loaded into APScheduler", n_jobs)

    yield
    task.cancel()
    fw_task.cancel()
    cw_task.cancel()
    sw_task.cancel()
    aii_task.cancel()
    scheduler.shutdown(wait=False)


app = FastAPI(title="Stratum Service Layer", version="0.5.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://stratum.kanpan.co"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_mw(request, call_next):
    from stratum.middleware.rate_limit import rate_limit_middleware

    return await rate_limit_middleware(request, call_next)


# ── Core routes (R2) ──────────────────────────────────────────────────────────
from stratum.api.routers import notes

app.include_router(notes.router)

from stratum.api.routers import agents

app.include_router(agents.router)

from stratum.api.routers import substrates

app.include_router(substrates.router)

from stratum.api.routers import search

app.include_router(search.router)

from stratum.api.routers import inbox

app.include_router(inbox.router)

from stratum.api.routers import content

app.include_router(content.router)

from stratum.api.routers import translate

app.include_router(translate.router)

from stratum.api.routers import concepts

app.include_router(concepts.router)

from stratum.api.routers import sync

app.include_router(sync.router)

from stratum.api.routers import account

app.include_router(account.router)

from stratum.api.routers import scheduled_jobs

app.include_router(scheduled_jobs.router)

# ── Advanced routes (R5) ──────────────────────────────────────────────────────
from stratum.api.routers import views

app.include_router(views.router)

from stratum.api.routers import recommendations

app.include_router(recommendations.router)

from stratum.api.routers import bookmarks

app.include_router(bookmarks.router)

from stratum.api.routers import highlights

app.include_router(highlights.router)

from stratum.api.routers import billing

app.include_router(billing.router)

from stratum.api.routers import notifications

app.include_router(notifications.router)

from stratum.api.routers import interactions

app.include_router(interactions.router)

from stratum.api.routers import feeds

app.include_router(feeds.router)

from stratum.api.routers import timeline

app.include_router(timeline.router)

from stratum.api.routers import export

app.include_router(export.router)

from stratum.api.routers import graph as graph_router

app.include_router(graph_router.router)

from stratum.api.routers import media

app.include_router(media.router)

from stratum.api.routers import folder_watch

app.include_router(folder_watch.router)

from stratum.api.routers import channels

app.include_router(channels.router)

from stratum.api.routers import sources

app.include_router(sources.router)

from stratum.api.routers import scan_ocr

app.include_router(scan_ocr.router)

from stratum.api.routers import bundle_split

app.include_router(bundle_split.router)

from stratum.api.routers import quality

app.include_router(quality.router)

# ── WebSocket ─────────────────────────────────────────────────────────────────
from stratum.api.ws import router as ws_router

app.include_router(ws_router)

# ── MCP SSE ───────────────────────────────────────────────────────────────────
app.mount("/mcp", mcp_app)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
async def health(response: Response):
    """Was a bare 200 regardless of DB state. Verifies the DB connection this
    app's routers actually depend on (documents/notes/graph/billing/etc.)."""
    try:
        from stratum.db import get_conn

        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "version": "0.5.0", "database": "connected"}
    except Exception as e:
        response.status_code = 503
        return {
            "status": "unhealthy",
            "version": "0.5.0",
            "database": "unreachable",
            "error": str(e),
        }
