from dataclasses import dataclass
from datetime import datetime, timezone
import ulid
from typing import Any

@dataclass
class User:
    id: str
    email: str
    username: str
    password_hash: str
    corpus_id: str
    email_verified: bool = False
    is_active: bool = True
    is_suspended: bool = False
    created_at: datetime = None
    updated_at: datetime = None
    last_login_at: datetime = None
    meta_json: str = "{}"

class UserDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    def create_user(self, *, email: str, username: str, password_hash: str) -> User:
        user_id = str(ulid.ULID())
        corpus_id = f"user_{user_id}"
        now = datetime.now(timezone.utc)
        self.conn.execute("""
            INSERT INTO users (id, email, username, password_hash, corpus_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, username, password_hash, corpus_id, now, now))
        return self.get_user_by_id(user_id)
    def get_user_by_id(self, user_id: str) -> User | None:
        res = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(res) if res else None
    def get_user_by_email(self, email: str) -> User | None:
        res = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return self._row_to_user(res) if res else None
    def get_user_by_username(self, username: str) -> User | None:
        res = self.conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return self._row_to_user(res) if res else None
    def _row_to_user(self, row) -> User:
        return User(
            id=row[0], email=row[1], username=row[2], password_hash=row[3],
            corpus_id=row[4], email_verified=row[5], is_active=row[6],
            is_suspended=row[7], created_at=row[8], updated_at=row[9],
            last_login_at=row[10], meta_json=row[11]
        )
