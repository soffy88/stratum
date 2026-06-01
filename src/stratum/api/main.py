"""Stratum Service Layer — FastAPI application.

Runs on port 9303. The existing Phase 14 SaaS (http_api/app.py) remains on 9302.
All SPEC 2 routes are wired here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stratum.api.mcp import mcp_app

app = FastAPI(title="Stratum Service Layer", version="0.5.0")

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

from stratum.api.routers import substrate

app.include_router(substrate.router)

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

# ── WebSocket ─────────────────────────────────────────────────────────────────
from stratum.api.ws import router as ws_router

app.include_router(ws_router)

# ── MCP SSE ───────────────────────────────────────────────────────────────────
app.mount("/mcp", mcp_app)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "0.5.0"}
