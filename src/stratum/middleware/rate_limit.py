"""Per-user/IP sliding window rate limiter for Stratum API.

Limits (per §5.5):
  /api/auth/register: 3/hour per IP
  /api/auth/login: 10/hour per IP
  /api/auth/refresh: 30/hour per user
  Other /api/*: 60/min per user

Uses in-memory store (no Redis dependency for MVP).
"""

import time
from collections import defaultdict
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

# Config
LIMITS = {
    "register": {"window": 3600, "max": 3, "key": "ip"},
    "login": {"window": 3600, "max": 10, "key": "ip"},
    "refresh": {"window": 3600, "max": 30, "key": "user"},
    "api_default": {"window": 60, "max": 60, "key": "user"},
}


def _get_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP") or request.client.host


def _classify_path(path: str) -> str:
    if "/api/auth/register" in path:
        return "register"
    if "/api/auth/login" in path:
        return "login"
    if "/api/auth/refresh" in path:
        return "refresh"
    if path.startswith("/api/"):
        return "api_default"
    return ""


async def rate_limit_middleware(request: Request, call_next):
    """Sliding window rate limiter."""
    path = request.url.path
    category = _classify_path(path)
    if not category:
        return await call_next(request)

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
