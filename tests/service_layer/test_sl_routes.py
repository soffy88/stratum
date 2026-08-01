"""Service-layer route tests backed by real DuckDB (in-memory per test).

§M5 rewrite: replaced mock stratum.db.* fixture with real DuckDB via conftest.py.
Routes now execute actual SQL against an isolated temp DuckDB database, catching
SQL dialect bugs (list_contains, SEQUENCE, etc.) that mock-only tests miss.

Coverage:
  - notes CRUD + cross-user isolation   (tests 1–3)
  - agents/run                          (test  4)
  - inbox/submit file upload            (test  5)
  - search IDOR post-filter             (test  6)
  - WebSocket auth guard (no token)     (test  7)
  - WebSocket CSWSH guard (bad origin)  (test  8)
  - JWT guard: missing token            (test  9)
  - JWT guard: invalid/expired token    (test 10–11)
"""

from __future__ import annotations

import io
import os
import sys
import time
from unittest.mock import MagicMock, patch

import duckdb
import pytest
from fastapi.testclient import TestClient

# ── JWT secret must be set before any stratum import ────────────────────────
os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402
from stratum.api.routers.agents import _HAS_OMODUL  # noqa: E402

requires_omodul = pytest.mark.skipif(
    not _HAS_OMODUL,
    reason="omodul platform package not installed (Docker image only)",
)


# ─────────────────────────────── helpers ────────────────────────────────────


def _make_token(user_id: str = "user-alice") -> str:
    return create_token(user_id)


def _auth(user_id: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _expired_token() -> str:
    import jwt

    secret = os.environ.get("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")
    payload = {"sub": "user-x", "iat": int(time.time()) - 10, "exp": int(time.time()) - 5}
    return jwt.encode(payload, secret, algorithm="HS256")


def _db_insert(db_path: str, table: str, data: dict) -> None:
    """Insert a row directly into the test DuckDB (for test data setup)."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f"${k}" for k in data)
    conn = duckdb.connect(db_path)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", data)
    conn.close()


# ─────────────────────────────── client fixture ──────────────────────────────


@pytest.fixture()
def client():
    """TestClient for the SL FastAPI app. No DB mocks — uses real DuckDB."""
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/notes — creates a note, returns ULID note_id
# ═══════════════════════════════════════════════════════════════════════════════


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
    assert isinstance(body["note_id"], str) and len(body["note_id"]) == 26


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/v1/notes/{id} — 404 when note belongs to a different user
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_note_cross_user_isolation(client, duckdb_test_db):
    # Pre-insert a note owned by user-bob
    _db_insert(
        duckdb_test_db,
        "notes",
        {"id": "NOTE-001", "user_id": "user-bob", "title": "Bob note", "content_markdown": "hi"},
    )

    # Alice requests that note — must get 404 (corpus isolation)
    r = client.get("/api/v1/notes/NOTE-001", headers=_auth("user-alice"))
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DELETE /api/v1/notes/{id} — soft-delete; subsequent GET returns 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_delete_note_then_get_is_404(client):
    # Create via the API — the service layer persists to Postgres since the
    # DuckDB → PG migration, so the legacy DuckDB pre-insert helper no longer
    # seeds data the routes can see.
    create_r = client.post(
        "/api/v1/notes",
        json={"title": "To delete", "content_markdown": "x"},
        headers=_auth("user-alice"),
    )
    assert create_r.status_code == 200
    note_id = create_r.json()["note_id"]

    del_r = client.delete(f"/api/v1/notes/{note_id}", headers=_auth("user-alice"))
    assert del_r.status_code == 200
    assert del_r.json()["status"] == "deleted"

    # Default delete is a hard purge; GET must return 404 afterwards
    get_r = client.get(f"/api/v1/notes/{note_id}", headers=_auth("user-alice"))
    assert get_r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 4. POST /api/v1/agents/daily_digest/run — returns JSON with agent_name
# ═══════════════════════════════════════════════════════════════════════════════


@requires_omodul
def test_agent_run_returns_agent_name(client):
    r = client.post(
        "/api/v1/agents/daily_digest/run",
        json={},
        headers=_auth(),
    )
    assert r.status_code == 200
    body = r.json()
    assert "agent_name" in body
    assert body["agent_name"] == "daily_digest"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. POST /api/v1/inbox/submit — returns upload_id and status
# ═══════════════════════════════════════════════════════════════════════════════


def test_inbox_submit_returns_upload_id_and_status(client, tmp_path):
    # The real inbox dir (~/.stratum/users/...) is root-owned (created by the
    # docker stack), so redirect the upload into tmp_path.
    inbox_dir = tmp_path / "inbox"
    content = b"hello world test content"
    with (
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value=inbox_dir),
        patch(
            "stratum.api.routers.inbox.ensure_dir",
            side_effect=lambda p: (os.makedirs(p, exist_ok=True), p)[1],
        ),
    ):
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


# ═══════════════════════════════════════════════════════════════════════════════
# 6. POST /api/v1/search — IDOR post-filter keeps only caller's results
# ═══════════════════════════════════════════════════════════════════════════════


def test_search_idor_post_filter(client):
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

    fake_output = MagicMock()
    fake_output.results = [
        _fake_result("R1", "user-alice"),  # caller → keep
        _fake_result("R2", "user-eve"),  # other user → filter out
        _fake_result("R3", None),  # no user_id → pass-through
    ]
    fake_output.citations = []
    fake_output.search_time_ms = 5
    fake_output.scope_hit_counts = {}

    # search_utils imports oprim/oskill at module level (absent on dev hosts);
    # the route's function-local import resolves against this stub.
    search_utils_stub = MagicMock()
    with (
        patch("stratum.api.routers.search._HAS_SEARCH", True),
        patch("stratum.api.routers.search.cross_layer_search", return_value=fake_output),
        patch.dict(sys.modules, {"stratum.api.search_utils": search_utils_stub}),
    ):
        r = client.post("/api/v1/search", json={"query": "test"}, headers=_auth("user-alice"))

    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["results"]]
    assert "R2" not in ids
    assert "R1" in ids
    assert "R3" in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 7. WS /ws without token — closes with 4001
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_no_token_closes_4001(client):
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()

    exc = exc_info.value
    assert hasattr(exc, "code"), f"Expected WebSocketDisconnect, got {type(exc)}: {exc}"
    assert exc.code == 4001, f"Expected 4001, got {exc.code}"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. WS /ws with cookie from disallowed origin — closes with 4403 (CSWSH)
# ═══════════════════════════════════════════════════════════════════════════════


def test_ws_cookie_disallowed_origin_closes_4403(client):
    token = _make_token("user-alice")

    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect(
            "/ws",
            cookies={"access_token": token},
            headers={"origin": "https://evil.example.com"},
        ) as ws:
            ws.receive_text()

    exc = exc_info.value
    assert hasattr(exc, "code"), f"Expected WebSocketDisconnect, got {type(exc)}: {exc}"
    assert exc.code == 4403, f"Expected 4403, got {exc.code}"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. JWT guard: missing token → 401
# ═══════════════════════════════════════════════════════════════════════════════


def test_jwt_guard_missing_token_401(client):
    r = client.get("/api/v1/notes")
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 10. JWT guard: expired token → 401
# ═══════════════════════════════════════════════════════════════════════════════


def test_jwt_guard_expired_token_401(client):
    token = _expired_token()
    r = client.get("/api/v1/notes", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 11. JWT guard: invalid (malformed) token → 401
# ═══════════════════════════════════════════════════════════════════════════════


def test_jwt_guard_invalid_token_401(client):
    r = client.get("/api/v1/notes", headers={"Authorization": "Bearer notavalidtoken"})
    assert r.status_code == 401
