"""Substrate CRUD — documents listing with view integration."""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from stratum.api.deps import get_current_user
from stratum.common import jwt_auth, now_utc
from stratum.db import get_conn, read, update
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("")
async def list_documents(
    view_id: Optional[str] = None,
    medium: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    tag_exclude: Optional[List[str]] = Query(None),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
):
    uh = hash_user_id(user.user_id)

    # view_id 传入 → load view filter 覆盖
    if view_id:
        with get_conn() as conn:
            v = conn.execute(
                "SELECT filter_json, sort_by, sort_order FROM user_saved_views WHERE id=? AND user_id=?",
                (view_id, uh),
            ).fetchone()
            if v:
                vf = json.loads(v[0]) if v[0] else {}
                medium = vf.get("medium") or medium
                tags = vf.get("tags") or tags
                tag_exclude = vf.get("tag_exclude") or tag_exclude
                sort_by = v[1] or sort_by
                sort_order = v[2] or sort_order

    # Build SQL with filters
    # For now, implementing a basic version that handles user isolation.
    # Full complex filtering logic would expand here.
    query_sql = f"SELECT * FROM substrates WHERE user_id = ?"
    params = [uh]

    # Simple medium filter implementation (assuming meta_json extraction or medium column)
    # The audit indicated substrates schema from migration 020 doesn't have a direct 'medium' column,
    # but uses 'mime'. Phase 17.12 instructions mention 'medium' logic.
    # Using mime as a proxy for medium in this recovery step if medium column missing.
    # Or check if medium column was added in 020? (Checking 020 again...)
    # 020 substrates: id, user_id, title, mime, source_path, file_hash, byte_size, page_count, parser, language, has_cjk, is_scanned, is_pinned, pinned_at, pin_priority, created_at, updated_at, meta_json

    # Simplified medium filter implementation
    if medium:
        # Check both direct 'mime' column and 'medium' field inside meta_json
        placeholders = ",".join(["?" for _ in medium])
        query_sql += f" AND (mime IN ({placeholders}) OR meta_json->>'$.medium' IN ({placeholders}))"
        params.extend(medium)
        params.extend(medium)

    query_sql += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query_sql, params).fetchall()
        # Mapping rows to dicts (assuming standard column order from 020+022)
        # This is a simplified list for recovery.
        return [dict(zip([d[0] for d in conn.description], r)) for r in rows]


@router.post("/{substrate_id}/pin")
async def pin_substrate(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != uh:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": True, "pinned_at": now_utc()})
    from stratum.changefeed import emit_event

    await emit_event(uh, "substrate_pin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "pinned"}


@router.post("/{substrate_id}/unpin")
async def unpin_substrate(substrate_id: str, user=Depends(get_current_user)):
    uh = hash_user_id(user.user_id)
    sub = read("substrates", substrate_id)
    if not sub or sub.get("user_id") != uh:
        raise HTTPException(404, "Substrate not found")
    update("substrates", substrate_id, {"is_pinned": False, "pinned_at": None})
    from stratum.changefeed import emit_event

    await emit_event(uh, "substrate_unpin", {"substrate_id": substrate_id})
    return {"substrate_id": substrate_id, "status": "unpinned"}
