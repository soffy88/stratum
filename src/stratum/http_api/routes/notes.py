"""Note routes: get single note + backlinks."""

import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.note import NoteDAO

router = APIRouter()


def get_db():
    from stratum.db import get_conn
    with get_conn() as conn:
        yield conn


class NoteDetail(BaseModel):
    """Single note — public schema (no corpus_id returned)."""

    id: str
    title: Optional[str] = None
    content: Optional[str] = None
    wikilinks: list[str] = []
    substrate_id: Optional[str] = None
    meta_json: dict[str, Any] = {}
    created_at: str
    updated_at: str


@router.get("/notes/{note_id}", response_model=NoteDetail, summary="Get single note")
async def get_note(note_id: str, request: Request, db=Depends(get_db)):
    """Return a single note by id (corpus-isolated)."""
    corpus_id = request.state.corpus_id
    note = NoteDAO(db).get_note(note_id=note_id, corpus_id=corpus_id)
    if not note:
        raise HTTPException(404, "Note not found")
    # Parse wikilinks JSON string → list
    wikilinks: list[str] = []
    if note.wikilinks:
        try:
            wikilinks = json.loads(note.wikilinks) if isinstance(note.wikilinks, str) else []
        except (json.JSONDecodeError, TypeError):
            wikilinks = []
    meta: dict[str, Any] = {}
    if note.meta_json:
        try:
            meta = json.loads(note.meta_json) if isinstance(note.meta_json, str) else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
    return NoteDetail(
        id=note.id,
        title=note.title,
        content=note.content,
        wikilinks=wikilinks,
        substrate_id=note.substrate_id,
        meta_json=meta,
        created_at=note.created_at.isoformat() if note.created_at else "",
        updated_at=note.updated_at.isoformat() if note.updated_at else "",
    )


class BacklinkItem(BaseModel):
    id: str
    title: str
    snippet: Optional[str] = None


@router.get("/notes/{note_id}/backlinks")
async def get_backlinks(note_id: str, request: Request, db=Depends(get_db)):
    corpus_id = request.state.corpus_id
    # Verify note ownership
    note = NoteDAO(db).get_note(note_id=note_id, corpus_id=corpus_id)
    if not note:
        raise HTTPException(404, "Note not found")

    # Find notes that reference this note_id in their wikilinks
    rows = db.execute(
        "SELECT id, title, content FROM note WHERE corpus_id = ? AND wikilinks LIKE ?",
        (corpus_id, f"%{note_id}%"),
    ).fetchall()
    backlinks = [
        BacklinkItem(id=r[0], title=r[1], snippet=(r[2] or "")[:100])
        for r in rows
        if r[0] != note_id
    ]
    return {"items": backlinks, "total": len(backlinks)}
