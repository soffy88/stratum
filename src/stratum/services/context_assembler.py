"""Context Assembler — 组装 agent prompt (对标 OpenViking build_context).

将以下上下文源组合成结构化 prompt:
  1. 检索结果 (相关 substrates L0/L1)
  2. Working Memory (当前 session 的 7-section WM)
  3. Long-term memories (与 query 相关的持久记忆)
  4. Session 消息历史 (最近对话)

输出格式:
  <context>
    <retrieval>...</retrieval>
    <working_memory>...</working_memory>
    <memories>...</memories>
    <conversation>...</conversation>
  </context>
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from stratum.db import get_conn

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Assembled context window for an agent."""

    query: str
    retrieval: list[dict] = field(default_factory=list)  # [{uri, layer, content, score}]
    working_memory: dict[str, Any] = field(default_factory=dict)
    memories: list[dict] = field(default_factory=list)  # [{type, content, confidence}]
    conversation: list[dict] = field(default_factory=list)  # [{role, content}]
    total_tokens: int = 0

    def to_prompt(self, max_tokens: int = 8000) -> str:
        """Render as structured prompt text, respecting token budget."""
        parts = []

        # Retrieval context
        if self.retrieval:
            retrieval_text = "\n".join(
                f"- {r.get('uri', '?').split('/')[-1][:40]}: {r.get('content', '')[:300]}"
                for r in self.retrieval[:10]
            )
            parts.append(f"<retrieval>\n{retrieval_text}\n</retrieval>")

        # Working memory
        if self.working_memory:
            wm_sections = []
            for name, content in self.working_memory.items():
                if content:
                    wm_sections.append(f"  {name}: {content[:200]}")
            if wm_sections:
                parts.append(f"<working_memory>\n" + "\n".join(wm_sections) + "\n</working_memory>")

        # Long-term memories
        if self.memories:
            mem_text = "\n".join(
                f"- [{m.get('type', '?')}] {m.get('content', '')[:200]}"
                for m in self.memories[:10]
            )
            parts.append(f"<memories>\n{mem_text}\n</memories>")

        # Conversation history
        if self.conversation:
            conv_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')[:300]}"
                for m in self.conversation[-10:]
            )
            parts.append(f"<conversation>\n{conv_text}\n</conversation>")

        # Join and truncate if needed
        result = "\n\n".join(parts)
        estimated_tokens = len(result) // 4
        if estimated_tokens > max_tokens:
            # Truncate from the end (conversation history)
            ratio = max_tokens / estimated_tokens
            result = result[: int(len(result) * ratio)]

        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for API response."""
        return {
            "query": self.query,
            "retrieval_count": len(self.retrieval),
            "working_memory_sections": list(self.working_memory.keys()),
            "memories_count": len(self.memories),
            "conversation_turns": len(self.conversation),
            "total_tokens": self.total_tokens,
            "prompt_preview": self.to_prompt(max_tokens=500)[:500],
        }


def build_context(
    query: str,
    session_id: str | None = None,
    user_id: str = "default",
    max_retrieval: int = 5,
    max_memories: int = 5,
    include_conversation: bool = True,
) -> ContextWindow:
    """Build a context window for an agent query.

    Args:
        query: The user's query
        session_id: Optional session ID for WM and conversation history
        user_id: User ID for memory retrieval
        max_retrieval: Max retrieval results to include
        max_memories: Max long-term memories to include
        include_conversation: Whether to include conversation history

    Returns:
        ContextWindow with assembled context
    """
    ctx = ContextWindow(query=query)

    # 1. Retrieval
    try:
        from stratum.services.retrieval_engine import retrieve, get_embedding

        query_emb = get_embedding(query)
        if query_emb:
            # Vector search for L0
            vector_results = _vector_search_context(query_emb, top_k=max_retrieval)
            ctx.retrieval = vector_results
    except Exception as exc:
        logger.warning("context_assembler: retrieval failed: %s", exc)

    # 2. Working Memory (from session)
    if session_id:
        try:
            from stratum.services.working_memory import get_working_memory

            wm = get_working_memory(session_id)
            if wm:
                ctx.working_memory = wm
        except Exception as exc:
            logger.warning("context_assembler: WM failed: %s", exc)

    # 3. Long-term memories
    try:
        ctx.memories = _search_memories(query, user_id, limit=max_memories)
    except Exception as exc:
        logger.warning("context_assembler: memories failed: %s", exc)

    # 4. Conversation history
    if session_id and include_conversation:
        try:
            from stratum.services.session_manager import get_messages

            messages = get_messages(session_id, limit=10)
            ctx.conversation = [
                {"role": m["role"], "content": m["content"][:300]} for m in messages
            ]
        except Exception as exc:
            logger.warning("context_assembler: conversation failed: %s", exc)

    # Estimate total tokens
    ctx.total_tokens = _estimate_tokens(ctx.to_prompt())
    return ctx


def _vector_search_context(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Search for relevant L0 content via pgvector."""
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT substrate_id, content,
                      1 - (embedding <=> ?::vector) as score
               FROM substrate_layers
               WHERE layer = 'L0' AND embedding IS NOT NULL
               ORDER BY embedding <=> ?::vector
               LIMIT ?""",
            (emb_str, emb_str, top_k),
        ).fetchall()
    return [
        {"uri": f"viking://resources/{r[0][:20]}", "content": r[1][:300], "score": float(r[2])}
        for r in rows
    ]


def _search_memories(query: str, user_id: str, limit: int = 5) -> list[dict]:
    """Search long-term memories by query (text + vector)."""
    results = []

    # Text search first (fast)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT memory_type, content, confidence
               FROM long_term_memories
               WHERE user_id = ? AND content ILIKE ?
               ORDER BY confidence DESC
               LIMIT ?""",
            (user_id, f"%{query[:50]}%", limit),
        ).fetchall()
    for r in rows:
        results.append({"type": r[0], "content": r[1], "confidence": float(r[2])})

    # Vector search if we have embeddings
    if len(results) < limit:
        try:
            from stratum.services.retrieval_engine import get_embedding

            query_emb = get_embedding(query)
            if query_emb:
                emb_str = "[" + ",".join(str(x) for x in query_emb) + "]"
                with get_conn() as conn:
                    rows = conn.execute(
                        """SELECT memory_type, content, confidence,
                                  1 - (embedding <=> ?::vector) as score
                           FROM long_term_memories
                           WHERE user_id = ? AND embedding IS NOT NULL
                           ORDER BY embedding <=> ?::vector
                           LIMIT ?""",
                        (emb_str, user_id, emb_str, limit),
                    ).fetchall()
                seen = {r["content"] for r in results}
                for r in rows:
                    if r[1] not in seen:
                        results.append({"type": r[0], "content": r[1], "confidence": float(r[2])})
                        seen.add(r[1])
        except Exception as exc:
            logger.debug("memory vector search failed: %s", exc)

    return results[:limit]


def _estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 chars for English)."""
    return len(text) // 4
