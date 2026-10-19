"""AII Notes CRUD — PostgreSQL service layer.

Append-only version history (note_revisions) plus soft-delete-by-default
with a trash bin. Every data path checks note ownership against the
authenticated user_id; cross-user access returns 404 (corpus isolation).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from stratum.changefeed import emit_event
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


def _get_owned_note_or_404(note_id: str, user_id: str) -> dict:
    """Fetch a note the caller owns (soft-deleted included); 404 otherwise."""
    note = read("notes_sl", note_id)
    if not note or note.get("user_id") != user_id:
        raise HTTPException(404, "Note not found")
    return note


def _snapshot_revision(note_id: str, note: dict, user_id: str, cause: str) -> int:
    """Append one revision row capturing the note's *current* content.

    Revisions are INSERT-only; the next version is MAX(version) + 1.
    Returns the new version number.
    """
    rows = query(
        "SELECT MAX(version) AS max_v FROM note_revisions WHERE note_id = %(nid)s",
        {"nid": note_id},
    )
    next_version = (rows[0]["max_v"] or 0) + 1
    insert(
        "note_revisions",
        {
            "id": generate_ulid(),
            "note_id": note_id,
            "version": next_version,
            "title": note.get("title"),
            "content_markdown": note.get("content_markdown"),
            "author_user_id": user_id,
            "cause": cause,
            "created_at": now_utc(),
        },
    )
    return next_version


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
    await emit_event(user_id, "note_create", {"note_id": note_id, "title": body.title})
    return {"note_id": note_id, "status": "created"}


@router.get("/notes")
async def list_notes(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT id, title, updated_at FROM notes_sl WHERE user_id = %(uid)s AND deleted_at IS NULL ORDER BY updated_at DESC",
        {"uid": user_id},
    )


# NOTE: /notes/trash is registered before /notes/{note_id} so the static
# segment is not swallowed by the note_id path parameter.
@router.get("/notes/trash")
async def trash_notes(user_id: str = Depends(jwt_auth)):
    """List the current user's soft-deleted notes (the trash bin)."""
    return query(
        "SELECT id, title, updated_at, deleted_at FROM notes_sl "
        "WHERE user_id = %(uid)s AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
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
    # Snapshot the pre-edit content before overwriting (append-only history).
    new_version = _snapshot_revision(note_id, existing, user_id, cause="edit")
    changes["updated_at"] = now_utc()
    update("notes_sl", note_id, changes)
    await emit_event(user_id, "note_update", {"note_id": note_id, "version": new_version})
    return {"note_id": note_id, "status": "updated", "version": new_version}


@router.get("/notes/{note_id}/revisions")
async def list_revisions(note_id: str, user_id: str = Depends(jwt_auth)):
    """Version history of a note, newest first. Owner-checked; includes
    revisions of soft-deleted notes (history survives trash)."""
    _get_owned_note_or_404(note_id, user_id)
    return query(
        "SELECT id, version, title, content_markdown, author_user_id, cause, created_at "
        "FROM note_revisions WHERE note_id = %(nid)s ORDER BY version DESC",
        {"nid": note_id},
    )


@router.post("/notes/{note_id}/revisions/{rev}/restore")
async def restore_revision(note_id: str, rev: int, user_id: str = Depends(jwt_auth)):
    """Restore an old version *as a new version*: the current content is
    snapshotted first (cause='restore'), then the note row is rewritten with
    the target version's content. History is never overwritten."""
    existing = read("notes_sl", note_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Note not found")
    targets = query(
        "SELECT version, title, content_markdown FROM note_revisions "
        "WHERE note_id = %(nid)s AND version = %(v)s",
        {"nid": note_id, "v": rev},
    )
    if not targets:
        raise HTTPException(404, "Revision not found")
    target = targets[0]
    new_version = _snapshot_revision(note_id, existing, user_id, cause="restore")
    update(
        "notes_sl",
        note_id,
        {
            "title": target["title"],
            "content_markdown": target["content_markdown"],
            "updated_at": now_utc(),
        },
    )
    await emit_event(
        user_id,
        "note_restore",
        {"note_id": note_id, "restored_version": rev, "new_version": new_version},
    )
    return {"note_id": note_id, "status": "restored", "version": new_version}


@router.post("/notes/{note_id}/restore")
async def restore_note(note_id: str, user_id: str = Depends(jwt_auth)):
    """Recover a soft-deleted note from the trash bin."""
    note = _get_owned_note_or_404(note_id, user_id)
    if not note.get("deleted_at"):
        return {"note_id": note_id, "status": "unchanged"}
    update("notes_sl", note_id, {"deleted_at": None, "updated_at": now_utc()})
    await emit_event(user_id, "note_undelete", {"note_id": note_id})
    return {"note_id": note_id, "status": "restored"}


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    purge: bool = Query(False, description="If true, hard purge; default is soft-delete"),
    user_id: str = Depends(jwt_auth),
):
    existing = read("notes_sl", note_id)
    if not existing or existing.get("user_id") != user_id:
        raise HTTPException(404, "Note not found")
    if purge:
        from stratum.services.purge_service import purge_note

        out = purge_note(note_id, user_id)
        if out.get("status") == "not_found":
            raise HTTPException(404, "Note not found")
        mode = "hard"
    else:
        if existing.get("deleted_at"):
            raise HTTPException(404, "Note not found")
        soft_delete("notes_sl", note_id)
        mode = "soft"
    await emit_event(user_id, "note_delete", {"note_id": note_id, "mode": mode})
    return {"note_id": note_id, "status": "deleted", "mode": mode}


@router.get("/notes/{note_id}/backlinks")
async def note_backlinks(note_id: str, user_id: str = Depends(jwt_auth)):
    """Return notes that contain a [[note_id]] wikilink to this note."""
    existing = read("notes_sl", note_id)
    if not existing or existing.get("user_id") != user_id or existing.get("deleted_at"):
        raise HTTPException(404, "Note not found")
    rows = query(
        "SELECT id, title, created_at FROM notes_sl "
        "WHERE user_id = %(user_id)s "
        "AND deleted_at IS NULL "
        "AND content_markdown LIKE %(pattern)s "
        "AND id != %(note_id)s "
        "ORDER BY created_at DESC LIMIT 50",
        {"user_id": user_id, "pattern": f"%[[{note_id}]]%", "note_id": note_id},
    )
    return {"note_id": note_id, "backlinks": rows}
