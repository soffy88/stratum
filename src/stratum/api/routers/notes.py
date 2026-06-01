"""Notes CRUD — PostgreSQL service layer."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.common import generate_ulid, now_utc, jwt_auth
from stratum.db import insert, read, update, soft_delete, query

router = APIRouter(prefix="/api/v1", tags=["notes"])


class NoteCreate(BaseModel):
    title: str
    content_markdown: str
    substrate_refs: list[str] = []
    concept_refs: list[str] = []
    content_refs: list[str] = []


class NoteUpdate(BaseModel):
    title: str | None = None
    content_markdown: str | None = None


def _emit(user_id: str, event_type: str, payload: dict) -> None:
    try:
        insert(
            "changefeed",
            {
                "event_id": generate_ulid(),
                "user_id": user_id,
                "device_id": "server",
                "event_type": event_type,
                "payload": payload,
            },
            returning="seq",
        )
    except Exception:
        pass  # changefeed is best-effort


@router.post("/notes")
async def create_note(body: NoteCreate, user_id: str = Depends(jwt_auth)):
    note_id = generate_ulid()
    ts = now_utc()
    insert(
        "notes_sl",
        {
            "id": note_id,
            "user_id": user_id,
            "title": body.title,
            "content_markdown": body.content_markdown,
            "substrate_refs": body.substrate_refs,
            "concept_refs": body.concept_refs,
            "content_refs": body.content_refs,
            "created_at": ts,
            "updated_at": ts,
        },
    )
    _emit(user_id, "note_create", {"note_id": note_id, "title": body.title})
    return {"note_id": note_id, "status": "created"}


@router.get("/notes")
async def list_notes(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT id, title, updated_at FROM notes_sl WHERE user_id = %(uid)s AND deleted_at IS NULL ORDER BY updated_at DESC",
        {"uid": user_id},
    )


@router.get("/notes/{note_id}")
async def get_note(note_id: str, user_id: str = Depends(jwt_auth)):
    note = read("notes_sl", note_id)
    if not note or note.get("user_id") != user_id or note.get("deleted_at"):
        raise HTTPException(404, "Note not found")
    return note


@router.put("/notes/{note_id}")
async def update_note(note_id: str, body: NoteUpdate, user_id: str = Depends(jwt_auth)):
    existing = read("notes_sl", note_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Note not found")
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    if not changes:
        return {"note_id": note_id, "status": "unchanged"}
    changes["updated_at"] = now_utc()
    update("notes_sl", note_id, changes)
    _emit(user_id, "note_update", {"note_id": note_id})
    return {"note_id": note_id, "status": "updated"}


@router.delete("/notes/{note_id}")
async def delete_note(note_id: str, user_id: str = Depends(jwt_auth)):
    existing = read("notes_sl", note_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Note not found")
    soft_delete("notes_sl", note_id)
    _emit(user_id, "note_delete", {"note_id": note_id})
    return {"note_id": note_id, "status": "deleted"}
