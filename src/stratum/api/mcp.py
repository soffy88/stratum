"""Stratum MCP server — registered tools for Claude Desktop / MCP clients.

Security model: MCP is a single-tenant tool. All queries are scoped to a single
user, whose ID is bound at startup via the STRATUM_MCP_USER_ID env var.
This is intentional — Claude Desktop connects as *one* user, not a multi-tenant
API. If STRATUM_MCP_USER_ID is not set, all tools return an error and the app
refuses to serve data.
"""

import os

from mcp.server.fastmcp import FastMCP

from stratum.db import query, read

_MCP_USER_ID = os.environ.get("STRATUM_MCP_USER_ID", "")

mcp = FastMCP("stratum")


def _require_user() -> str:
    if not _MCP_USER_ID:
        raise RuntimeError(
            "STRATUM_MCP_USER_ID is not set — refusing to serve unscoped data. "
            "Set this env var to your Stratum user_id before starting the MCP server."
        )
    return _MCP_USER_ID


@mcp.tool()
async def search_knowledge(query_text: str, top_k: int = 10) -> dict:
    """Hybrid search across the configured user's substrate library."""
    user_id = _require_user()
    try:
        from oskill.cross_layer_search import cross_layer_search
        from stratum.api.search_utils import get_tantivy_mgr, get_pgvector_user_mgr

        result = cross_layer_search(
            query=query_text,
            scope=["user_substrate", "user_notes"],
            top_k=top_k,
            lancedb_mgr=get_pgvector_user_mgr(user_id),
            tantivy_mgr=get_tantivy_mgr(),
            pgvector_mgr=None,
        )
        return {
            "results": [
                {"title": r.title, "type": r.type, "score": round(r.score, 4)}
                for r in result.results[:top_k]
                if getattr(r, "user_id", None) in (None, user_id)
            ],
            "search_time_ms": result.search_time_ms,
        }
    except ImportError:
        return {"results": [], "error": "oskill not available"}


@mcp.tool()
async def get_note(note_id: str) -> dict:
    """Fetch one of the user's notes by ID."""
    user_id = _require_user()
    note = read("notes", note_id)
    if not note or note.get("user_id") != user_id or note.get("deleted_at"):
        return {"error": "Note not found"}
    return {
        "id": note["id"],
        "title": note.get("title"),
        "content_markdown": note.get("content_markdown"),
        "updated_at": str(note.get("updated_at") or ""),
    }


@mcp.tool()
async def list_recent_notes(limit: int = 20) -> list[dict]:
    """List the user's most recently updated notes."""
    user_id = _require_user()
    return query(
        "SELECT id, title, updated_at FROM notes_sl "
        "WHERE user_id = %(uid)s AND deleted_at IS NULL "
        "ORDER BY updated_at DESC",
        {"uid": user_id},
        limit=limit,
    )


@mcp.tool()
async def get_substrate(substrate_id: str) -> dict:
    """Fetch one of the user's substrates (documents) by ID."""
    user_id = _require_user()
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != user_id:
        return {"error": "Not found"}
    return {
        "id": sub["id"],
        "title": sub.get("title"),
        "is_pinned": sub.get("is_pinned", False),
    }


@mcp.tool()
async def list_recent_changes(since_seq: int = 0, limit: int = 20) -> list[dict]:
    """Pull recent changefeed events for this user."""
    user_id = _require_user()
    return query(
        "SELECT seq, event_type, payload, timestamp FROM changefeed "
        "WHERE user_id = %(uid)s AND seq > %(since)s ORDER BY seq ASC",
        {"uid": user_id, "since": since_seq},
        limit=limit,
    )


# ASGI app — mounted at /mcp in api/main.py and http_api/app.py
mcp_app = mcp.streamable_http_app()
