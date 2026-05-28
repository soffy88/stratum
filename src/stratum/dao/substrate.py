from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Substrate:
    id: str
    ulid: str
    corpus_id: str
    title: str
    mime: str
    source_path: str
    file_hash: str
    byte_size: int
    page_count: int
    parser: str
    language: str
    has_cjk: bool
    is_scanned: bool
    created_at: datetime
    updated_at: datetime
    meta_json: str
    is_pinned: bool
    pinned_at: Optional[datetime]

class SubstrateDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, ulid, corpus_id, title, mime, source_path, file_hash, byte_size, page_count, parser, language, has_cjk, is_scanned, created_at, updated_at, meta_json, is_pinned, pinned_at"
    def list_substrates(self, *, corpus_id: str, medium: Optional[str] = None, limit: int = 50) -> List[Substrate]:
        sql = f"SELECT {self._COLS} FROM substrate WHERE corpus_id = ?"
        params = [corpus_id]
        if medium:
            sql += " AND mime LIKE ?"
            params.append(f"%{medium}%")
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [Substrate(*r) for r in self.conn.execute(sql, params).fetchall()]
    def get_substrate(self, *, substrate_id: str, corpus_id: str) -> Optional[Substrate]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM substrate WHERE id = ? AND corpus_id = ?", (substrate_id, corpus_id)).fetchone()
        return Substrate(*res) if res else None
