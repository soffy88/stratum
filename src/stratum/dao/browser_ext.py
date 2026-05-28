from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class BrowserExtUrlIndex:
    id: str
    url: str
    normalized_url: str
    substrate_id: str
    ingested_at: datetime
    corpus_id: str

class BrowserExtDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, url, normalized_url, substrate_id, ingested_at, corpus_id"
    def get_by_url(self, *, normalized_url: str, corpus_id: str) -> Optional[BrowserExtUrlIndex]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM browser_ext_url_index WHERE normalized_url = ? AND corpus_id = ?", (normalized_url, corpus_id)).fetchone()
        return BrowserExtUrlIndex(*res) if res else None
