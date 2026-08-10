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
from stratum.utils.user_id_hash import hash_user_id

_MCP_USER_ID = os.environ.get("STRATUM_MCP_USER_ID", "")

# DNS rebinding 防护默认拒非 localhost Host — stratum-api 容器名访问需放行
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "stratum",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,   # 容器内网服务, 无 rebinding 面
    ),
)


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

        result = cross_layer_search(
            query=query_text,
            top_k=top_k,
            lancedb_mgr=None,
            tantivy_mgr=None,
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
        "SELECT id, title, updated_at FROM notes "
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
    # Routers emit events under either the raw user id (notes/concepts) or its
    # hash (documents/highlights/views) — match both forms, as sync.py does.
    return query(
        "SELECT seq, event_type, payload, timestamp FROM changefeed "
        "WHERE user_id IN (%(uid)s, %(huid)s) AND seq > %(since)s ORDER BY seq ASC",
        {"uid": user_id, "huid": hash_user_id(user_id), "since": since_seq},
        limit=limit,
    )


# ── Phase 1-4: New tools ─────────────────────────────────────────────────────

@mcp.tool()
async def viking_ls(uri: str = "viking://resources/", depth: int = 1) -> dict:
    """List directory contents in the viking:// virtual filesystem.
    Returns children nodes with their L0 summaries."""
    _require_user()
    from stratum.services.directory_builder import ls
    children = ls(uri, depth=depth)
    return {"uri": uri, "children": children, "count": len(children)}


@mcp.tool()
async def viking_tree(uri: str = "viking://resources/", depth: int = 2) -> dict:
    """Get hierarchical tree view of the viking:// filesystem.
    Shows directory structure with L0 summaries at each level."""
    _require_user()
    from stratum.services.directory_builder import tree
    nodes = tree(uri, max_depth=depth)
    return {"uri": uri, "nodes": nodes, "count": len(nodes)}


@mcp.tool()
async def viking_find(query_text: str, mode: str = "semantic", limit: int = 10) -> dict:
    """Find nodes in the viking:// filesystem.
    Modes: 'name' (URI match), 'content' (text search), 'semantic' (vector search)."""
    user_id = _require_user()
    from stratum.services.directory_builder import find_by_name, find_by_content
    if mode == "name":
        results = find_by_name(query_text, limit=limit)
    else:
        results = find_by_content(query_text, top_k=limit, user_id=user_id)
    return {"query": query_text, "mode": mode, "results": results, "count": len(results)}


@mcp.tool()
async def viking_read(uri: str, layer: str = "L1") -> dict:
    """Read content from a viking:// node at a specific layer.
    L0=abstract (~100 tokens), L1=overview (~2K tokens), L2=full content."""
    _require_user()
    from stratum.services.directory_builder import cat
    result = cat(uri, layer=layer)
    if not result:
        return {"error": f"Content not found: {uri}"}
    return result


@mcp.tool()
async def viking_grep(pattern: str, scope: str = "viking://resources/",
                      layer: str = "L2", limit: int = 30) -> dict:
    """Regex search within the viking:// filesystem.
    Searches layer content under the given URI scope."""
    _require_user()
    from stratum.services.directory_builder import grep
    results = grep(pattern, scope_uri=scope, layer=layer, limit=limit)
    return {"pattern": pattern, "scope": scope, "matches": results, "count": len(results)}


@mcp.tool()
async def retrieve_context(query_text: str, max_depth: int = 2, top_k: int = 10,
                           namespace: str = "global",
                           budget_tokens: int | None = None) -> dict:
    """Tiered retrieval with trajectory tracking.
    Searches L0→L1→L2 layers with directory-recursive drill-down.
    namespace: global(权威知识库) | personal(个人草稿) | all(联邦合并).
    Returns results with viking:// URIs and retrieval trajectory."""
    user_id = _require_user()
    from stratum.services.retrieval_engine import retrieve
    response = retrieve(query=query_text, max_depth=max_depth, top_k=top_k,
                        user_id=user_id, namespace=namespace,
                        budget_tokens=budget_tokens)
    return {
        "query": response.query,
        "total_ms": response.total_ms,
        "result_count": len(response.results),
        "results": [
            {"uri": r.uri, "layer": r.layer, "score": round(r.score, 4),
             "content_preview": r.content[:300], "token_count": r.token_count,
             "namespace": r.namespace}
            for r in response.results
        ],
        "trajectory": [
            {"phase": s.phase, "candidates": s.candidates, "hits": s.hits}
            for s in response.trajectory
        ],
    }


@mcp.tool()
async def session_create(title: str | None = None) -> dict:
    """Create a new agent session for tracking context across a conversation."""
    user_id = _require_user()
    from stratum.services.session_manager import create_session
    return create_session(user_id, title=title)


@mcp.tool()
async def session_add_message(session_id: str, role: str, content: str) -> dict:
    """Add a message to an agent session.
    Roles: user, assistant, system, tool."""
    _require_user()
    from stratum.services.session_manager import add_message
    return add_message(session_id, role, content)


@mcp.tool()
async def session_commit(session_id: str) -> dict:
    """Commit a session: compress old messages, extract long-term memories,
    update Working Memory. Call this periodically or at session end."""
    user_id = _require_user()
    from stratum.services.session_manager import commit_session
    return await commit_session(session_id, user_id)


@mcp.tool()
async def session_get_context(session_id: str, query_text: str | None = None,
                              max_tokens: int = 4000) -> dict:
    """Get context for the next agent turn: Working Memory + relevant memories +
    retrieval results. Inject this into the agent's prompt."""
    user_id = _require_user()
    from stratum.services.session_manager import get_context
    return await get_context(session_id, query=query_text, user_id=user_id,
                            max_tokens=max_tokens)


@mcp.tool()
async def list_memories(memory_type: str | None = None, limit: int = 20) -> dict:
    """List long-term memories extracted from sessions.
    Types: preference, experience, case, trajectory, knowledge_gap, fact."""
    user_id = _require_user()
    from stratum.services.memory_extractor import list_memories as _list
    return {"memories": _list(user_id, memory_type=memory_type, limit=limit)}


@mcp.tool()
async def search_memories(query_text: str, limit: int = 5) -> dict:
    """Semantic search across long-term memories."""
    user_id = _require_user()
    from stratum.services.memory_extractor import get_relevant_memories
    return {"memories": get_relevant_memories(user_id, query_text, limit=limit)}


@mcp.tool()
async def build_context(
    query: str,
    session_id: str | None = None,
    max_retrieval: int = 5,
    max_memories: int = 5,
    format: str = "prompt",
) -> dict:
    """Build a structured context window for an agent.

    Combines retrieval results, working memory, long-term memories,
    and conversation history into a prompt-ready format.
    对标 OpenViking build_context.

    Args:
        query: The query to build context for
        session_id: Optional session for WM and conversation history
        max_retrieval: Max retrieval results (default 5)
        max_memories: Max long-term memories (default 5)
        format: "prompt" (text) or "dict" (structured)
    """
    user_id = _require_user()
    from stratum.services.context_assembler import build_context as _build

    ctx = _build(
        query=query,
        session_id=session_id,
        user_id=user_id,
        max_retrieval=max_retrieval,
        max_memories=max_memories,
    )
    if format == "prompt":
        return {"prompt": ctx.to_prompt(), "total_tokens": ctx.total_tokens}
    return ctx.to_dict()




# ── 决策智能 (semantica 能力 3O 化) ───────────────────────────────────
@mcp.tool()
async def record_decision(category: str, scenario: str, outcome: str,
                          reasoning: str = "", confidence: float = 0.5,
                          decision_maker: str = "master") -> dict:
    """记录一次决策 (一等对象): category/scenario/reasoning/outcome/confidence。
    之后可因果链接、先例检索、策略校验、审计导出。"""
    user_id = _require_user()
    try:
        from omodul.decision_ledger import DecisionLedgerConfig, DecisionLedgerInput, decision_ledger
        from stratum.dao.decision_intelligence import DecisionLedgerBackend
    except ImportError:
        return {"error": "omodul/stratum decision 未装配"}
    r = decision_ledger(
        DecisionLedgerConfig(),
        DecisionLedgerInput(action="record", category=category, scenario=scenario,
                            outcome=outcome, reasoning=reasoning,
                            confidence=confidence, decision_maker=decision_maker,
                            backend=DecisionLedgerBackend(user_id)),
    )
    return r["findings"]


@mcp.tool()
async def query_decisions(query_text: str, max_results: int = 5) -> dict:
    """按场景检索历史决策 (先例检索): 返回最相似的已记录决策。"""
    user_id = _require_user()
    try:
        from omodul.decision_ledger import DecisionLedgerConfig, DecisionLedgerInput, decision_ledger
        from stratum.dao.decision_intelligence import DecisionLedgerBackend
    except ImportError:
        return {"error": "omodul/stratum decision 未装配"}
    r = decision_ledger(
        DecisionLedgerConfig(),
        DecisionLedgerInput(action="query_similar", query_text=query_text,
                            max_results=max_results,
                            backend=DecisionLedgerBackend(user_id)),
    )
    return r["findings"]


@mcp.tool()
async def run_reasoning(rules: list[str], query: str = "") -> dict:
    """确定性前向推理 (Datalog): 概念图 facts + 规则 → 推导事实 + 可解释链。"""
    user_id = _require_user()
    try:
        from omodul.kg_reasoning import KgReasoningConfig, KgReasoningInput, kg_reasoning
        from stratum.dao.decision_intelligence import list_concept_triples
    except ImportError:
        return {"error": "omodul 未装配"}
    r = kg_reasoning(
        KgReasoningConfig(),
        KgReasoningInput(facts=[], rules=rules, query=query,
                         backend=_TripleSource(user_id)),
    )
    return r["findings"]


class _TripleSource:
    def __init__(self, user_id: str) -> None:
        self._uid = user_id

    def list_triples(self):
        return list_concept_triples(self._uid)


# ASGI app — mounted at /mcp in api/main.py and http_api/app.py
mcp_app = mcp.streamable_http_app()

