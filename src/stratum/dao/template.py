from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import ulid

@dataclass
class Template:
    id: str
    user_id: str
    corpus_id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime

class TemplateDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, name, content, created_at, updated_at"
    def list_templates(self, *, corpus_id: str, limit: int = 50) -> List[Template]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM templates WHERE corpus_id = ? ORDER BY created_at DESC LIMIT ?", (corpus_id, limit)).fetchall()
        return [Template(*r) for r in res]
    def get_template(self, *, template_id: str, corpus_id: str) -> Optional[Template]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM templates WHERE id = ? AND corpus_id = ?", (template_id, corpus_id)).fetchone()
        return Template(*res) if res else None
