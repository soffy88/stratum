"""Per-user/IP sliding window rate limiter + API key auth for Stratum API.

Rate limits (per §5.5):
  /api/auth/register: 3/hour per IP
  /api/auth/login: 10/hour per IP
  /api/auth/refresh: 30/hour per user
  /api/aii/*: 300/min per key (AII routes); /api/aii/api/chat: 20/min
  Other /api/*: 60/min per user

API Key auth (P2):
  /api/aii/* routes require X-API-Key header (matching AII_API_KEY env var).
  This replaces AII's standalone APIKeyMiddleware after backend merge.

Uses in-memory store (no Redis dependency for MVP).
"""

import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class _Window:
    timestamps: list = field(default_factory=list)

    def count_in_window(self, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        return len(self.timestamps)

    def add(self):
        self.timestamps.append(time.time())


# Global stores (per-process; sufficient for single-instance MVP)
_ip_windows: dict[str, dict[str, _Window]] = defaultdict(lambda: defaultdict(_Window))
_user_windows: dict[str, dict[str, _Window]] = defaultdict(lambda: defaultdict(_Window))

# AII API key rate limiting — sliding window per key prefix
_aii_windows: dict[str, deque] = {}

# Config
LIMITS = {
    "register": {"window": 3600, "max": 3, "key": "ip"},
    "login": {"window": 3600, "max": 10, "key": "ip"},
    "refresh": {"window": 3600, "max": 30, "key": "user"},
    "api_default": {"window": 60, "max": 60, "key": "user"},
}

# AII rate limits (matches AII's original APIKeyMiddleware)
_AII_DEFAULT_LIMIT = (60, 300)  # 300 req/min for all /api/aii/* routes
_AII_CHAT_LIMIT = (60, 20)      # 20 req/min for /api/aii/api/chat


def _get_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP") or request.client.host


# Top-level segments served by the legacy http_api app (:9302, mounted under
# /api/*). They must not fall through to the AII fallback — that gate is for
# rewritten /api/aii/* traffic arriving at stratum-sl, and applying it here
# would 401/500 every legacy route.
_LEGACY_API_SEGMENTS = {
    "admin",
    "agents",
    "auth",
    "feedback",
    "notes",
    "scheduled_jobs",
    "scheduled-jobs",
    "search",
    "share",
    "shares",
    "substrates",
    "users",
}


def _classify_path(path: str) -> str:
    if path.startswith("/api/aii/"):
        return "aii"
    if "/api/auth/register" in path:
        return "register"
    if "/api/auth/login" in path:
        return "login"
    if "/api/auth/refresh" in path:
        return "refresh"
    # Stratum SL routes all use /api/v1/* prefix. Any other /api/* path is
    # either a legacy http_api route (above segments) or an AII route
    # (Next.js rewrite strips the /api/aii prefix before forwarding to
    # stratum-sl).
    if path.startswith("/api/") and not path.startswith("/api/v1/"):
        segment = path[len("/api/"):].split("/", 1)[0]
        if segment in _LEGACY_API_SEGMENTS:
            return "api_default"
        return "aii"
    if path.startswith("/api/"):
        return "api_default"
    return ""


def _aii_rate_limit(key: str, path: str) -> bool:
    """Check AII API key rate limit. Returns True if allowed."""
    if "/chat" in path:
        window, max_req = _AII_CHAT_LIMIT
        bucket = f"chat:{key[:8]}"
    else:
        window, max_req = _AII_DEFAULT_LIMIT
        bucket = f"default:{key[:8]}"

    now = time.monotonic()
    if bucket not in _aii_windows:
        _aii_windows[bucket] = deque()
    dq = _aii_windows[bucket]
    cutoff = now - window
    while dq and dq[0] <= cutoff:
        dq.popleft()
    if len(dq) >= max_req:
        return False
    dq.append(now)
    return True


def _extract_api_key(request: Request) -> str:
    """Extract API key from X-API-Key header or Authorization: Bearer."""
    key = request.headers.get("x-api-key", "")
    if key:
        return key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return ""


# Paths exempt from AII API key auth (health probes, internal embed).
# Note: Next.js rewrite strips /api/aii prefix, so paths here match
# what arrives at stratum-sl (not the original client-side path).
_AII_EXEMPT = {"/api/ping", "/internal/embed"}


async def rate_limit_middleware(request: Request, call_next):
    """Sliding window rate limiter + API key auth for /api/aii/* routes."""
    path = request.url.path
    category = _classify_path(path)
    if not category:
        return await call_next(request)

    # ── AII routes: API key auth + AII-specific rate limits ──
    if category == "aii":
        if path in _AII_EXEMPT:
            return await call_next(request)

        provided = _extract_api_key(request)
        main_key = os.getenv("AII_API_KEY", "")
        stratum_key = os.getenv("STRATUM_API_KEY", "")

        if not main_key:
            return JSONResponse(
                status_code=500,
                content={"detail": "AII_API_KEY not set on server"},
            )

        matched = False
        if provided:
            if secrets.compare_digest(provided, main_key):
                matched = True
            elif stratum_key and secrets.compare_digest(provided, stratum_key):
                matched = True

        if not matched:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API key for /api/aii/*"},
            )

        if not _aii_rate_limit(provided, path):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded for /api/aii/*"},
            )

        return await call_next(request)

    # ── Non-AII routes: standard rate limiting ──
    limit_cfg = LIMITS[category]
    ip = _get_ip(request)

    if limit_cfg["key"] == "ip":
        window = _ip_windows[ip][category]
        if window.count_in_window(limit_cfg["window"]) >= limit_cfg["max"]:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        window.add()
    elif limit_cfg["key"] == "user":
        user_id = getattr(request.state, "user_id", None) or ip
        window = _user_windows[user_id][category]
        if window.count_in_window(limit_cfg["window"]) >= limit_cfg["max"]:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        window.add()

    return await call_next(request)


def reset_rate_limits():
    """For testing: clear all rate limit state."""
    _ip_windows.clear()
    _user_windows.clear()
    _aii_windows.clear()
