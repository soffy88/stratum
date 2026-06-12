"""Highlight CRUD — Phase 17.12 version."""

from fastapi import APIRouter, Depends, HTTPException

from stratum.api.deps import get_current_user
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/highlights", tags=["highlights"])


@router.get("")
async def list_highlights(user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.created_at
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
            "created_at": str(r[6]),
        }
        for r in rows
    ]


@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(highlight_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        conn.execute("DELETE FROM highlights WHERE id=?", (highlight_id,))
