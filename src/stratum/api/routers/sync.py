"""Sync status + changefeed pull + vault folder sync (MVP week 5–6)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stratum.common import get_local_state, jwt_auth, user_changefeed_path
from stratum.db import query
from stratum.utils.user_id_hash import hash_user_id

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


class VaultSyncRequest(BaseModel):
    path: str = Field(..., description="Local or mounted cloud path under allowed roots")
    mode: str = Field("export", description="export | import | both")


@router.get("/status")
async def sync_status(user_id: str = Depends(jwt_auth)):
    local = get_local_state(user_id)
    # Routers emit events under either the raw JWT subject (notes/concepts) or
    # its hash (documents/highlights/views) — match both forms.
    rows = query(
        "SELECT COUNT(*) AS cnt FROM changefeed "
        "WHERE user_id IN (%(uid)s, %(huid)s) AND processed = FALSE",
        {"uid": user_id, "huid": hash_user_id(user_id)},
        limit=1,
    )
    pending = rows[0]["cnt"] if rows else 0
    return {
        "is_fully_synced": pending == 0,
        "pending_count": pending,
        **local,
    }


@router.get("/vault/roots")
async def vault_sync_roots(user_id: str = Depends(jwt_auth)):
    """List allowed filesystem roots for vault sync."""
    from stratum.services.vault_sync_service import allowed_roots

    return {"roots": [str(r) for r in allowed_roots()]}


@router.post("/vault")
async def vault_sync(body: VaultSyncRequest, user_id: str = Depends(jwt_auth)):
    """Export knowledge vault to a folder, import notes MD, or both.

    Path must be under STRATUM_VAULT_SYNC_ROOTS (mounted gdrive/rclone OK).
    """
    from stratum.services.vault_sync_service import sync_vault

    try:
        return sync_vault(user_id, body.path, mode=body.mode)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except OSError as e:
        raise HTTPException(500, f"filesystem error: {e}") from e


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
        "WHERE user_id IN (%(uid)s, %(huid)s) AND seq > %(since)s "
        "AND event_type = ANY(%(types)s) "
        "ORDER BY seq ASC",
        {
            "uid": user_id,
            "huid": hash_user_id(user_id),
            "since": since,
            "types": allowed_types,
        },
        limit=limit,
    )
    latest_seq = rows[-1]["seq"] if rows else since
    return {
        "events": rows,
        "latest_seq": latest_seq,
        "has_more": len(rows) == limit,
        "scope": scope_keys,
    }
