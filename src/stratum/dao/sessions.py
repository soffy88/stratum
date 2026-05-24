from dataclasses import dataclass
from datetime import datetime, timedelta
import ulid

@dataclass
class Session:
    id: str
    user_id: str
    refresh_token_hash: str
    user_agent: str | None
    ip_address: str | None
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    last_used_at: datetime

class SessionDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    def create_session(self, *, user_id: str, refresh_token_hash: str, user_agent: str | None, ip: str | None, ttl_days: int = 30) -> Session:
        session_id = str(ulid.ULID())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=ttl_days)
        self.conn.execute("""
            INSERT INTO sessions (id, user_id, refresh_token_hash, user_agent, ip_address, expires_at, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, refresh_token_hash, user_agent, ip, expires_at, now, now))
        return self.get_session_by_id(session_id)
    def get_session_by_id(self, session_id: str):
        res = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return self._row_to_session(res) if res else None
    def get_session_by_refresh_hash(self, refresh_token_hash: str):
        res = self.conn.execute("SELECT * FROM sessions WHERE refresh_token_hash = ? AND revoked_at IS NULL", (refresh_token_hash,)).fetchone()
        return self._row_to_session(res) if res else None
    def _row_to_session(self, row):
        return Session(
            id=row[0], user_id=row[1], refresh_token_hash=row[2],
            user_agent=row[3], ip_address=row[4], expires_at=row[5],
            revoked_at=row[6], created_at=row[7], last_used_at=row[8]
        )
