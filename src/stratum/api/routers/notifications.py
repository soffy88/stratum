"""Notification dispatch."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query as db_query

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(jwt_auth),
):
    """List notification events from changefeed."""
    rows = db_query(
        "SELECT event_id AS id, payload, created_at "
        "FROM changefeed "
        "WHERE user_id = $uid AND event_type = 'notification' "
        "ORDER BY created_at DESC "
        "LIMIT $limit OFFSET $offset",
        {"uid": user_id, "limit": limit, "offset": offset},
    )
    items = []
    for r in rows:
        payload = r.get("payload") or {}
        items.append({
            "id": r["id"],
            "title": payload.get("title", ""),
            "body": payload.get("body", ""),
            "created_at": r["created_at"],
        })
    return {"items": items, "count": len(items)}


class NotificationSend(BaseModel):
    title: str
    body: str
    channels: list[str] = ["web"]


@router.post("/send")
async def send_notification(body: NotificationSend, user_id: str = Depends(jwt_auth)):
    # Record in changefeed so WS clients receive it
    insert(
        "changefeed",
        {
            "event_id": generate_ulid(),
            "user_id": user_id,
            "device_id": "server",
            "event_type": "notification",
            "payload": {
                "title": body.title,
                "body": body.body,
                "channels": body.channels,
            },
        },
    )

    # Push to active WebSocket connections
    try:
        from stratum.api.ws import broadcast_to_user

        import asyncio

        asyncio.create_task(
            broadcast_to_user(
                user_id,
                {"type": "notification", "title": body.title, "body": body.body},
            )
        )
    except Exception:
        pass

    return {"status": "sent", "channels": body.channels}
