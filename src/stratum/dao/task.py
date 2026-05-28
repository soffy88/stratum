from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List
import ulid

@dataclass
class Task:
    id: str
    user_id: str
    corpus_id: str
    text: str
    completed: bool
    due_date: Optional[date]
    scheduled_date: Optional[date]
    tags: Optional[str]
    created_at: datetime

class TaskDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, text, completed, due_date, scheduled_date, tags, created_at"
    def list_tasks(self, *, corpus_id: str, completed: Optional[bool] = None, limit: int = 50) -> List[Task]:
        sql = f"SELECT {self._COLS} FROM tasks WHERE corpus_id = ?"
        params = [corpus_id]
        if completed is not None:
            sql += " AND completed = ?"
            params.append(completed)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [Task(*r) for r in self.conn.execute(sql, params).fetchall()]
    def get_task(self, *, task_id: str, corpus_id: str) -> Optional[Task]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM tasks WHERE id = ? AND corpus_id = ?", (task_id, corpus_id)).fetchone()
        return Task(*res) if res else None
