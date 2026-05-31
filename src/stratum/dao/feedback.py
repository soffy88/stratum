"""DAO for feedback table."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import ulid


@dataclass
class Feedback:
    id: str
    user_id: str
    content: str
    page_url: Optional[str]
    created_at: datetime


class FeedbackDAO:
    def __init__(self, db_conn):
        self.conn = db_conn

    def create_feedback(
        self, *, user_id: str, content: str, page_url: Optional[str] = None
    ) -> Feedback:
        fb_id = str(ulid.ULID())
        now = datetime.now(timezone.utc)
        self.conn.execute(
            "INSERT INTO feedback (id, user_id, content, page_url, created_at) VALUES (?, ?, ?, ?, ?)",
            (fb_id, user_id, content, page_url, now),
        )
        return Feedback(
            id=fb_id, user_id=user_id, content=content, page_url=page_url, created_at=now
        )

    def list_recent(self, limit: int = 20) -> list[Feedback]:
        rows = self.conn.execute(
            "SELECT id, user_id, content, page_url, created_at FROM feedback ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [Feedback(*r) for r in rows]
