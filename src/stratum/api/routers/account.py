"""Account management — delete account."""

import asyncio

from fastapi import APIRouter, Depends

from stratum.common import jwt_auth
from stratum.db import query

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.post("/delete")
async def delete_account(user_id: str = Depends(jwt_auth)):
    """Purge user knowledge data (MVP 真删). Account tombstone kept for audit."""
    from stratum.common import generate_ulid, now_utc
    from stratum.db import insert
    from stratum.services.purge_service import purge_concept, purge_note, purge_substrate
    from stratum.utils.user_id_hash import hash_user_id

    uh = hash_user_id(user_id)
    purged = {"notes": 0, "concepts": 0, "substrates": 0}

    # notes_sl (live table name; legacy "notes" soft-delete kept as best-effort)
    for table, key, purger in (
        ("notes_sl", "notes", purge_note),
        ("concepts", "concepts", purge_concept),
    ):
        try:
            rows = query(
                f"SELECT id FROM {table} WHERE user_id = %(uid)s",
                {"uid": user_id},
            )
        except Exception:
            rows = []
        for row in rows:
            purger(row["id"], user_id)
            purged[key] += 1

    try:
        rows = query(
            "SELECT id FROM substrates WHERE user_id = %(uh)s OR user_id = %(uid)s",
            {"uh": uh, "uid": user_id},
        )
    except Exception:
        rows = []
    for row in rows:
        purge_substrate(row["id"], user_id)
        purged["substrates"] += 1

    insert(
        "changefeed",
        {
            "event_id": generate_ulid(),
            "user_id": user_id,
            "device_id": "server",
            "event_type": "account_delete_requested",
            "payload": {
                "mode": "hard",
                "purged": purged,
                "requested_at": now_utc(),
            },
        },
    )

    return {
        "status": "purged",
        "mode": "hard",
        "purged": purged,
        "message": "Account knowledge data permanently deleted.",
    }
