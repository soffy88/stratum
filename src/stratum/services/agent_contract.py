"""Shared AgentContract: explicit memory and persistence boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass


_APPROVED_WRITE_TOOLS = frozenset(
    {
        "create_evidence",
        "create_claim",
        "create_relation",
        "create_highlight",
        "session_add_message",
    }
)


@dataclass(frozen=True)
class AgentContract:
    version: str = "1.0"
    memory_policy: str = "working_only"
    persistence_policy: str = "write_via_knowledge_api"
    core_memory: str = "current_working_context"
    recall_memory: str = "read_only_event_log"
    archival_memory: str = "knowledge_foundation"
    max_working_context_tokens: int = 12_000

    def validate_tool(self, tool_name: str, *, writes: bool = False) -> None:
        if writes and self.persistence_policy != "write_via_knowledge_api":
            raise PermissionError("agent writes must go through the Knowledge API")
        if writes and tool_name not in _APPROVED_WRITE_TOOLS:
            raise PermissionError(f"tool is not an approved knowledge write: {tool_name}")

    def to_dict(self) -> dict:
        payload = asdict(self)
        # Keep the API/MCP contract self-describing and deterministic for
        # clients that need to decide whether a proposed write is permitted.
        payload["approved_write_tools"] = sorted(_APPROVED_WRITE_TOOLS)
        return payload


DEFAULT_AGENT_CONTRACT = AgentContract()

