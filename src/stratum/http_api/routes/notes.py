"""Note routes: get backlinks."""
import os
from typing import Optional

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ...dao.note import NoteDAO

router = APIRouter()


def get_db():
    conn = duckdb.connect(os.path.expanduser("~/.stratum/meta.duckdb"))
    try:
        yield conn
    finally:
        conn.close()


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
        (corpus_id, f"%{note_id}%")
    ).fetchall()
    backlinks = [BacklinkItem(id=r[0], title=r[1], snippet=(r[2] or "")[:100]) for r in rows if r[0] != note_id]
    return {"items": backlinks, "total": len(backlinks)}
