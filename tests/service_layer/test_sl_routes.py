"""Unit tests for Stratum service-layer routes (src/stratum/api/).

All PostgreSQL calls are mocked — no real DB required.
JWT_SECRET is set via conftest.py (tests/conftest.py) before import.

Coverage:
  - notes CRUD + cross-user isolation   (tests 1–3)
  - agents/run                          (test  4)
  - inbox/submit file upload            (test  5)
  - search IDOR post-filter             (test  6)
  - WebSocket auth guard (no token)     (test  7)
  - WebSocket CSWSH guard (bad origin)  (test  8)
  - JWT guard: missing token            (test  9)
  - JWT guard: invalid/expired token    (test 10)
"""

from __future__ import annotations

import io
import os
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Ensure JWT_SECRET is set before anything imports stratum.common ─────────
# conftest.py already calls setdefault; the env-var override here is a belt-
# and-suspenders measure so the file is also usable in isolation.
os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

# Import create_token after secret is set
from stratum.common import create_token  # noqa: E402


# ─────────────────────────────── fixture helpers ─────────────────────────────


def _make_token(user_id: str = "user-alice") -> str:
    return create_token(user_id)


def _auth(user_id: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _expired_token() -> str:
    """Create a token that is already expired (iat = exp = 1 second ago)."""
    import jwt

    secret = os.environ.get("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")
    payload = {"sub": "user-x", "iat": int(time.time()) - 10, "exp": int(time.time()) - 5}
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture()
def client():
    """TestClient for the service-layer FastAPI app with mocked stratum.db.

    Notes router (and others) do ``from stratum.db import read, insert, ...``
    at import time, binding names in their own namespace.  Patching only
    ``stratum.db.read`` after the module is loaded has no effect on those
    already-bound names.  We therefore patch both the canonical module AND
    every router namespace that bound the symbols, so return_value changes
    made inside tests propagate correctly.
    """
    # Ensure the app (and all its routers) are imported before we patch,
    # so the router-level names exist.
    from stratum.api.main import app  # noqa: F401 — side-effect: registers routers

    _read_mock = MagicMock(return_value=None)
    _insert_mock = MagicMock(return_value="fake-id")
    _update_mock = MagicMock(return_value=None)
    _soft_delete_mock = MagicMock(return_value=None)
    _query_mock = MagicMock(return_value=[])

    # Namespaces that bind db symbols directly via `from stratum.db import ...`
    _router_targets = [
        "stratum.api.routers.notes",
        "stratum.api.routers.agents",
        "stratum.api.routers.substrate",
        "stratum.api.routers.search",
        "stratum.api.routers.inbox",
        "stratum.api.routers.content",
        "stratum.api.routers.concepts",
        "stratum.api.routers.views",
        "stratum.api.routers.account",
        "stratum.api.routers.billing",
        "stratum.api.routers.bookmarks",
        "stratum.api.routers.highlights",
        "stratum.api.routers.notifications",
        "stratum.api.routers.interactions",
        "stratum.api.routers.recommendations",
        "stratum.api.routers.sync",
        "stratum.api.routers.translate",
        "stratum.api.mcp",
    ]

    import sys

    patches = []
    # Patch the canonical module
    for sym, mock in (
        ("stratum.db.read", _read_mock),
        ("stratum.db.insert", _insert_mock),
        ("stratum.db.update", _update_mock),
        ("stratum.db.soft_delete", _soft_delete_mock),
        ("stratum.db.query", _query_mock),
    ):
        p = patch(sym, mock)
        p.start()
        patches.append(p)

    # Patch each router namespace that already bound the symbol
    for mod_name in _router_targets:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for attr, mock in (
            ("read", _read_mock),
            ("insert", _insert_mock),
            ("update", _update_mock),
            ("soft_delete", _soft_delete_mock),
            ("query", _query_mock),
        ):
            if hasattr(mod, attr):
                p = patch.object(mod, attr, mock)
                p.start()
                patches.append(p)

    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            c.mock_insert = _insert_mock
            c.mock_read = _read_mock
            c.mock_update = _update_mock
            c.mock_soft_delete = _soft_delete_mock
            c.mock_query = _query_mock
            yield c
    finally:
        for p in reversed(patches):
            p.stop()


# ═════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/notes — creates a note, returns note_id
# ═════════════════════════════════════════════════════════════════════════════


def test_create_note_returns_note_id(client):
    r = client.post(
        "/api/v1/notes",
        json={"title": "Test Note", "content_markdown": "hello"},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "note_id" in body
    assert body["status"] == "created"
    # note_id should be a non-empty string (ULID)
    assert isinstance(body["note_id"], str) and len(body["note_id"]) == 26


# ═════════════════════════════════════════════════════════════════════════════
# 2. GET /api/v1/notes/{id} — returns 404 for another user's note (isolation)
# ═════════════════════════════════════════════════════════════════════════════


def test_get_note_cross_user_isolation(client):
    # DB returns a note that belongs to user-bob
    client.mock_read.return_value = {
        "id": "NOTE-001",
        "user_id": "user-bob",
        "title": "Bob's note",
        "deleted_at": None,
    }

    # Alice requests that note — must get 404
    r = client.get("/api/v1/notes/NOTE-001", headers=_auth("user-alice"))
    assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 3. DELETE /api/v1/notes/{id} — soft-delete; subsequent GET returns 404
# ═════════════════════════════════════════════════════════════════════════════


def test_delete_note_then_get_is_404(client):
    # First: make the note exist and belong to alice
    client.mock_read.return_value = {
        "id": "NOTE-002",
        "user_id": "user-alice",
        "title": "Alice note",
        "deleted_at": None,
    }

    del_r = client.delete("/api/v1/notes/NOTE-002", headers=_auth("user-alice"))
    assert del_r.status_code == 200
    assert del_r.json()["status"] == "deleted"

    # soft_delete was called
    client.mock_soft_delete.assert_called_once()

    # Simulate the note having a deleted_at timestamp now
    client.mock_read.return_value = {
        "id": "NOTE-002",
        "user_id": "user-alice",
        "title": "Alice note",
        "deleted_at": "2026-01-01T00:00:00",
    }

    get_r = client.get("/api/v1/notes/NOTE-002", headers=_auth("user-alice"))
    assert get_r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 4. POST /api/v1/agents/daily_digest/run — returns JSON with agent_name
# ═════════════════════════════════════════════════════════════════════════════


def test_agent_run_returns_agent_name(client):
    r = client.post(
        "/api/v1/agents/daily_digest/run",
        json={},
        headers=_auth(),
    )
    # Accepts 200 whether omodul is present or not
    assert r.status_code == 200
    body = r.json()
    assert "agent_name" in body
    assert body["agent_name"] == "daily_digest"


# ═════════════════════════════════════════════════════════════════════════════
# 5. POST /api/v1/inbox/submit — returns upload_id and status
# ═════════════════════════════════════════════════════════════════════════════


def test_inbox_submit_returns_upload_id_and_status(client, tmp_path):
    content = b"hello world test content"
    r = client.post(
        "/api/v1/inbox/submit",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "upload_id" in body
    assert "status" in body
    assert isinstance(body["upload_id"], str)


# ═════════════════════════════════════════════════════════════════════════════
# 6. POST /api/v1/search — IDOR post-filter: results only contain caller's uid
# ═════════════════════════════════════════════════════════════════════════════


def test_search_idor_post_filter(client):
    """Simulate oskill returning mixed-user results; verify only own rows returned."""

    # Build fake result objects with user_id attribute
    def _fake_result(rid, uid):
        r = MagicMock()
        r.id = rid
        r.user_id = uid
        r.type = "substrate"
        r.title = f"doc-{rid}"
        r.score = 0.9
        r.highlight = ""
        r.citation = None
        return r

    fake_search_output = MagicMock()
    fake_search_output.results = [
        _fake_result("R1", "user-alice"),  # belongs to caller
        _fake_result("R2", "user-eve"),  # another user → must be filtered
        _fake_result("R3", None),  # no user_id → pass-through
    ]
    fake_search_output.citations = []
    fake_search_output.search_time_ms = 5
    fake_search_output.scope_hit_counts = {}

    with (
        patch("stratum.api.routers.search._HAS_SEARCH", True),
        patch("stratum.api.routers.search.cross_layer_search", return_value=fake_search_output),
    ):
        r = client.post(
            "/api/v1/search",
            json={"query": "test query"},
            headers=_auth("user-alice"),
        )

    assert r.status_code == 200
    body = r.json()
    returned_ids = [item["id"] for item in body["results"]]
    # R2 (user-eve) must be absent
    assert "R2" not in returned_ids
    # R1 (alice) and R3 (no uid) must be present
    assert "R1" in returned_ids
    assert "R3" in returned_ids


# ═════════════════════════════════════════════════════════════════════════════
# 7. WS /ws without token — closes with 4001
# ═════════════════════════════════════════════════════════════════════════════


def test_ws_no_token_closes_4001(client):
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()

    # TestClient raises WebSocketDisconnect on close; code 4001
    exc = exc_info.value
    # starlette WebSocketDisconnect carries the code
    assert hasattr(exc, "code"), f"Expected WebSocketDisconnect, got {type(exc)}: {exc}"
    assert exc.code == 4001, f"Expected close code 4001, got {exc.code}"


# ═════════════════════════════════════════════════════════════════════════════
# 8. WS /ws with cookie from disallowed origin — closes with 4403 (CSWSH)
# ═════════════════════════════════════════════════════════════════════════════


def test_ws_cookie_disallowed_origin_closes_4403(client):
    valid_token = _make_token("user-alice")

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect(
            "/ws",
            cookies={"access_token": valid_token},
            headers={"origin": "https://evil.example.com"},
        ) as ws:
            ws.receive_text()

    exc = exc_info.value
    assert hasattr(exc, "code"), f"Expected WebSocketDisconnect, got {type(exc)}: {exc}"
    assert exc.code == 4403, f"Expected close code 4403, got {exc.code}"


# ═════════════════════════════════════════════════════════════════════════════
# 9. JWT guard: missing token → 401
# ═════════════════════════════════════════════════════════════════════════════


def test_jwt_guard_missing_token_401(client):
    r = client.get("/api/v1/notes")
    assert r.status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# 10. JWT guard: expired/invalid token → 401
# ═════════════════════════════════════════════════════════════════════════════


def test_jwt_guard_expired_token_401(client):
    token = _expired_token()
    r = client.get("/api/v1/notes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_jwt_guard_invalid_token_401(client):
    r = client.get("/api/v1/notes", headers={"Authorization": "Bearer notavalidtoken"})
    assert r.status_code == 401
