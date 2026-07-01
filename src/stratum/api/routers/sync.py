"""Sync status + changefeed pull (Phase 15 P1-C1: scope filtering)."""

from fastapi import APIRouter, Depends

from stratum.common import get_local_state, jwt_auth, user_changefeed_path
from stratum.db import query

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

_EVENT_TYPES_BY_SCOPE: dict[str, list[str]] = {
    "notes": ["note_create", "note_update", "note_delete"],
    "substrates": ["substrate_create", "substrate_delete", "substrate_pin", "substrate_unpin"],
    "highlights": ["highlight_create", "highlight_delete"],
    "concepts": ["concept_create", "concept_update", "concept_delete"],
    "agents": ["agent_run_completed", "agent_run_failed"],
    "views": ["view_create", "view_default_changed"],
}

_ALL_SCOPE_KEYS = list(_EVENT_TYPES_BY_SCOPE)


@router.get("/status")
async def sync_status(user_id: str = Depends(jwt_auth)):
    local = get_local_state(user_id)
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
async def pull_changefeed(
    since: int = 0,
    limit: int = 50,
    scope: str = "notes,substrates,highlights,concepts",
    user_id: str = Depends(jwt_auth),
):
    """Pull changefeed events since `since` seq, filtered by scope.

    scope: comma-separated list of scope keys. Defaults to the 4 main data scopes.
    Available: notes, substrates, highlights, concepts, agents, views.
    """
    scope_keys = [s.strip() for s in scope.split(",") if s.strip()]
    allowed_types: list[str] = []
    for key in scope_keys:
        allowed_types.extend(_EVENT_TYPES_BY_SCOPE.get(key, []))

    if not allowed_types:
        return {"events": [], "latest_seq": since, "has_more": False}

    rows = query(
        "SELECT seq, event_id, event_type, payload, timestamp "
        "FROM changefeed "
        "WHERE user_id = %(uid)s AND seq > %(since)s "
        "AND event_type = ANY(%(types)s) "
        "ORDER BY seq ASC",
        {"uid": user_id, "since": since, "types": allowed_types},
        limit=limit,
    )
    latest_seq = rows[-1]["seq"] if rows else since
    return {
        "events": rows,
        "latest_seq": latest_seq,
        "has_more": len(rows) == limit,
        "scope": scope_keys,
    }
