"""Share routes: create/list/revoke shares + public access."""
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.share_tokens import ShareTokenDAO
from ...dao.note import NoteDAO
from ...dao.users import UserDAO
from ...auth.jwt_handler import decode_access

router = APIRouter()


def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn


# --- Schemas ---

class CreateShareRequest(BaseModel):
    expires_in_days: Optional[int] = None
    allow_anonymous: bool = True


class CreateShareResponse(BaseModel):
    token: str
    share_url: str
    expires_at: Optional[datetime] = None


class ShareTokenPublic(BaseModel):
    token: str
    resource_type: str
    resource_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int


class ListSharesResponse(BaseModel):
    items: list[ShareTokenPublic]
    total: int


class PublicNoteResponse(BaseModel):
    title: str
    content: str
    shared_by_username: str
    shared_at: datetime


# --- Helpers ---

def _get_auth_user(request: Request) -> dict:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization")
    try:
        return decode_access(auth.split(" ")[1])
    except Exception:
        raise HTTPException(401, "Invalid token")


def _strip_private_refs(content: str) -> str:
    """Remove wikilinks to private notes from shared content."""
    return re.sub(r'\[\[_private[^\]]*\]\]', '[私有引用]', content or "")


# --- Authenticated routes ---

@router.post("/api/share/note/{note_id}", response_model=CreateShareResponse)
async def create_share(note_id: str, req: CreateShareRequest, request: Request, db=Depends(get_db)):
    user = _get_auth_user(request)
    user_id = user["sub"]
    corpus_id = user["corpus_id"]

    # Verify user owns the note
    note = NoteDAO(db).get_note(note_id=note_id, corpus_id=corpus_id)
    if not note:
        raise HTTPException(404, "Note not found")

    share = ShareTokenDAO(db).create_share_token(
        resource_type="note", resource_id=note_id, corpus_id=corpus_id,
        created_by=user_id, expires_in_days=req.expires_in_days,
        allow_anonymous=req.allow_anonymous,
    )
    return CreateShareResponse(
        token=share.token,
        share_url=f"/share/{share.token}",
        expires_at=share.expires_at,
    )


@router.get("/api/shares", response_model=ListSharesResponse)
async def list_shares(request: Request, db=Depends(get_db)):
    user = _get_auth_user(request)
    shares = ShareTokenDAO(db).list_user_shares(user["sub"])
    items = [ShareTokenPublic(token=s.token, resource_type=s.resource_type,
                              resource_id=s.resource_id, created_at=s.created_at,
                              expires_at=s.expires_at, access_count=s.access_count)
             for s in shares]
    return ListSharesResponse(items=items, total=len(items))


@router.delete("/api/share/{token}")
async def revoke_share(token: str, request: Request, db=Depends(get_db)):
    user = _get_auth_user(request)
    ok = ShareTokenDAO(db).revoke_share(token, user["sub"])
    if not ok:
        raise HTTPException(403, "Not authorized to revoke this share")
    return {"status": "revoked"}


# --- Public route (no auth) ---

@router.get("/share/{token}", response_model=PublicNoteResponse)
async def get_public_share(token: str, db=Depends(get_db)):
    dao = ShareTokenDAO(db)
    share = dao.get_share_token(token)
    if not share:
        raise HTTPException(404, "Share not found")
    if share.revoked_at:
        raise HTTPException(410, "Share has been revoked")
    if share.expires_at:
        expires = share.expires_at if share.expires_at.tzinfo else share.expires_at.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            raise HTTPException(410, "Share has expired")

    # Only notes supported in Phase 14
    if share.resource_type != "note":
        raise HTTPException(404, "Resource type not supported")

    note = NoteDAO(db).get_note(note_id=share.resource_id, corpus_id=share.corpus_id)
    if not note:
        raise HTTPException(404, "Shared resource no longer exists")

    # Get sharer username
    sharer = UserDAO(db).get_user_by_id(share.created_by)
    username = sharer.username if sharer else "unknown"

    # Increment access
    dao.increment_access(token)

    return PublicNoteResponse(
        title=note.title,
        content=_strip_private_refs(note.content),
        shared_by_username=username,
        shared_at=share.created_at,
    )
