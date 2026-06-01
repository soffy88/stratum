"""Stratum service layer — shared utilities used by all route modules."""

import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

# ── Time ──────────────────────────────────────────────────────────────────────


def now_utc() -> str:
    """Current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def now_utc_dt() -> datetime:
    return datetime.now(timezone.utc)


def ts_to_iso(dt: datetime) -> str:
    return dt.isoformat()


# ── ID generation ─────────────────────────────────────────────────────────────

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(n: int, width: int) -> str:
    s = []
    for _ in range(width):
        n, r = divmod(n, 32)
        s.append(_CROCKFORD[r])
    return "".join(reversed(s))


def generate_ulid() -> str:
    """Generate a 26-character ULID (Crockford base32, ms-precision timestamp prefix)."""
    ts_ms = int(time.time() * 1000)
    ts_part = _encode_crockford(ts_ms, 10)
    rand_bytes = uuid.uuid4().bytes[:10]
    rand_int = int.from_bytes(rand_bytes, "big")
    rand_part = _encode_crockford(rand_int, 16)
    return ts_part + rand_part


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── File paths ────────────────────────────────────────────────────────────────


def user_data_dir(user_id: str) -> Path:
    root = Path(os.environ.get("STRATUM_DATA_DIR", str(Path.home() / ".stratum")))
    return root / "users" / user_id


def user_inbox_dir(user_id: str) -> Path:
    return user_data_dir(user_id) / "inbox"


def user_agent_runs_dir(user_id: str) -> Path:
    return user_data_dir(user_id) / "agent_runs"


def user_translations_dir(user_id: str) -> Path:
    return user_data_dir(user_id) / "translations"


def user_highlights_dir(user_id: str) -> Path:
    return user_data_dir(user_id) / "highlights"


def user_changefeed_path(user_id: str) -> Path:
    return user_data_dir(user_id) / "changefeed.log"


def user_sync_state_path(user_id: str) -> Path:
    return user_data_dir(user_id) / "sync_state.json"


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── JWT auth ──────────────────────────────────────────────────────────────────

_JWT_SECRET = os.environ.get("JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"


def create_token(user_id: str, expires_hours: int = 168) -> str:
    import jwt

    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_hours * 3600,
    }
    secret = _JWT_SECRET or os.environ.get("JWT_SECRET", "")
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> str:
    """Verify a JWT and return user_id. Raises HTTPException on failure."""
    import jwt as _jwt

    raw = token.removeprefix("Bearer ").strip()
    if not raw:
        raise HTTPException(401, "Missing token")
    secret = _JWT_SECRET or os.environ.get("JWT_SECRET", "")
    try:
        payload = _jwt.decode(raw, secret, algorithms=[_JWT_ALGORITHM])
        return payload["sub"]
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def jwt_auth(request: Request) -> str:
    """FastAPI dependency — extracts Bearer token and returns user_id."""
    return verify_token(request.headers.get("Authorization", ""))


# ── In-memory dedup cache (replace with Redis in production) ──────────────────
# TECHNICAL_DEBT: DedupCache uses process-local memory; replace with Redis
# before horizontal scaling. See TECHNICAL_DEBT.md.


class DedupCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        self._store[key] = (time.time() + ttl, value)

    async def clear(self) -> None:
        self._store.clear()


dedup_cache = DedupCache()


# ── Sync state ────────────────────────────────────────────────────────────────


def get_local_state(user_id: str) -> dict:
    p = user_sync_state_path(user_id)
    if p.exists():
        import json

        return json.loads(p.read_text())
    return {"is_fully_synced": True, "pending_count": 0, "last_sync_at": None}
