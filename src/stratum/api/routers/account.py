"""Account management — delete account."""

import asyncio

from fastapi import APIRouter, Depends

from stratum.common import ensure_dir, jwt_auth, user_data_dir
from stratum.db import soft_delete, query

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.post("/delete")
async def delete_account(user_id: str = Depends(jwt_auth)):
    """Soft-delete all user data. Hard deletion runs after 30-day grace period."""
    from stratum.common import now_utc

    # Soft-delete notes and concepts
    for table in ("notes", "concepts"):
        rows = query(
            f"SELECT id FROM {table} WHERE user_id = %(uid)s AND deleted_at IS NULL",
            {"uid": user_id},
        )
        for row in rows:
            soft_delete(table, row["id"])

    # Mark substrates deleted
    rows = query(
        "SELECT id FROM substrates WHERE user_id = %(uid)s",
        {"uid": user_id},
    )
    for row in rows:
        soft_delete("substrates", row["id"])

    # Record deletion request in changefeed
    from stratum.common import generate_ulid
    from stratum.db import insert

    insert(
        "changefeed",
        {
            "event_id": generate_ulid(),
            "user_id": user_id,
            "device_id": "server",
            "event_type": "account_delete_requested",
            "payload": {"grace_days": 30, "requested_at": now_utc()},
        },
    )

    return {
        "status": "scheduled",
        "message": "Account and all data will be permanently deleted after 30-day grace period.",
    }
