"""Notification dispatch."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


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
