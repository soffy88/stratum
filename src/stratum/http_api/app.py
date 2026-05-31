"""Stratum HTTP API application."""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from stratum.middleware.corpus_isolation import corpus_isolation_middleware
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
def health_check():
    return {"status": "healthy"}
