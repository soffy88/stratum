"""Phase 15 P1-C2: WebSocket real broadcast tests.

R-3: no mocks — uses real TestClient WebSocket + ticket auth.

Sync guarantee (no timeout needed):
  1. ws.send_text("ping") / ws.receive_text() — ensures the WS endpoint
     has reached its receive loop AND active_connections is populated.
  2. client.post(...) — HTTP request runs synchronously; emit_event awaited
     inside, broadcast_to_user completes before the response returns.
  3. ws.receive_json() — data already in the receive queue, returns immediately.

Coverage (5 tests, ≥3 are R-3 WS broadcast tests):
  1. note_create broadcasts event_type=note_create
  2. concept_create broadcasts event_type=concept_create
  3. broadcast isolation — Bob's mutation not delivered to Alice's WS
  4. invalid ticket → close 4001
  5. emit_event with no active WS → silently succeeds (no crash)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402


def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _get_ticket(client, uid: str = "user-alice") -> str:
    r = client.post("/api/v1/ws/ticket", headers=_auth(uid))
    assert r.status_code == 200, f"ticket failed: {r.text}"
    return r.json()["ticket"]


def _ws_ready(ws) -> None:
    """Ping/pong handshake — guarantees active_connections is populated."""
    ws.send_text("ping")
    pong = ws.receive_text()
    assert pong == "pong", f"Expected pong, got {pong!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. note_create mutation broadcasts event via WS
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_broadcast_note_create(client):
    ticket = _get_ticket(client)

    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        _ws_ready(ws)

        # HTTP post completes synchronously — broadcast_to_user runs during it
        r = client.post(
            "/api/v1/notes",
            json={"title": "WS test note", "content_markdown": "hello"},
            headers=_auth(),
        )
        assert r.status_code == 200

        # Data already in queue — returns immediately
        event = ws.receive_json()
        assert event["event_type"] == "note_create", f"Got: {event}"
        assert "event_id" in event
        assert "timestamp" in event
        assert event["payload"].get("title") == "WS test note"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. concept_create mutation broadcasts event via WS
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_broadcast_concept_create(client):
    ticket = _get_ticket(client)

    with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
        _ws_ready(ws)

        r = client.post(
            "/api/v1/concepts",
            json={"name": "BroadcastCept"},
            headers=_auth(),
        )
        assert r.status_code == 200

        event = ws.receive_json()
        assert event["event_type"] == "concept_create", f"Got: {event}"
        assert event["payload"].get("name") == "BroadcastCept"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Broadcast isolation: Bob's mutation NOT delivered to Alice's WS
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_broadcast_isolation(client):
    """Alice's WS receives only her own events, not Bob's."""
    ticket_alice = _get_ticket(client, "user-alice")

    with client.websocket_connect(f"/ws?ticket={ticket_alice}") as ws:
        _ws_ready(ws)

        # Bob creates a note — broadcast_to_user("user-bob", ...) finds no alice conn
        client.post(
            "/api/v1/notes",
            json={"title": "Bob's note", "content_markdown": "y"},
            headers=_auth("user-bob"),
        )

        # Alice creates a note — broadcast_to_user("user-alice", ...) sends to ws
        client.post(
            "/api/v1/notes",
            json={"title": "Alice's note", "content_markdown": "z"},
            headers=_auth("user-alice"),
        )

        # Receive: must be Alice's event (Bob's was never queued for Alice)
        event = ws.receive_json()
        assert event["event_type"] == "note_create", f"Got: {event}"
        assert event["payload"].get("title") == "Alice's note", (
            f"Expected Alice's note, got payload={event['payload']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Invalid ticket → WS closes with 4001
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_invalid_ticket_closes_4001(client):
    from starlette.testclient import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?ticket=invalid-ticket-xxxx"):
            pass
    assert exc_info.value.code == 4001


# ═══════════════════════════════════════════════════════════════════════════════
# 5. emit_event with no active WS connection → silently succeeds
# ═══════════════════════════════════════════════════════════════════════════════


def test_emit_event_no_ws_no_crash(client):
    """Mutations succeed (DB write) even when no WS client is connected."""
    r = client.post(
        "/api/v1/notes",
        json={"title": "No WS note", "content_markdown": "x"},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "created"
