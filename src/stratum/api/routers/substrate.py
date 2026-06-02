"""Substrate pin / unpin."""

from fastapi import APIRouter, Depends, HTTPException

from stratum.changefeed import emit_event
from stratum.common import jwt_auth, now_utc
from stratum.db import read, update

router = APIRouter(prefix="/api/v1/substrate", tags=["substrate"])


@router.post("/{substrate_id}/pin")
async def pin_substrate(substrate_id: str, user_id: str = Depends(jwt_auth)):
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != user_id:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": True, "pinned_at": now_utc()})
    await emit_event(user_id, "substrate_pin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "pinned"}


@router.post("/{substrate_id}/unpin")
async def unpin_substrate(substrate_id: str, user_id: str = Depends(jwt_auth)):
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != user_id:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": False, "pinned_at": None})
    await emit_event(user_id, "substrate_unpin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "unpinned"}
