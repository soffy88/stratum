"""API Key authentication middleware with in-memory rate limiting."""
import os
import secrets
import time
from collections import deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Paths exempt from auth (health probes)
_EXEMPT = {"/api/ping"}

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
    # Evict timestamps outside current window
    cutoff = now - window
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if len(dq) >= max_req:
        return False
    dq.append(now)
    return True


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"status": "error", "error": {"code": code, "message": message}},
        status_code=status,
    )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key / Bearer token; apply per-endpoint rate limits."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Exempt paths (health probes)
        if path in _EXEMPT:
            return await call_next(request)

        # Only guard /api/* routes
        if not path.startswith("/api/"):
            return await call_next(request)

        # --- Auth ---
        expected = os.getenv("AII_API_KEY", "")
        if not expected:
            # Misconfigured server — refuse all rather than allow all
            return _err(500, "server_misconfigured", "AII_API_KEY not set on server")

        provided = (
            request.headers.get("X-API-Key")
            or _bearer(request.headers.get("Authorization", ""))
        )
        if not provided or not secrets.compare_digest(provided, expected):
            return _err(401, "unauthorized", "Missing or invalid API key")

        # --- Rate limiting ---
        if path.startswith("/api/chat"):
            window, max_req = _CHAT_LIMIT
            bucket = f"chat:{provided[:8]}"
        else:
            window, max_req = _DEFAULT_LIMIT
            bucket = f"default:{provided[:8]}"

        if not _rate_limit(bucket, window, max_req):
            return _err(429, "rate_limited", f"Too many requests — limit {max_req}/{window}s")

        return await call_next(request)


def _bearer(header: str) -> str:
    """Extract token from 'Bearer <token>' header."""
    if header.lower().startswith("bearer "):
        return header[7:]
    return ""
