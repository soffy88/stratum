"""User profile + sessions management routes."""

import hashlib
import os
from datetime import datetime
from typing import Optional

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...auth.jwt_handler import decode_access
from ...dao.profile import ProfileDAO
from ...dao.sessions import SessionDAO
from ...dao.users import UserDAO

router = APIRouter()


def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn


def _current_user_id(request: Request, db=None) -> str:
    """Extract user_id from Bearer token. Returns ULID (for session ops).
    sub is now email; look up user.id (ULID) so session table lookups still work."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")
    try:
        payload = decode_access(auth.split(" ")[1])
        sub = payload["sub"]
        if db and "@" in sub:
            user = UserDAO(db).get_user_by_email(sub)
            if user:
                return user.id
        return sub
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


# ── Public schemas ────────────────────────────────────────────────────────────


class UserProfilePublic(BaseModel):
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime


class SessionPublic(BaseModel):
    id: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None  # truncated to ≤16 chars
    created_at: datetime
    last_used_at: datetime
    is_current: bool = False


class SessionListResponse(BaseModel):
    items: list[SessionPublic]


# ── Public endpoint — no auth required ───────────────────────────────────────


@router.get("/by-username/{username}", response_model=UserProfilePublic)
async def get_user_by_username(username: str, db=Depends(get_db)):
    """Public profile lookup. No authentication required."""
    user = UserDAO(db).get_user_by_username(username)
    if not user or not user.is_active or user.is_suspended:
        raise HTTPException(404, "User not found")
    profile = ProfileDAO(db).get_profile(user.id)
    return UserProfilePublic(
        username=user.username,
        display_name=profile.display_name if profile else None,
        bio=profile.bio if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        created_at=user.created_at,
    )


# ── Authenticated endpoints ───────────────────────────────────────────────────


@router.get("/me/sessions", response_model=SessionListResponse)
async def list_my_sessions(request: Request, db=Depends(get_db)):
    user_id = _current_user_id(request, db)
    sessions = SessionDAO(db).list_user_sessions(user_id, active_only=True)

    # Identify current session via refresh_token cookie (absent in API tests → no match)
    current_hash: Optional[str] = None
    rt = request.cookies.get("refresh_token")
    if rt:
        current_hash = hashlib.sha256(rt.encode()).hexdigest()

    items = []
    for s in sessions:
        is_current = current_hash is not None and s.refresh_token_hash == current_hash
        ip = (s.ip_address or "")[:16] or None
        items.append(
            SessionPublic(
                id=s.id,
                user_agent=s.user_agent,
                ip_address=ip,
                created_at=s.created_at,
                last_used_at=s.last_used_at,
                is_current=is_current,
            )
        )
    return SessionListResponse(items=items)


@router.delete("/me/sessions/{session_id}")
async def revoke_my_session(session_id: str, request: Request, db=Depends(get_db)):
    user_id = _current_user_id(request, db)
    session = SessionDAO(db).get_session_by_id(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(404, "Session not found")
    SessionDAO(db).revoke_session(session_id)
    return {"status": "revoked"}
