"""Abuse detection for Stratum API.

Per §5.6:
  Same IP 10+ register in 5 min → block 1 hour
  Same IP 20+ failed login in 5 min → block 4 hours
  Single user 100+ /api/* in 1 hour → warning + degrade

Uses in-memory tracking + DuckDB blocked_ips table for persistence.
"""

import time
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
import duckdb
import ulid as ulid_mod


@dataclass
class _Counter:
    timestamps: list = field(default_factory=list)

    def count_in_window(self, window_seconds: int) -> int:
        now = time.time()
        cutoff = now - window_seconds
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        return len(self.timestamps)

    def add(self):
        self.timestamps.append(time.time())


_register_counts: dict[str, _Counter] = defaultdict(_Counter)
_failed_login_counts: dict[str, _Counter] = defaultdict(_Counter)
_blocked_cache: dict[str, float] = {}  # ip -> expires_at timestamp

# Thresholds
REGISTER_THRESHOLD = 10
REGISTER_WINDOW = 300  # 5 min
REGISTER_BLOCK_HOURS = 1

LOGIN_FAIL_THRESHOLD = 20
LOGIN_FAIL_WINDOW = 300  # 5 min
LOGIN_FAIL_BLOCK_HOURS = 4


def _get_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP") or request.client.host


def _is_blocked(ip: str) -> bool:
    expires = _blocked_cache.get(ip)
    if expires and time.time() < expires:
        return True
    if expires:
        del _blocked_cache[ip]
    return False


def _block_ip(ip: str, hours: int, reason: str):
    expires = time.time() + hours * 3600
    _blocked_cache[ip] = expires
    # Persist to PG (best-effort). PG upsert via ON CONFLICT (was DuckDB INSERT OR REPLACE).
    try:
        from stratum.db import get_conn

        expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO blocked_ips (ip_address, reason, blocked_at, expires_at, blocked_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 1)
                ON CONFLICT (ip_address) DO UPDATE SET
                    reason = EXCLUDED.reason,
                    blocked_at = CURRENT_TIMESTAMP,
                    expires_at = EXCLUDED.expires_at,
                    blocked_count = blocked_ips.blocked_count + 1
            """,
                (ip, reason, expires_at),
            )
    except Exception:
        pass  # Non-critical; in-memory block still active


def record_auth_event(event_type: str, ip: str, user_id: str | None = None):
    """Record an auth event and check abuse thresholds."""
    if event_type == "register":
        counter = _register_counts[ip]
        counter.add()
        if counter.count_in_window(REGISTER_WINDOW) >= REGISTER_THRESHOLD:
            _block_ip(ip, REGISTER_BLOCK_HOURS, "excessive_register")

    elif event_type == "login_failed":
        counter = _failed_login_counts[ip]
        counter.add()
        if counter.count_in_window(LOGIN_FAIL_WINDOW) >= LOGIN_FAIL_THRESHOLD:
            _block_ip(ip, LOGIN_FAIL_BLOCK_HOURS, "excessive_failed_login")


async def abuse_detection_middleware(request: Request, call_next):
    """Check if IP is blocked before processing request."""
    ip = _get_ip(request)
    if _is_blocked(ip):
        return JSONResponse(
            status_code=403, content={"detail": "IP temporarily blocked due to abuse"}
        )
    return await call_next(request)


def reset_abuse_state():
    """For testing: clear all abuse detection state."""
    _register_counts.clear()
    _failed_login_counts.clear()
    _blocked_cache.clear()
