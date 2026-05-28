from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Derivative:
    id: str
    substrate_id: str
    kind: str
    seq: int
    content: str
    embedding_id: Optional[str]
    embedding_dim: Optional[int]
    meta_json: str
    created_at: datetime
    corpus_id: str

class DerivativeDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, substrate_id, kind, seq, content, embedding_id, embedding_dim, meta_json, created_at, corpus_id"
    def list_by_substrate(self, *, substrate_id: str, corpus_id: str) -> List[Derivative]:
        return [Derivative(*r) for r in self.conn.execute(f"SELECT {self._COLS} FROM derivative WHERE substrate_id = ? AND corpus_id = ?", (substrate_id, corpus_id)).fetchall()]
