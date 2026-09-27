import os
from datetime import datetime, timedelta, timezone

import jwt

from .exceptions import TokenExpired, InvalidToken


def configured_secrets() -> tuple[str, ...]:
    """Return signing keys in rotation order: newest first, oldest last."""
    raw = os.getenv("JWT_SECRETS", "")
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    legacy = os.getenv("JWT_SECRET", "").strip()
    if legacy and legacy not in keys:
        keys.append(legacy)
    return tuple(keys)


def _require_secrets() -> tuple[str, ...]:
    keys = configured_secrets()
    if not keys:
        raise RuntimeError("JWT_SECRET or JWT_SECRETS not set — refusing to start")
    if any(len(key) < 32 for key in keys):
        raise RuntimeError("all JWT signing secrets must be ≥ 32 chars")
    return keys


SECRET_KEY = _require_secrets()[0]

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def encode_access(user_id: str, corpus_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "corpus_id": corpus_id, "exp": expire, "iat": now}
    return jwt.encode(to_encode, _require_secrets()[0], algorithm=ALGORITHM)


def decode_access(token: str) -> dict:
    expired = False
    for secret in _require_secrets():
        try:
            return jwt.decode(token, secret, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            expired = True
        except jwt.InvalidTokenError:
            continue
    if expired:
        raise TokenExpired("Token has expired")
    raise InvalidToken("Invalid token")
