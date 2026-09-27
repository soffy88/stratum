"""MCP adapter for the canonical evidence-brief service.

This module only adapts an already-created MCP/FastMCP-like object.  Runtime
construction and application-specific authentication wiring remain the
responsibility of the caller.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar, cast

from stratum.services.evidence_brief import (
    EvidenceBriefRequest,
    build_evidence_brief,
    render_evidence_brief_markdown,
)

_Tool = TypeVar("_Tool", bound=Callable[..., Any])
RequireUser = Callable[[], str | Awaitable[str]]


class MCPToolRegistrar(Protocol):
    def tool(self) -> Callable[[_Tool], _Tool]: ...


async def _authenticated_user_id(require_user: RequireUser) -> str:
    user_id = require_user()
    if inspect.isawaitable(user_id):
        user_id = await user_id
    return user_id


def register_evidence_brief_tool(
    mcp: MCPToolRegistrar, require_user: RequireUser
) -> Callable[..., Any]:
    """Register the evidence-brief tool on an existing MCP instance.

    The intended application wiring is exactly::

        register_evidence_brief_tool(mcp, _require_user)
    """

    @mcp.tool()
    async def evidence_brief(
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        output_format: str = "structured",
    ) -> dict[str, Any] | str:
        """Retrieve a cited evidence brief for the authenticated user."""
        if output_format not in {"structured", "markdown"}:
            raise ValueError("unsupported output_format; use 'structured' or 'markdown'")

        user_id = await _authenticated_user_id(require_user)
        brief = build_evidence_brief(
            EvidenceBriefRequest(
                query=query,
                user_id=user_id,
                top_k=top_k,
                rerank=rerank,
            )
        )
        if output_format == "markdown":
            return render_evidence_brief_markdown(brief)
        return brief

    return cast(Callable[..., Any], evidence_brief)
