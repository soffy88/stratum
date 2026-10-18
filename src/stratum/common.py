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


def _jwt_secrets() -> tuple[str, ...]:
    raw = os.environ.get("JWT_SECRETS", "")
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    legacy = os.environ.get("JWT_SECRET", "").strip() or _JWT_SECRET
    if legacy and legacy not in keys:
        keys.append(legacy)
    return tuple(keys)


def create_token(user_id: str, expires_hours: int = 168) -> str:
    import jwt

    payload = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_hours * 3600,
    }
    secrets = _jwt_secrets()
    if not secrets:
        raise RuntimeError("JWT_SECRET or JWT_SECRETS not set")
    return jwt.encode(payload, secrets[0], algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> str:
    """Verify a JWT and return user_id. Raises HTTPException on failure."""
    import jwt as _jwt

    raw = token.removeprefix("Bearer ").strip()
    if not raw:
        raise HTTPException(401, "Missing token")
    expired = False
    for secret in _jwt_secrets():
        try:
            payload = _jwt.decode(raw, secret, algorithms=[_JWT_ALGORITHM])
            _check_principal_status(payload["sub"], payload.get("iat"))
            return payload["sub"]
        except _jwt.ExpiredSignatureError:
            expired = True
        except _jwt.InvalidTokenError:
            continue
    if expired:
        raise HTTPException(401, "Token expired")
    raise HTTPException(401, "Invalid token")


_STATUS_CACHE_TTL = 30.0
_status_cache: dict[tuple[str, int], tuple[float, str | None]] = {}


def _lookup_principal_block(sub: str, iat: int) -> str | None:
    """Return a reason to reject (suspended / sessions revoked) or None.

    Principals that are not rows in `users` (service tokens, tests) are not affected.
    Fail open on DB errors so an auth-DB hiccup does not lock everyone out."""
    import logging

    try:
        from stratum.db import get_conn

        with get_conn() as conn:
            row = conn.execute(
                "SELECT id, is_active, is_suspended FROM users WHERE email = ? OR id = ? LIMIT 1",
                (sub, sub),
            ).fetchone()
            if not row:
                return None
            if row[2] is True or row[1] is False:
                return "Account suspended"
            srow = conn.execute(
                "SELECT count(*), "
                "sum(CASE WHEN revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP THEN 1 ELSE 0 END), "
                "max(revoked_at) FROM sessions WHERE user_id = ?",
                (row[0],),
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("principal status check skipped: %s", exc)
        return None
    if not srow:
        return None
    total, active, last_revoked = srow
    # All of the user's sessions are revoked/expired and the token predates the
    # last revocation (logout / forced sign-out) → the token is dead too.
    if (
        isinstance(total, int)
        and total > 0
        and not active
        and isinstance(last_revoked, datetime)
        and isinstance(iat, (int, float))
    ):
        if last_revoked.tzinfo is None:
            last_revoked = last_revoked.replace(tzinfo=timezone.utc)
        ts = last_revoked.timestamp()
        if iat <= ts:
            return "Session revoked"
    return None


def _check_principal_status(sub: str, iat: Any) -> None:
    """安全审计 🟡22: reject access tokens of suspended users / revoked sessions."""
    if os.environ.get("STRATUM_AUTH_STATUS_CHECK", "1") == "0":
        return
    try:
        iat_i = int(iat) if iat is not None else 0
    except (TypeError, ValueError):
        iat_i = 0
    key = (str(sub), iat_i)
    now = time.time()
    hit = _status_cache.get(key)
    if hit and hit[0] > now:
        reason = hit[1]
    else:
        reason = _lookup_principal_block(str(sub), iat_i)
        if len(_status_cache) > 10_000:
            _status_cache.clear()
        _status_cache[key] = (now + _STATUS_CACHE_TTL, reason)
    if reason:
        raise HTTPException(401, reason)


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
