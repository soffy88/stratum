"""Working Memory — 7 段结构化 WM (对标 OpenViking Working Memory v2).

7 sections:
  1. Session Title — 会话标题
  2. Current State — 当前状态
  3. Task & Goals — 任务和目标
  4. Key Facts & Decisions — 关键事实和决策
  5. Files & Context — 文件和上下文引用
  6. Errors & Corrections — 错误和修正
  7. Open Issues — 未解决问题

每个 section 支持 KEEP / UPDATE / APPEND 操作.
WM 存储在 agent_sessions.meta_json->'working_memory'.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from stratum.config import OLLAMA_BASE_URL
from stratum.db import get_conn

logger = logging.getLogger(__name__)

_OLLAMA_BASE = OLLAMA_BASE_URL
_MODEL = "qwen3-8b"

WM_SECTIONS = [
    "Session Title",
    "Current State",
    "Task & Goals",
    "Key Facts & Decisions",
    "Files & Context",
    "Errors & Corrections",
    "Open Issues",
]

# ── LLM call ─────────────────────────────────────────────────────────────────


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
        logger.warning("WM LLM call failed: %s", exc)
        return ""


# ── WM operations ────────────────────────────────────────────────────────────


def create_working_memory(session_id: str, title: str = "") -> dict[str, str]:
    """Create initial Working Memory for a session."""
    wm = {section: "" for section in WM_SECTIONS}
    wm["Session Title"] = title or f"Session {session_id[:12]}"
    wm["Current State"] = "Session initialized, awaiting first message."
    wm["Open Issues"] = "None yet."
    _save_wm(session_id, wm)
    return wm


def get_working_memory(session_id: str) -> dict[str, str] | None:
    """Get current Working Memory for a session."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT meta_json FROM agent_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    meta = json.loads(row[0]) if row[0] else {}
    return meta.get("working_memory")


def update_working_memory(session_id: str, messages: list[dict]) -> dict[str, str]:
    """Update Working Memory based on new messages.

    Uses LLM to determine what to KEEP / UPDATE / APPEND per section.
    """
    current_wm = get_working_memory(session_id)
    if not current_wm:
        current_wm = create_working_memory(session_id)

    # Only process recent messages
    recent = messages[-10:]  # last 10 messages
    if not recent:
        return current_wm

    # Build conversation summary
    conversation = "\n".join(f"[{m['role']}] {m['content'][:200]}" for m in recent)

    # Ask LLM to update each section
    updated_wm = dict(current_wm)
    for section in WM_SECTIONS:
        if section == "Session Title":
            continue  # Don't change title after creation

        current_content = current_wm.get(section, "")
        new_content = _update_section(section, current_content, conversation)
        if new_content and new_content != current_content:
            updated_wm[section] = new_content

    _save_wm(session_id, updated_wm)
    return updated_wm


def _update_section(section: str, current: str, conversation: str) -> str:
    """Ask LLM to update a specific WM section."""
    prompt = f"""You are maintaining a structured Working Memory for an AI agent session.

Current section: ## {section}
Current content:
{current if current else "(empty)"}

Recent conversation:
{conversation}

Update this section based on the conversation. Rules:
- If nothing new is relevant to this section, output the EXACT current content unchanged.
- If there are new facts/decisions/errors/issues, APPEND them as new bullet points.
- If the current content is outdated, UPDATE it.
- Keep it concise (under 500 characters).
- Output ONLY the section content, no headers or explanations."""

    result = _call_llm(
        [
            {
                "role": "system",
                "content": "You maintain structured working memory for AI agents. Be concise and precise.",
            },
            {"role": "user", "content": prompt},
        ]
    )

    return result if result else current


def _save_wm(session_id: str, wm: dict[str, str]) -> None:
    """Save Working Memory to session meta_json."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT meta_json FROM agent_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        meta = json.loads(row[0]) if row and row[0] else {}
        meta["working_memory"] = wm
        conn.execute(
            "UPDATE agent_sessions SET meta_json = ?::jsonb WHERE id = ?",
            (json.dumps(meta, ensure_ascii=False), session_id),
        )


def render_working_memory(wm: dict[str, str]) -> str:
    """Render WM as formatted markdown."""
    parts = []
    for section in WM_SECTIONS:
        content = wm.get(section, "")
        parts.append(f"## {section}\n{content if content else '(empty)'}")
    return "\n\n".join(parts)
