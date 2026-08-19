"""Session & Memory API — Agent 会话 + 长期记忆 (对标 OpenViking Session)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from stratum.common import jwt_auth

router = APIRouter(prefix="/api/v1", tags=["sessions"])


# ── Request models ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str | None = None


class AddMessageRequest(BaseModel):
    role: str  # user / assistant / system / tool
    content: str
    parts: list[dict] | None = None


def _session_or_404(session_id: str, user_id: str):
    from stratum.services.session_manager import get_session

    session = get_session(session_id, user_id=user_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


# ── Session CRUD ─────────────────────────────────────────────────────────────

@router.post("/sessions")
async def create_session(req: CreateSessionRequest, user_id: str = Depends(jwt_auth)):
    """创建 Agent 会话."""
    from stratum.services.session_manager import create_session as _create
    return _create(user_id, title=req.title)


@router.get("/sessions")
async def list_sessions(
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(jwt_auth),
):
    """列出会话."""
    from stratum.services.session_manager import list_sessions as _list
    return {"sessions": _list(user_id, status=status, limit=limit)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = Depends(jwt_auth)):
    """获取会话详情."""
    return _session_or_404(session_id, user_id)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(jwt_auth)):
    """删除会话."""
    from stratum.services.session_manager import delete_session as _del

    out = _del(session_id, user_id=user_id)
    if out.get("error") == "not_found":
        raise HTTPException(404, "Session not found")
    return out


@router.post("/sessions/{session_id}/archive")
async def archive_session(session_id: str, user_id: str = Depends(jwt_auth)):
    """归档会话."""
    from stratum.services.session_manager import archive_session as _archive

    _session_or_404(session_id, user_id)
    out = _archive(session_id, user_id=user_id)
    if out.get("error") == "not_found":
        raise HTTPException(404, "Session not found")
    return out


# ── Messages ─────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, req: AddMessageRequest,
                      user_id: str = Depends(jwt_auth)):
    """添加消息到会话."""
    from stratum.services.session_manager import add_message as _add
    if req.role not in ("user", "assistant", "system", "tool"):
        raise HTTPException(400, f"Invalid role: {req.role}")
    out = _add(session_id, req.role, req.content, req.parts, user_id=user_id)
    if out.get("error") == "not_found":
        raise HTTPException(404, "Session not found")
    return out


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(jwt_auth),
):
    """获取会话消息."""
    from stratum.services.session_manager import get_messages as _get

    _session_or_404(session_id, user_id)
    return {"messages": _get(session_id, limit=limit, offset=offset, user_id=user_id)}


# ── Commit ───────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/commit")
async def commit_session(session_id: str, user_id: str = Depends(jwt_auth)):
    """提交会话 — 触发压缩 + 记忆提取 + WM 更新."""
    from stratum.services.session_manager import commit_session as _commit

    out = await _commit(session_id, user_id)
    if out.get("error") == "Session not found":
        raise HTTPException(404, "Session not found")
    return out


# ── Context ──────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/context")
async def get_context(
    session_id: str,
    q: str | None = Query(None, description="Optional query for retrieval"),
    max_tokens: int = Query(4000, ge=500, le=16000),
    user_id: str = Depends(jwt_auth),
):
    """获取 Agent 上下文 (WM + 记忆 + 检索结果)."""
    from stratum.services.session_manager import get_context as _ctx

    _session_or_404(session_id, user_id)
    return await _ctx(session_id, query=q, user_id=user_id, max_tokens=max_tokens)


# ── Working Memory ───────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/working-memory")
async def get_working_memory(session_id: str, user_id: str = Depends(jwt_auth)):
    """获取 Working Memory."""
    from stratum.services.working_memory import get_working_memory, render_working_memory

    _session_or_404(session_id, user_id)
    wm = get_working_memory(session_id)
    if not wm:
        raise HTTPException(404, "Working Memory not found")
    return {
        "session_id": session_id,
        "sections": wm,
        "rendered": render_working_memory(wm),
    }


# ── Memories ─────────────────────────────────────────────────────────────────

@router.get("/memories")
async def list_memories(
    memory_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(jwt_auth),
):
    """列出长期记忆."""
    from stratum.services.memory_extractor import list_memories as _list
    return {"memories": _list(user_id, memory_type=memory_type, limit=limit)}


@router.get("/memories/search")
async def search_memories(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    user_id: str = Depends(jwt_auth),
):
    """语义搜索记忆."""
    from stratum.services.memory_extractor import get_relevant_memories
    return {"memories": get_relevant_memories(user_id, q, limit=limit)}


@router.get("/memories/stats")
async def memory_stats(user_id: str = Depends(jwt_auth)):
    """记忆统计."""
    from stratum.services.memory_extractor import get_memory_stats
    return get_memory_stats(user_id)
