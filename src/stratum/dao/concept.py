from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Concept:
    id: str
    name: str
    aliases: Optional[str]
    description: Optional[str]
    wikilink: Optional[str]
    source_ids: str
    meta_json: str
    created_at: datetime
    updated_at: datetime
    corpus_id: str

class ConceptDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, name, aliases, description, wikilink, source_ids, meta_json, created_at, updated_at, corpus_id"
    def get_concept(self, *, concept_id: str, corpus_id: str) -> Optional[Concept]:
        res = self.conn.execute(f"SELECT {self._COLS} FROM concept WHERE id = ? AND corpus_id = ?", (concept_id, corpus_id)).fetchone()
        return Concept(*res) if res else None
