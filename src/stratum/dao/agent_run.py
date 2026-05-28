from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class AgentRun:
    id: str
    user_id: str
    corpus_id: str
    agent_name: str
    params: str
    status: str
    trace: Optional[str]
    citations: Optional[str]
    output: Optional[str]
    total_input_tokens: int
    total_output_tokens: int
    cost_usd: float
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

class AgentRunDAO:
    def __init__(self, db_conn):
        self.conn = db_conn
    _COLS = "id, user_id, corpus_id, agent_name, params, status, trace, citations, output, total_input_tokens, total_output_tokens, cost_usd, started_at, completed_at, error_message"
    def list_runs(self, *, corpus_id: str, limit: int = 50) -> List[AgentRun]:
        return [AgentRun(*r) for r in self.conn.execute(f"SELECT {self._COLS} FROM agent_runs WHERE corpus_id = ? ORDER BY started_at DESC LIMIT ?", (corpus_id, limit)).fetchall()]
