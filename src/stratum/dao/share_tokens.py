"""DAO for share_tokens table."""
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, List


def _nanoid(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class ShareToken:
    token: str
    resource_type: str
    resource_id: str
    corpus_id: str
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    access_count: int
    last_accessed_at: Optional[datetime]
    allow_anonymous: bool
    meta_json: str


class ShareTokenDAO:
    def __init__(self, db_conn):
        self.conn = db_conn

    _COLS = "token, resource_type, resource_id, corpus_id, created_by, created_at, expires_at, revoked_at, access_count, last_accessed_at, allow_anonymous, meta_json"

    def _row(self, r) -> ShareToken:
        return ShareToken(*r)

    def create_share_token(self, *, resource_type: str, resource_id: str, corpus_id: str,
                           created_by: str, expires_in_days: Optional[int] = None,
                           allow_anonymous: bool = True) -> ShareToken:
        token = _nanoid()
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(days=expires_in_days)) if expires_in_days else None
        self.conn.execute(f"""
            INSERT INTO share_tokens (token, resource_type, resource_id, corpus_id, created_by, created_at, expires_at, allow_anonymous)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (token, resource_type, resource_id, corpus_id, created_by, now, expires_at, allow_anonymous))
        return self.get_share_token(token)

    def get_share_token(self, token: str) -> Optional[ShareToken]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM share_tokens WHERE token = ?", (token,)).fetchone()
        return self._row(res) if res else None

    def list_user_shares(self, user_id: str, resource_type: Optional[str] = None) -> List[ShareToken]:
        sql = f"SELECT {self._COLS} FROM share_tokens WHERE created_by = ? AND revoked_at IS NULL"
        params: list = [user_id]
        if resource_type:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        sql += " ORDER BY created_at DESC"
        return [self._row(r) for r in self.conn.execute(sql, params).fetchall()]

    def revoke_share(self, token: str, user_id: str) -> bool:
        """Revoke a share. Returns False if token not found or not owned by user."""
        existing = self.get_share_token(token)
        if not existing or existing.created_by != user_id:
            return False
        now = datetime.now(timezone.utc)
        self.conn.execute("UPDATE share_tokens SET revoked_at = ? WHERE token = ?", (now, token))
        return True

    def increment_access(self, token: str) -> None:
        now = datetime.now(timezone.utc)
        self.conn.execute(
            "UPDATE share_tokens SET access_count = access_count + 1, last_accessed_at = ? WHERE token = ?",
            (now, token))
