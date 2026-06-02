"""Shared changefeed event emitter (Phase 15 P1-B4 / P1-C2).

emit_event() writes to DB and broadcasts to connected WebSocket clients.
Best-effort — never raises; failures are silently swallowed.

Lazy-imports broadcast_to_user from stratum.api.ws to avoid circular imports
at module initialisation time.
"""

from stratum.common import generate_ulid, now_utc
from stratum.db import insert


async def emit_event(user_id: str, event_type: str, payload: dict) -> None:
    try:
        event_id = generate_ulid()
        insert(
            "changefeed",
            {
                "event_id": event_id,
                "user_id": user_id,
                "device_id": "server",
                "event_type": event_type,
                "payload": payload,
            },
            returning="seq",
        )
        # P1-C2: broadcast to connected WebSocket clients (Wave 3)
        from stratum.api.ws import broadcast_to_user

        await broadcast_to_user(
            user_id,
            {
                "event_id": event_id,
                "event_type": event_type,
                "payload": payload,
                "timestamp": now_utc(),
            },
        )
    except Exception:
        pass
