"""Phase 15 P1-B4: Changefeed event emission tests.

For each mutation endpoint, verify the corresponding event was written
to the changefeed table. The service layer persists to Postgres since the
DuckDB → PG migration, so events are read back via stratum.db.

Events tested (14 total = 3 existing note + 11 new):
  note_create / note_update / note_delete          (existing — smoke check)
  substrate_pin / substrate_unpin                  (substrate.py)
  concept_create / concept_update / concept_delete  (concepts.py)
  agent_run_completed | agent_run_failed            (agents.py — one fires)
  highlight_create / highlight_delete              (highlights.py)
  view_create / view_default_changed               (views.py)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402
from stratum.api.routers.agents import _HAS_OMODUL  # noqa: E402
from stratum.db import execute as _pg_execute  # noqa: E402
from stratum.db import insert as _pg_insert  # noqa: E402
from stratum.db import query as _pg_query  # noqa: E402
from stratum.utils.user_id_hash import hash_user_id  # noqa: E402

requires_omodul = pytest.mark.skipif(
    not _HAS_OMODUL,
    reason="omodul platform package not installed (Docker image only)",
)


def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# Routers are split on user identity: notes/concepts emit with the raw JWT
# subject, while documents/highlights/views emit with hash_user_id(). Match
# both forms when counting events and cleaning up.
_TEST_USER_IDS = tuple(
    uid for base in ("user-alice", "user-bob") for uid in (base, hash_user_id(base))
)


@pytest.fixture(autouse=True)
def _clean_event_state():
    """Tests assert per-user event counts against the shared dev Postgres.

    Wipe the previous round's events and API-created rows for the fixed test
    users so each test starts from a known-empty state (fixed substrate ids
    would otherwise collide on re-runs).
    """
    _pg_execute("DELETE FROM changefeed WHERE user_id IN %(uids)s", {"uids": _TEST_USER_IDS})
    _pg_execute("DELETE FROM notes_sl WHERE user_id IN %(uids)s", {"uids": _TEST_USER_IDS})
    _pg_execute("DELETE FROM concepts WHERE user_id IN %(uids)s", {"uids": _TEST_USER_IDS})
    _pg_execute("DELETE FROM highlights WHERE user_id IN %(uids)s", {"uids": _TEST_USER_IDS})
    _pg_execute("DELETE FROM user_saved_views WHERE user_id IN %(uids)s", {"uids": _TEST_USER_IDS})
    _pg_execute("DELETE FROM substrates WHERE id IN ('SUB-PIN-01', 'SUB-UNP-01')")
    yield


def _events_of_type(event_type: str, user_id: str = "user-alice") -> int:
    rows = _pg_query(
        "SELECT COUNT(*) AS n FROM changefeed "
        "WHERE user_id IN %(uids)s AND event_type = %(t)s",
        {"uids": (user_id, hash_user_id(user_id)), "t": event_type},
        limit=1,
    )
    return rows[0]["n"] if rows else 0


def _db_insert(table: str, data: dict) -> None:
    _pg_insert(table, data)


# ═══════════════════════════════════════════════════════════════════════════════
# Existing note events — smoke check that shared emit_event still works
# ═══════════════════════════════════════════════════════════════════════════════


def test_note_create_emits_event(client):
    client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    assert _events_of_type("note_create") >= 1


def test_note_update_emits_event(client):
    r = client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    nid = r.json()["note_id"]
    client.put(f"/api/v1/notes/{nid}", json={"title": "T2"}, headers=_auth())
    assert _events_of_type("note_update") >= 1


def test_note_delete_emits_event(client):
    r = client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    nid = r.json()["note_id"]
    client.delete(f"/api/v1/notes/{nid}", headers=_auth())
    assert _events_of_type("note_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# substrate_pin / substrate_unpin
# ═══════════════════════════════════════════════════════════════════════════════


def test_substrate_pin_emits_event(client):
    # The documents router matches substrates on the hashed user id.
    _db_insert(
        "substrates", {"id": "SUB-PIN-01", "user_id": hash_user_id("user-alice")}
    )
    r = client.post("/api/v1/documents/SUB-PIN-01/pin", headers=_auth())
    assert r.status_code == 200
    assert _events_of_type("substrate_pin") >= 1


def test_substrate_unpin_emits_event(client):
    _db_insert(
        "substrates", {"id": "SUB-UNP-01", "user_id": hash_user_id("user-alice")}
    )
    client.post("/api/v1/documents/SUB-UNP-01/pin", headers=_auth())
    r = client.post("/api/v1/documents/SUB-UNP-01/unpin", headers=_auth())
    assert r.status_code == 200
    assert _events_of_type("substrate_unpin") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# concept_create / concept_update / concept_delete
# ═══════════════════════════════════════════════════════════════════════════════


def test_concept_create_emits_event(client):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    assert r.status_code == 200
    assert _events_of_type("concept_create") >= 1


def test_concept_update_emits_event(client):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    cid = r.json()["concept_id"]
    client.put(f"/api/v1/concepts/{cid}", json={"name": "Testcept2"}, headers=_auth())
    assert _events_of_type("concept_update") >= 1


def test_concept_delete_emits_event(client):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    cid = r.json()["concept_id"]
    client.delete(f"/api/v1/concepts/{cid}", headers=_auth())
    assert _events_of_type("concept_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# agent_run_completed | agent_run_failed (one of them fires per run)
# ═══════════════════════════════════════════════════════════════════════════════


@requires_omodul
def test_agent_run_emits_completed_or_failed_event(client):
    r = client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth())
    assert r.status_code == 200
    count = _events_of_type("agent_run_completed") + _events_of_type("agent_run_failed")
    assert count >= 1, "Neither agent_run_completed nor agent_run_failed was emitted"


# ═══════════════════════════════════════════════════════════════════════════════
# highlight_create / highlight_delete
# ═══════════════════════════════════════════════════════════════════════════════


def test_highlight_create_emits_event(client):
    r = client.post(
        "/api/v1/highlights",
        json={"substrate_id": "PC-001", "text": "excerpt"},
        headers=_auth(),
    )
    assert r.status_code == 201
    assert _events_of_type("highlight_create") >= 1


def test_highlight_delete_emits_event(client):
    r = client.post(
        "/api/v1/highlights",
        json={"substrate_id": "PC-001", "text": "excerpt"},
        headers=_auth(),
    )
    hid = r.json()["id"]
    client.delete(f"/api/v1/highlights/{hid}", headers=_auth())
    assert _events_of_type("highlight_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# view_create / view_default_changed
# ═══════════════════════════════════════════════════════════════════════════════


def test_view_create_emits_event(client):
    r = client.post("/api/v1/views", json={"name": "My View"}, headers=_auth())
    assert r.status_code == 201
    assert _events_of_type("view_create") >= 1


# test_view_default_changed_emits_event was dropped: the views router has no
# set-default route anymore — view_default_changed survives only as a name in
# sync.py's scope registry, nothing emits it.
