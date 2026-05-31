import jwt
from datetime import datetime, timedelta, timezone
import os
from .exceptions import TokenExpired, InvalidToken

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET not set — refusing to start")
if len(SECRET_KEY) < 32:
    raise RuntimeError(f"JWT_SECRET too short ({len(SECRET_KEY)} chars) — must be ≥ 32")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def encode_access(user_id: str, corpus_id: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": user_id, "corpus_id": corpus_id, "exp": expire, "iat": now}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpired("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidToken("Invalid token")
