from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class ScheduledJob:
    id: str
    user_id: str
    corpus_id: str
    name: str
    agent_name: str
    agent_params: str
    cron_expression: str
    timezone: str
    enabled: bool
    notify_on_completion: bool
    notify_on_failure: bool
    max_runtime_seconds: int
    created_at: datetime
    updated_at: datetime

class ScheduledJobDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, name, agent_name, agent_params, cron_expression, timezone, enabled, notify_on_completion, notify_on_failure, max_runtime_seconds, created_at, updated_at"
    def list_jobs(self, *, corpus_id: str) -> List[ScheduledJob]:
        return [ScheduledJob(*r) for r in self.conn.execute(f"SELECT {self._COLS} FROM scheduled_jobs WHERE corpus_id = ?", (corpus_id,)).fetchall()]
