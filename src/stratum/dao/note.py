from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List
import ulid

@dataclass
class Note:
    id: str
    corpus_id: str
    title: str
    content: str
    wikilinks: str
    substrate_id: Optional[str]
    meta_json: str
    created_at: datetime
    updated_at: datetime

class NoteDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, corpus_id, title, content, wikilinks, substrate_id, meta_json, created_at, updated_at"
    def list_notes(self, *, corpus_id: str, limit: int = 50) -> List[Note]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM note WHERE corpus_id = ? ORDER BY created_at DESC LIMIT ?", (corpus_id, limit)).fetchall()
        return [Note(*r) for r in res]
    def get_note(self, *, note_id: str, corpus_id: str) -> Optional[Note]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM note WHERE id = ? AND corpus_id = ?", (note_id, corpus_id)).fetchone()
        return Note(*res) if res else None
    def create_note(self, *, corpus_id: str, title: str, content: str, substrate_id: Optional[str] = None) -> Note:
        note_id = str(ulid.ULID())
        now = datetime.now(timezone.utc)
        self.conn.execute("INSERT INTO note (id, corpus_id, title, content, substrate_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (note_id, corpus_id, title, content, substrate_id, now, now))
        return self.get_note(note_id=note_id, corpus_id=corpus_id)
