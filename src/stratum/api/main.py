"""Stratum Service Layer — FastAPI application.

Runs on port 9303. The existing Phase 14 SaaS (http_api/app.py) remains on 9302.
All SPEC 2 routes are wired here.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stratum.api.mcp import mcp_app
from stratum.db.run_migrations import run_migrations


def _register_providers() -> None:
    """Register 3O providers (LLM + TTS + image_gen) with obase ProviderRegistry at startup."""
    try:
        from obase.provider_registry import ProviderRegistry
        from oprim.llm.llm_call import llm_call

        if not ProviderRegistry.has("llm", "qwen3"):

            def _qwen3(messages, **_):
                prompt = next((m["content"] for m in messages if m["role"] == "user"), "")
                return llm_call(prompt=prompt, provider="qwen3_dashscope", model="qwen3-max").text

            ProviderRegistry.register("llm", "qwen3", _qwen3)
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


async def _arxiv_watcher_loop() -> None:
    from stratum.services.arxiv_watcher_service import arxiv_watcher_loop
    import logging as _log
    _l = _log.getLogger(__name__)
    try:
        await arxiv_watcher_loop()
    except Exception:
        _l.exception("arxiv_watcher_loop crashed")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    run_migrations()  # 启动时自动建表
    _register_providers()
    task = asyncio.create_task(_feed_tracker_loop())
    fw_task = asyncio.create_task(_folder_watcher_loop())
    cw_task = asyncio.create_task(_channel_watcher_loop())
    ax_task = asyncio.create_task(_arxiv_watcher_loop())
    yield
    task.cancel()
    fw_task.cancel()
    cw_task.cancel()
    ax_task.cancel()


app = FastAPI(title="Stratum Service Layer", version="0.5.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://stratum.uex.hk"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

from stratum.api.routers import arxiv

app.include_router(arxiv.router)

# ── WebSocket ─────────────────────────────────────────────────────────────────
from stratum.api.ws import router as ws_router

app.include_router(ws_router)

# ── MCP SSE ───────────────────────────────────────────────────────────────────
app.mount("/mcp", mcp_app)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.5.0"}
