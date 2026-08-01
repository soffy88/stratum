"""Memory Extractor — 长期记忆提取 (对标 OpenViking Session Memory).

Session commit 后异步提取:
  - preference: 用户偏好 (格式、深度、语言)
  - experience: Agent 执行经验 (哪些检索策略有效)
  - case: 成功案例和问题解决记录
  - trajectory: 完整任务轨迹
  - knowledge_gap: 发现的知识缺口
  - fact: 重要事实

存储: long_term_memories 表 + 注册到 viking://memories/ 目录.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx
import numpy as np

from stratum.db import get_conn

logger = logging.getLogger(__name__)

_OLLAMA_BASE = "http://172.19.0.1:11434"
_MODEL = "qwen3-8b"
_EMBED_MODEL = "qwen3-embedding"

MEMORY_TYPES = [
    "preference",
    "experience",
    "case",
    "trajectory",
    "knowledge_gap",
    "fact",
]

# ── LLM / Embedding ─────────────────────────────────────────────────────────

def _call_llm(messages: list[dict]) -> str:
    try:
        resp = httpx.post(
            f"{_OLLAMA_BASE}/api/chat",
            json={"model": _MODEL, "messages": messages, "stream": False},
            timeout=120.0,
        )
        resp.raise_for_status()
        result = resp.json().get("message", {}).get("content", "").strip()
        if "" in result:
            result = re.sub(r"", "", result, flags=re.DOTALL).strip()
        return result
    except Exception as exc:
        logger.warning("memory_extractor LLM failed: %s", exc)
        return ""


_EMBED_DIM = 1024  # Must match substrate_layers.embedding vector dimension


def _get_embedding(text: str) -> list[float] | None:
    try:
        resp = httpx.post(
            f"{_OLLAMA_BASE}/api/embeddings",
            json={"model": _EMBED_MODEL, "prompt": text[:4000]},
            timeout=30.0,
        )
        resp.raise_for_status()
        emb = resp.json().get("embedding", [])
        # Truncate to match vector(1024) column (Matryoshka-safe)
        return emb[:_EMBED_DIM] if len(emb) > _EMBED_DIM else emb
    except Exception:
        return None


def _gen_id(prefix: str = "mem") -> str:
    import hashlib
    raw = f"{prefix}-{time.time()}-{id(prefix)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ── Extraction ───────────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """\
You are an expert at extracting long-term memories from AI agent conversations.

Given the following conversation between a user and an AI assistant, extract any long-term memories that would be useful in future sessions.

Memory types to extract:
- **preference**: User preferences about format, depth, language, style
- **experience**: What worked well or poorly in this session
- **case**: Notable problem-solving episodes or success stories
- **knowledge_gap**: Topics the user needs to learn more about
- **fact**: Important facts stated during the conversation

Output format: a JSON array of objects:
[
  {
    "type": "preference|experience|case|knowledge_gap|fact",
    "content": "The memory content (1-3 sentences, precise)",
    "confidence": 0.0-1.0,
    "tags": ["tag1", "tag2"]
  }
]

Rules:
- Only extract genuinely useful long-term information, not trivial exchanges
- Each memory should be self-contained and understandable without the conversation
- If nothing worth remembering, return an empty array []
- Maximum 5 memories per conversation
- Output ONLY the JSON array, no explanation"""


async def extract_memories(session_id: str, user_id: str,
                           messages: list[dict]) -> dict[str, Any]:
    """Extract long-term memories from session messages.

    Returns:
        {"extracted": N, "by_type": {type: count}}
    """
    if not messages:
        return {"extracted": 0, "by_type": {}}

    # Build conversation text
    conversation = "\n".join(
        f"[{m['role']}] {m['content'][:300]}" for m in messages[-20:]
    )

    # Call LLM to extract memories
    result_text = await asyncio.to_thread(
        _call_llm,
        [
            {"role": "system", "content": _EXTRACTION_PROMPT},
            {"role": "user", "content": f"Extract memories from this conversation:\n\n{conversation}"},
        ],
    )

    if not result_text:
        return {"extracted": 0, "by_type": {}, "reason": "LLM returned empty"}

    # Parse JSON
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            memories = json.loads(json_match.group())
        else:
            memories = json.loads(result_text)
    except json.JSONDecodeError:
        logger.warning("Memory extraction: invalid JSON from LLM")
        return {"extracted": 0, "by_type": {}, "reason": "JSON parse failed"}

    if not isinstance(memories, list):
        return {"extracted": 0, "by_type": {}, "reason": "Not a list"}

    # Persist memories
    by_type: dict[str, int] = {}
    for mem in memories[:5]:  # Max 5
        mem_type = mem.get("type", "fact")
        if mem_type not in MEMORY_TYPES:
            mem_type = "fact"
        content = mem.get("content", "")
        if not content:
            continue

        confidence = min(1.0, max(0.0, float(mem.get("confidence", 0.7))))
        tags = mem.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        # Get embedding
        embedding = await asyncio.to_thread(_get_embedding, content)

        # Store
        mem_id = _gen_id("mem")
        try:
            with get_conn() as conn:
                conn.execute(
                    """INSERT INTO long_term_memories
                       (id, user_id, memory_type, content, source_session,
                        confidence, embedding, tags)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (mem_id, user_id, mem_type, content, session_id,
                     confidence, embedding, tags),
                )
        except Exception as exc:
            logger.warning("Memory persist failed: %s", exc)
            continue

        by_type[mem_type] = by_type.get(mem_type, 0) + 1

        # Register in viking:// directory
        try:
            from stratum.services.directory_builder import ensure_directory, register_ku
            mem_dir = ensure_directory("viking://memories", user_id)
            ensure_directory(mem_dir, mem_type)
            # Register as a memory node
            mem_uri = f"{mem_dir}/{mem_type}/{mem_id[:12]}"
            with get_conn() as conn:
                parent_row = conn.execute(
                    "SELECT id FROM context_directory WHERE uri = ?",
                    (f"{mem_dir}/{mem_type}",),
                ).fetchone()
                parent_id = parent_row[0] if parent_row else None
                conn.execute(
                    """INSERT INTO context_directory
                       (id, parent_id, uri, node_type, ref_id, l0_content, depth)
                       VALUES (?, ?, ?, 'memory', ?, ?, ?)
                       ON CONFLICT (uri) DO NOTHING""",
                    (_gen_id("mdir"), parent_id, mem_uri, mem_id,
                     content[:200], mem_uri.count("/")),
                )
        except Exception:
            pass  # Non-critical

    extracted = sum(by_type.values())
    logger.info("memory_extractor: session %s → %d memories (%s)",
                session_id[:12], extracted, by_type)
    return {"extracted": extracted, "by_type": by_type}


# ── Memory retrieval ─────────────────────────────────────────────────────────

def get_relevant_memories(user_id: str, query: str,
                          limit: int = 5) -> list[dict[str, Any]]:
    """Get memories relevant to a query, sorted by relevance.

    Uses embedding similarity search.
    """
    if not query:
        # Return most recent memories if no query
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT id, memory_type, content, confidence, tags, created_at
                   FROM long_term_memories
                   WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [
            {"id": r[0], "type": r[1], "content": r[2], "confidence": r[3],
             "tags": r[4], "created_at": str(r[5])}
            for r in rows
        ]

    # Vector search
    query_emb = _get_embedding(query)
    if not query_emb:
        return []

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, memory_type, content, confidence, tags, embedding, created_at
               FROM long_term_memories
               WHERE user_id = ? AND embedding IS NOT NULL""",
            (user_id,),
        ).fetchall()

    # Compute similarities
    query_np = np.array(query_emb)
    scored = []
    for r in rows:
        mem_id, mem_type, content, confidence, tags, emb, created_at = r
        if not emb:
            continue
        try:
            emb_list = list(emb) if not isinstance(emb, list) else emb
            emb_np = np.array(emb_list)
            score = float(np.dot(query_np, emb_np) / (
                np.linalg.norm(query_np) * np.linalg.norm(emb_np)
            ))
            scored.append({
                "id": mem_id, "type": mem_type, "content": content,
                "confidence": confidence, "tags": tags,
                "score": round(score, 4), "created_at": str(created_at),
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def list_memories(user_id: str, memory_type: str | None = None,
                  limit: int = 50) -> list[dict]:
    """List all memories for a user."""
    with get_conn() as conn:
        if memory_type:
            rows = conn.execute(
                """SELECT id, memory_type, content, confidence, tags, created_at
                   FROM long_term_memories
                   WHERE user_id = ? AND memory_type = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, memory_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, memory_type, content, confidence, tags, created_at
                   FROM long_term_memories
                   WHERE user_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
    return [
        {"id": r[0], "type": r[1], "content": r[2], "confidence": r[3],
         "tags": r[4], "created_at": str(r[5])}
        for r in rows
    ]


def get_memory_stats(user_id: str) -> dict[str, Any]:
    """Get memory statistics."""
    with get_conn() as conn:
        total = conn.execute(
            "SELECT count(*) FROM long_term_memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        by_type = conn.execute(
            """SELECT memory_type, count(*)
               FROM long_term_memories WHERE user_id = ?
               GROUP BY memory_type""",
            (user_id,),
        ).fetchall()
        avg_conf = conn.execute(
            "SELECT AVG(confidence) FROM long_term_memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
    return {
        "total": total,
        "by_type": {r[0]: r[1] for r in by_type},
        "avg_confidence": round(float(avg_conf), 3) if avg_conf else 0,
    }
