"""Shared changefeed event emitter (Phase 15 P1-B4).

emit_event() is best-effort — it never raises. Routes call it after any
mutation without wrapping in try/except.

Wave 3 will extend this to also broadcast over WebSocket; change only here.
"""

from stratum.common import generate_ulid
from stratum.db import insert


def emit_event(user_id: str, event_type: str, payload: dict) -> None:
    try:
        insert(
            "changefeed",
            {
                "event_id": generate_ulid(),
                "user_id": user_id,
                "device_id": "server",
                "event_type": event_type,
                "payload": payload,
            },
            returning="seq",
        )
    except Exception:
        pass
