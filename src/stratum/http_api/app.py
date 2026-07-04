"""Stratum HTTP API application (legacy "Phase 14" app, `stratum-api` container, :9302).

Still load-bearing — don't assume this is dead just because api/main.py (SPEC2,
:9304) has newer/richer routers with the same names (notes/agents/substrates/
search/scheduled_jobs). Frontend rewrites send /api/auth/* and bare /api/search
here specifically (see api/main.py's module docstring for the full routing
table and why a merge is deferred, not abandoned)."""

import os

from stratum.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from stratum.middleware.corpus_isolation import corpus_isolation_middleware
from stratum.middleware.rate_limit import rate_limit_middleware
from stratum.middleware.abuse_detection import abuse_detection_middleware
from stratum.http_api.routes import auth, search, substrates, notes, agents, scheduled_jobs
from stratum.http_api.routes.admin import router as admin_router
from stratum.http_api.routes.feedback import router as feedback_router
from stratum.http_api.routes.share import router as share_router
from stratum.http_api.routes.users import router as users_router
from stratum.http_api.metrics import metrics_middleware

# Sentry: only initialise when SENTRY_DSN is set (env-guarded — no DSN = no telemetry)
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )


def _validate_production_secrets() -> None:
    """Refuse to start if any critical secret is missing or too short (production only)."""
    if os.getenv("STRATUM_ENV") != "production":
        return
    for name in ("JWT_SECRET", "COOKIE_SECRET", "ADMIN_SECRET"):
        val = os.getenv(name, "")
        if not val or len(val) < 32:
            raise RuntimeError(
                f"{name} must be set and ≥ 32 chars in production (got {len(val)} chars)"
            )


_validate_production_secrets()

app = FastAPI(title="Stratum API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
    return await metrics_middleware(request, call_next)


@app.middleware("http")
async def corpus_mw(request: Request, call_next):
    return await corpus_isolation_middleware(request, call_next)


@app.middleware("http")
async def rate_limit_mw(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


# Outermost (registered last → runs first): reject already-blocked IPs before
# spending any rate-limit/corpus-isolation/route work on them.
@app.middleware("http")
async def abuse_detection_mw(request: Request, call_next):
    return await abuse_detection_middleware(request, call_next)


# Auth (exempt from corpus middleware)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Authenticated routes (corpus_id injected by middleware)
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(substrates.router, prefix="/api", tags=["substrates"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(scheduled_jobs.router, prefix="/api", tags=["scheduled_jobs"])

# Users: public by-username + authenticated sessions management
app.include_router(users_router, prefix="/api/users", tags=["users"])

# Feedback (alpha period in-app feedback)
app.include_router(feedback_router, prefix="/api", tags=["feedback"])

# Share (mixed: authenticated create/revoke + public read)
app.include_router(share_router, tags=["share"])

# Admin stats — wiki-only, requires X-Admin-Secret header
app.include_router(admin_router, prefix="/api", tags=["admin"])


@app.get("/health")
def health_check(response: Response):
    """Was a bare 200 regardless of DB state — a dead backend still passed this
    check as long as the process was alive. Now verifies the DB connection the
    app actually depends on."""
    try:
        from stratum.db import get_conn

        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        response.status_code = 503
        return {"status": "unhealthy", "database": "unreachable", "error": str(e)}


# MCP SSE endpoint — for Claude Desktop / MCP clients
try:
    from stratum.api.mcp import mcp_app

    app.mount("/mcp", mcp_app)
except Exception:
    pass  # mcp optional; skip if fastmcp not installed
