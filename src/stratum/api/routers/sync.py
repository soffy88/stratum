"""Sync status + changefeed pull."""

from fastapi import APIRouter, Depends

from stratum.common import get_local_state, jwt_auth, user_changefeed_path
from stratum.db import query

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.get("/status")
async def sync_status(user_id: str = Depends(jwt_auth)):
    local = get_local_state(user_id)
    # Count pending changefeed events
    rows = query(
        "SELECT COUNT(*) AS cnt FROM changefeed WHERE user_id = %(uid)s AND processed = FALSE",
        {"uid": user_id},
        limit=1,
    )
    pending = rows[0]["cnt"] if rows else 0
    return {
        "is_fully_synced": pending == 0,
        "pending_count": pending,
        **local,
    }


@router.get("/changefeed")
async def pull_changefeed(since: int = 0, limit: int = 50, user_id: str = Depends(jwt_auth)):
    rows = query(
        "SELECT seq, event_id, event_type, payload, timestamp "
        "FROM changefeed "
        "WHERE user_id = %(uid)s AND seq > %(since)s "
        "ORDER BY seq ASC",
        {"uid": user_id, "since": since},
        limit=limit,
    )
    latest_seq = rows[-1]["seq"] if rows else since
    return {
        "events": rows,
        "latest_seq": latest_seq,
        "has_more": len(rows) == limit,
    }
