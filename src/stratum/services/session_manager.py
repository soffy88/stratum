"""Session Manager — Agent 会话生命周期管理 (对标 OpenViking Session).

核心功能:
  - create_session → 创建会话
  - add_message → 追加消息 (user/assistant/system/tool)
  - commit → 触发压缩 + 记忆提取 + WM 更新
  - get_context → 注入记忆 + 检索结果到 Agent context
  - archive → 归档
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────

AUTO_COMMIT_THRESHOLD = 8000   # tokens before auto-compress
KEEP_RECENT_COUNT = 20         # keep last N messages after archive
DEFAULT_RETENTION_BUDGET = 4000  # token budget for retained messages


def _run_auto_commit(session_id: str, user_id: str) -> None:
    """Run commit_session in a new event loop (for background threads)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(commit_session(session_id, user_id))
        loop.close()
        logger.info("auto-commit completed for session %s: %s", session_id[:12], result.get("status", "ok"))
    except Exception as exc:
        logger.warning("auto-commit failed for session %s: %s", session_id[:12], exc)


def _gen_id(prefix: str = "sess") -> str:
    import hashlib
    raw = f"{prefix}-{time.time()}-{id(prefix)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)



def require_session_owner(session_id: str, user_id: str) -> dict[str, Any] | None:
    """Return session dict if it exists and belongs to user_id; else None."""
    return get_session(session_id, user_id=user_id)


# ── Session CRUD ─────────────────────────────────────────────────────────────

def create_session(user_id: str, title: str | None = None) -> dict[str, Any]:
    """Create a new agent session."""
    session_id = _gen_id("sess")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_sessions (id, user_id, title, status)
               VALUES (?, ?, ?, 'active')""",
            (session_id, user_id, title),
        )
    logger.info("session_manager: created session %s for user %s", session_id[:12], user_id[:12])
    return {
        "id": session_id,
        "user_id": user_id,
        "title": title,
        "status": "active",
        "message_count": 0,
        "total_tokens": 0,
    }


def add_message(session_id: str, role: str, content: str,
                parts: list[dict] | None = None,
                user_id: str | None = None) -> dict[str, Any]:
    """Add a message to a session. If user_id is set, enforce ownership."""
    if user_id is not None and require_session_owner(session_id, user_id) is None:
        return {"error": "not_found"}
    msg_id = _gen_id("msg")
    tokens = _estimate_tokens(content)

    with get_conn() as conn:
        # Double-check ownership at write time when user_id provided
        if user_id is not None:
            row = conn.execute(
                "SELECT 1 FROM agent_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if not row:
                return {"error": "not_found"}
        conn.execute(
            """INSERT INTO session_messages (id, session_id, role, content, parts_json, estimated_tokens)
               VALUES (?, ?, ?, ?, ?::jsonb, ?)""",
            (msg_id, session_id, role, content,
             json.dumps(parts or [], ensure_ascii=False), tokens),
        )
        conn.execute(
            """UPDATE agent_sessions
               SET message_count = message_count + 1,
                   total_tokens = total_tokens + ?,
                   pending_tokens = pending_tokens + ?,
                   updated_at = NOW()
               WHERE id = ?""",
            (tokens, tokens, session_id),
        )
        # Check if we should auto-commit
        session = conn.execute(
            "SELECT pending_tokens, user_id FROM agent_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

    result = {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "estimated_tokens": tokens,
    }

    # Auto-commit if pending_tokens exceeds threshold (fire-and-forget)
    if session and session[0] > AUTO_COMMIT_THRESHOLD:
        user_id = session[1]
        try:
            import threading
            thread = threading.Thread(
                target=lambda: _run_auto_commit(session_id, user_id),
                daemon=True,
            )
            thread.start()
            result["auto_commit"] = "scheduled"
        except Exception as exc:
            logger.debug("auto-commit scheduling failed: %s", exc)

    return result


def get_messages(session_id: str, limit: int = 50, offset: int = 0,
                user_id: str | None = None) -> list[dict]:
    """Get messages from a session. If user_id is set, enforce ownership."""
    if user_id is not None and require_session_owner(session_id, user_id) is None:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, role, content, parts_json, estimated_tokens, created_at
               FROM session_messages
               WHERE session_id = ?
               ORDER BY created_at ASC
               LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        ).fetchall()
    return [
        {
            "id": r[0],
            "role": r[1],
            "content": r[2],
            "parts": json.loads(r[3]) if r[3] else [],
            "estimated_tokens": r[4],
            "created_at": str(r[5]),
        }
        for r in rows
    ]


def get_session(session_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    """Get session metadata. If user_id is set, only return when owned by that user."""
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                """SELECT id, user_id, title, status, message_count, total_tokens,
                          commit_count, pending_tokens, keep_recent_count, meta_json,
                          created_at, updated_at
                   FROM agent_sessions WHERE id = ? AND user_id = ?""",
                (session_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT id, user_id, title, status, message_count, total_tokens,
                          commit_count, pending_tokens, keep_recent_count, meta_json,
                          created_at, updated_at
                   FROM agent_sessions WHERE id = ?""",
                (session_id,),
            ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "title": row[2],
        "status": row[3],
        "message_count": row[4],
        "total_tokens": row[5],
        "commit_count": row[6],
        "pending_tokens": row[7],
        "keep_recent_count": row[8],
        "meta": json.loads(row[9]) if row[9] else {},
        "created_at": str(row[10]),
        "updated_at": str(row[11]),
    }


def list_sessions(user_id: str, status: str | None = None,
                  limit: int = 20) -> list[dict]:
    """List sessions for a user."""
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                """SELECT id, title, status, message_count, total_tokens,
                          commit_count, created_at, updated_at
                   FROM agent_sessions
                   WHERE user_id = ? AND status = ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (user_id, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, status, message_count, total_tokens,
                          commit_count, created_at, updated_at
                   FROM agent_sessions
                   WHERE user_id = ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
    return [
        {
            "id": r[0], "title": r[1], "status": r[2],
            "message_count": r[3], "total_tokens": r[4],
            "commit_count": r[5], "created_at": str(r[6]), "updated_at": str(r[7]),
        }
        for r in rows
    ]


# ── Commit (compress + extract memory + update WM) ──────────────────────────

async def commit_session(session_id: str, user_id: str) -> dict[str, Any]:
    """Commit a session: archive old messages, extract memory, update WM.

    This is the core operation that makes sessions useful for long-term context.
    """
    session = get_session(session_id, user_id=user_id)
    if not session:
        return {"error": "Session not found"}

    messages = get_messages(session_id)
    if not messages:
        return {"status": "empty", "session_id": session_id}

    total_tokens = sum(m["estimated_tokens"] for m in messages)
    results: dict[str, Any] = {
        "session_id": session_id,
        "total_messages": len(messages),
        "total_tokens": total_tokens,
    }

    # Step 1: Archive if over threshold
    if total_tokens > AUTO_COMMIT_THRESHOLD and len(messages) > KEEP_RECENT_COUNT:
        archive_result = await _archive_messages(session_id, messages)
        results["archive"] = archive_result

    # Step 2: Update Working Memory
    try:
        from stratum.services.working_memory import update_working_memory
        wm = update_working_memory(session_id, messages)
        results["working_memory"] = {"sections_updated": len(wm)}
    except Exception as exc:
        logger.warning("WM update failed: %s", exc)
        results["working_memory"] = {"error": str(exc)}

    # Step 3: Extract long-term memory (async, don't block)
    try:
        from stratum.services.memory_extractor import extract_memories
        memories = await extract_memories(session_id, user_id, messages)
        results["memories_extracted"] = memories
    except Exception as exc:
        logger.warning("Memory extraction failed: %s", exc)
        results["memories_extracted"] = {"error": str(exc)}

    # Update session commit count and reset pending tokens
    with get_conn() as conn:
        conn.execute(
            """UPDATE agent_sessions
               SET commit_count = commit_count + 1,
                   pending_tokens = 0,
                   updated_at = NOW()
               WHERE id = ?""",
            (session_id,),
        )

    logger.info("session_manager: committed session %s — %s", session_id[:12], results)
    return results


async def _archive_messages(session_id: str, messages: list[dict]) -> dict[str, Any]:
    """Archive old messages, keeping only the most recent ones."""
    keep = messages[-KEEP_RECENT_COUNT:]
    archive = messages[:-KEEP_RECENT_COUNT]

    if not archive:
        return {"archived": 0}

    # Generate overview from archived messages
    overview = _generate_archive_overview(archive)
    archive_tokens = sum(m["estimated_tokens"] for m in archive)

    # Get next archive index
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(archive_index), -1) FROM session_archives WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        next_index = (row[0] if row else -1) + 1

        archive_id = _gen_id("arch")
        conn.execute(
            """INSERT INTO session_archives
               (id, session_id, archive_index, overview, message_count, token_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (archive_id, session_id, next_index, overview,
             len(archive), archive_tokens),
        )

        # Delete archived messages
        archived_ids = [m["id"] for m in archive]
        for mid in archived_ids:
            conn.execute("DELETE FROM session_messages WHERE id = ?", (mid,))

        # Update pending tokens
        conn.execute(
            """UPDATE agent_sessions
               SET pending_tokens = pending_tokens - ?
               WHERE id = ?""",
            (archive_tokens, session_id),
        )

    return {
        "archive_index": next_index,
        "archived_messages": len(archive),
        "archived_tokens": archive_tokens,
        "retained_messages": len(keep),
    }


def _generate_archive_overview(messages: list[dict]) -> str:
    """Generate a simple overview from archived messages."""
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]

    topics = []
    for m in user_msgs[:5]:
        content = m["content"][:100]
        topics.append(f"- {content}")

    return (
        f"Archive: {len(messages)} messages "
        f"({len(user_msgs)} user, {len(assistant_msgs)} assistant)\n\n"
        f"Topics discussed:\n" + "\n".join(topics)
    )


# ── Context injection ────────────────────────────────────────────────────────

async def get_context(session_id: str, query: str | None = None,
                      user_id: str = "default",
                      max_tokens: int = 4000) -> dict[str, Any]:
    """Get context for an agent turn: WM + memories + retrieval results.

    This is what an Agent would call before generating a response.
    """
    if user_id and user_id != "default":
        if require_session_owner(session_id, user_id) is None:
            return {"error": "Session not found", "session_id": session_id}
    context_parts: list[dict[str, Any]] = []
    total_tokens = 0

    # 1. Working Memory
    try:
        from stratum.services.working_memory import get_working_memory
        wm = get_working_memory(session_id)
        if wm:
            wm_tokens = _estimate_tokens(json.dumps(wm, ensure_ascii=False))
            if total_tokens + wm_tokens < max_tokens:
                context_parts.append({"type": "working_memory", "content": wm, "tokens": wm_tokens})
                total_tokens += wm_tokens
    except Exception as exc:
        logger.debug("WM not available: %s", exc)

    # 2. Long-term memories
    try:
        from stratum.services.memory_extractor import get_relevant_memories
        memories = get_relevant_memories(user_id, query or "", limit=5)
        if memories:
            mem_tokens = sum(_estimate_tokens(m["content"]) for m in memories)
            if total_tokens + mem_tokens < max_tokens:
                context_parts.append({"type": "memories", "content": memories, "tokens": mem_tokens})
                total_tokens += mem_tokens
    except Exception as exc:
        logger.debug("Memory retrieval not available: %s", exc)

    # 3. Retrieval results (if query provided)
    if query:
        try:
            from stratum.services.retrieval_engine import retrieve
            resp = retrieve(query=query, max_depth=2, top_k=5, user_id=user_id)
            retrieval_items = [
                {"uri": r.uri, "layer": r.layer, "content": r.content[:500], "score": r.score}
                for r in resp.results[:5]
            ]
            ret_tokens = sum(_estimate_tokens(item["content"]) for item in retrieval_items)
            if total_tokens + ret_tokens < max_tokens:
                context_parts.append({"type": "retrieval", "content": retrieval_items, "tokens": ret_tokens})
                total_tokens += ret_tokens
        except Exception as exc:
            logger.debug("Retrieval not available: %s", exc)

    return {
        "session_id": session_id,
        "context_parts": context_parts,
        "total_tokens": total_tokens,
    }


# ── Archive ──────────────────────────────────────────────────────────────────

def archive_session(session_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Archive a session (mark as completed). Enforces ownership when user_id set."""
    with get_conn() as conn:
        if user_id is not None:
            cur = conn.execute(
                "UPDATE agent_sessions SET status = 'archived', updated_at = NOW() "
                "WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
            # psycopg2 rowcount via cursor if available
            if hasattr(cur, "rowcount") and cur.rowcount == 0:
                return {"error": "not_found"}
        else:
            conn.execute(
                "UPDATE agent_sessions SET status = 'archived', updated_at = NOW() WHERE id = ?",
                (session_id,),
            )
    return {"session_id": session_id, "status": "archived"}


def delete_session(session_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Delete a session and all its data. Enforces ownership when user_id set."""
    with get_conn() as conn:
        if user_id is not None:
            row = conn.execute(
                "SELECT 1 FROM agent_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if not row:
                return {"error": "not_found"}
        conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_archives WHERE session_id = ?", (session_id,))
        if user_id is not None:
            conn.execute(
                "DELETE FROM agent_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            )
        else:
            conn.execute("DELETE FROM agent_sessions WHERE id = ?", (session_id,))
    return {"session_id": session_id, "status": "deleted"}
