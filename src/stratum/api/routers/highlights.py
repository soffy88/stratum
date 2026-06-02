"""Highlight CRUD."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from stratum.changefeed import emit_event
from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query, soft_delete

router = APIRouter(prefix="/api/v1/highlights", tags=["highlights"])


class HighlightCreate(BaseModel):
    content_id: str | None = None
    substrate_id: str | None = None
    anchor: dict
    color: str = "yellow"
    note: str | None = None


@router.post("")
async def create_highlight(body: HighlightCreate, user_id: str = Depends(jwt_auth)):
    if not body.content_id and not body.substrate_id:
        raise HTTPException(400, "content_id or substrate_id required")
    hid = generate_ulid()
    insert(
        "highlights",
        {
            "id": hid,
            "user_id": user_id,
            "content_id": body.content_id,
            "substrate_id": body.substrate_id,
            "anchor": body.anchor,
            "color": body.color,
            "note": body.note,
            "created_at": now_utc(),
        },
    )
    await emit_event(user_id, "highlight_create", {"highlight_id": hid})
    return {"highlight_id": hid, "status": "created"}


@router.get("")
async def list_highlights(
    content_id: str | None = None,
    substrate_id: str | None = None,
    user_id: str = Depends(jwt_auth),
):
    if content_id:
        return query(
            "SELECT * FROM highlights WHERE user_id = %(uid)s AND content_id = %(cid)s AND status = 'active'",
            {"uid": user_id, "cid": content_id},
        )
    if substrate_id:
        return query(
            "SELECT * FROM highlights WHERE user_id = %(uid)s AND substrate_id = %(sid)s AND status = 'active'",
            {"uid": user_id, "sid": substrate_id},
        )
    return query(
        "SELECT * FROM highlights WHERE user_id = %(uid)s AND status = 'active' ORDER BY created_at DESC",
        {"uid": user_id},
    )


@router.delete("/{highlight_id}")
async def delete_highlight(highlight_id: str, user_id: str = Depends(jwt_auth)):
    from stratum.db import update

    rows = query(
        "SELECT id, user_id FROM highlights WHERE id = %(hid)s",
        {"hid": highlight_id},
        limit=1,
    )
    if not rows or rows[0].get("user_id") != user_id:
        raise HTTPException(404, "Highlight not found")
    update("highlights", highlight_id, {"status": "deleted"})
    await emit_event(user_id, "highlight_delete", {"highlight_id": highlight_id})
    return {"highlight_id": highlight_id, "status": "deleted"}
