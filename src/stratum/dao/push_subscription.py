from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class PushSubscription:
    id: str
    user_id: str
    corpus_id: str
    channel: str
    recipient: str
    keys_json: str
    enabled: bool
    created_at: datetime

class PushSubscriptionDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, channel, recipient, keys_json, enabled, created_at"
    def list_by_corpus(self, *, corpus_id: str) -> List[PushSubscription]:
        return [PushSubscription(*r) for r in self.conn.execute(f"SELECT {self._COLS} FROM push_subscriptions WHERE corpus_id = ?", (corpus_id,)).fetchall()]
