from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class View:
    id: str
    user_id: str
    corpus_id: str
    name: str
    description: Optional[str]
    default_filter: str
    default_llm: Optional[str]
    default_system_prompt: Optional[str]
    icon: Optional[str]
    is_default: bool
    is_builtin: bool
    created_at: datetime
    updated_at: datetime

class ViewDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, name, description, default_filter, default_llm, default_system_prompt, icon, is_default, is_builtin, created_at, updated_at"
    def list_views(self, *, corpus_id: str, limit: int = 50) -> List[View]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM views WHERE corpus_id = ? ORDER BY created_at DESC LIMIT ?", (corpus_id, limit)).fetchall()
        return [View(*r) for r in res]
    def get_view(self, *, view_id: str, corpus_id: str) -> Optional[View]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM views WHERE id = ? AND corpus_id = ?", (view_id, corpus_id)).fetchone()
        return View(*res) if res else None
