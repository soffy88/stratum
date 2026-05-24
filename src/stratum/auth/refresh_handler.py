import hashlib
import os
import ulid
from .exceptions import InvalidToken

def create_refresh(user_id: str, user_agent: str | None, ip: str | None) -> tuple[str, str]:
    secret = os.urandom(64).hex()
    token_str = f"{ulid.ULID()}_{secret}"
    refresh_token_hash = hashlib.sha256(token_str.encode()).hexdigest()
    return token_str, refresh_token_hash
