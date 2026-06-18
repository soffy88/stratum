"""Highlight CRUD — Phase 17.12 version."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/highlights", tags=["highlights"])


class HighlightCreate(BaseModel):
    substrate_id: str
    color: str = "yellow"
    text: str
    note: Optional[str] = None
    location_json: dict[str, Any] = {}  # PDF: {page, rects} / EPUB: {cfi}


@router.post("", status_code=201)
async def create_highlight(body: HighlightCreate, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    hid = generate_ulid()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO highlights (id, user_id, substrate_id, color, text, note, location_json) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                hid,
                uh,
                body.substrate_id,
                body.color,
                body.text,
                body.note,
                json.dumps(body.location_json),
            ),
        )
        row = conn.execute(
            "SELECT id, color, text, note, substrate_id, location_json, created_at "
            "FROM highlights WHERE id=?",
            (hid,),
        ).fetchone()
    if not row:
        raise HTTPException(500, "Failed to create highlight")
    return {
        "id": row[0],
        "color": row[1],
        "text": row[2],
        "note": row[3],
        "substrate_id": row[4],
        "location_json": json.loads(row[5] or "{}"),
        "created_at": str(row[6]),
    }


@router.get("")
async def list_highlights(substrate_id: Optional[str] = None, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        if substrate_id:
            rows = conn.execute(
                """
                SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.location_json, h.created_at
                FROM highlights h
                LEFT JOIN substrates s ON h.substrate_id = s.id
                WHERE h.user_id = ? AND h.substrate_id = ?
                ORDER BY h.created_at DESC
                """,
                (uh, substrate_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.location_json, h.created_at
                FROM highlights h
                LEFT JOIN substrates s ON h.substrate_id = s.id
                WHERE h.user_id = ?
                ORDER BY h.created_at DESC
                """,
                (uh,),
            ).fetchall()
    return [
        {
            "id": r[0],
            "color": r[1],
            "text": r[2],
            "note": r[3],
            "substrate_id": r[4],
            "substrate_title": r[5],
            "location_json": json.loads(r[6] or "{}"),
            "created_at": str(r[7]),
        }
        for r in rows
    ]


@router.patch("/{highlight_id}")
async def update_highlight(highlight_id: str, body: dict, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        updates = {k: v for k, v in body.items() if k in ("color", "note")}
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE highlights SET {sets} WHERE id=?", (*updates.values(), highlight_id)
            )
    return {"ok": True}


@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(highlight_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        conn.execute("DELETE FROM highlights WHERE id=?", (highlight_id,))
