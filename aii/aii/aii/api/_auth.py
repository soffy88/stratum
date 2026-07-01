"""API Key authentication middleware with in-memory rate limiting."""
import os
import secrets
import time
from collections import deque
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Paths exempt from auth (health probes)
_EXEMPT = {"/api/ping", "/internal/embed"}

# Rate limit config: (window_seconds, max_requests)
_DEFAULT_LIMIT = (60, 60)   # 60 req/min for all endpoints
_CHAT_LIMIT    = (60, 20)   # 20 req/min for /api/chat (DeepSeek cost guard)

# In-memory sliding window per path-group: {key -> deque of timestamps}
_windows: dict[str, deque] = {}


def _rate_limit(bucket: str, window: int, max_req: int) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.monotonic()
    if bucket not in _windows:
        _windows[bucket] = deque()
    dq = _windows[bucket]
    cutoff = now - window
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if len(dq) >= max_req:
        return False
    dq.append(now)
    return True


def _err_response(status: int, code: str, message: str):
    return JSONResponse(
        {"status": "error", "error": {"code": code, "message": message}},
        status_code=status,
    )


class APIKeyMiddleware:
    """Pure-ASGI middleware: validates X-API-Key and applies rate limits.

    Using raw ASGI (not BaseHTTPMiddleware) avoids Starlette's anyio task-group
    body-streaming overhead, which under heavy flywheel load causes 40-50 s delays
    on the first response after server startup.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Exempt paths (health probes)
        if path in _EXEMPT:
            await self.app(scope, receive, send)
            return

        # Only guard /api/* routes
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # --- Auth ---
        # Accepted keys: AII_API_KEY (frontend/admin) + STRATUM_API_KEY (read-only, revocable)
        main_key    = os.getenv("AII_API_KEY", "")
        stratum_key = os.getenv("STRATUM_API_KEY", "")
        if not main_key:
            resp = _err_response(500, "server_misconfigured", "AII_API_KEY not set on server")
            await resp(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        provided = (
            headers.get(b"x-api-key", b"").decode()
            or _bearer(headers.get(b"authorization", b"").decode())
        )

        matched = False
        if provided:
            if secrets.compare_digest(provided, main_key):
                matched = True
            elif stratum_key and secrets.compare_digest(provided, stratum_key):
                matched = True
        if not matched:
            resp = _err_response(401, "unauthorized", "Missing or invalid API key")
            await resp(scope, receive, send)
            return

        # --- Rate limiting ---
        if path.startswith("/api/chat"):
            window, max_req = _CHAT_LIMIT
            bucket = f"chat:{provided[:8]}"
        else:
            window, max_req = _DEFAULT_LIMIT
            bucket = f"default:{provided[:8]}"

        if not _rate_limit(bucket, window, max_req):
            resp = _err_response(429, "rate_limited", f"Too many requests — limit {max_req}/{window}s")
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)


def _bearer(header: str) -> str:
    """Extract token from 'Bearer <token>' header."""
    if header.lower().startswith("bearer "):
        return header[7:]
    return ""
