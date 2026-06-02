"""Phase 15 P1-B4: Changefeed event emission tests.

For each mutation endpoint, verify the corresponding event was written
to the changefeed table. Direct DuckDB query via duckdb_test_db fixture.

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

import duckdb
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


def _latest_event(db_path: str, user_id: str = "user-alice") -> str | None:
    conn = duckdb.connect(db_path)
    rows = conn.execute(
        "SELECT event_type FROM changefeed WHERE user_id = ? ORDER BY seq DESC LIMIT 1",
        [user_id],
    ).fetchall()
    conn.close()
    return rows[0][0] if rows else None


def _events_of_type(db_path: str, event_type: str, user_id: str = "user-alice") -> int:
    conn = duckdb.connect(db_path)
    row = conn.execute(
        "SELECT COUNT(*) FROM changefeed WHERE user_id = ? AND event_type = ?",
        [user_id, event_type],
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def _db_insert(db_path: str, table: str, data: dict) -> None:
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f"${k}" for k in data)
    conn = duckdb.connect(db_path)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", data)
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Existing note events — smoke check that shared emit_event still works
# ═══════════════════════════════════════════════════════════════════════════════


def test_note_create_emits_event(client, duckdb_test_db):
    client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    assert _events_of_type(duckdb_test_db, "note_create") >= 1


def test_note_update_emits_event(client, duckdb_test_db):
    r = client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    nid = r.json()["note_id"]
    client.put(f"/api/v1/notes/{nid}", json={"title": "T2"}, headers=_auth())
    assert _events_of_type(duckdb_test_db, "note_update") >= 1


def test_note_delete_emits_event(client, duckdb_test_db):
    r = client.post(
        "/api/v1/notes",
        json={"title": "T", "content_markdown": "x"},
        headers=_auth(),
    )
    nid = r.json()["note_id"]
    client.delete(f"/api/v1/notes/{nid}", headers=_auth())
    assert _events_of_type(duckdb_test_db, "note_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# substrate_pin / substrate_unpin
# ═══════════════════════════════════════════════════════════════════════════════


def test_substrate_pin_emits_event(client, duckdb_test_db):
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-PIN-01", "user_id": "user-alice"})
    r = client.post("/api/v1/substrate/SUB-PIN-01/pin", headers=_auth())
    assert r.status_code == 200
    assert _events_of_type(duckdb_test_db, "substrate_pin") >= 1


def test_substrate_unpin_emits_event(client, duckdb_test_db):
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-UNP-01", "user_id": "user-alice"})
    client.post("/api/v1/substrate/SUB-UNP-01/pin", headers=_auth())
    r = client.post("/api/v1/substrate/SUB-UNP-01/unpin", headers=_auth())
    assert r.status_code == 200
    assert _events_of_type(duckdb_test_db, "substrate_unpin") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# concept_create / concept_update / concept_delete
# ═══════════════════════════════════════════════════════════════════════════════


def test_concept_create_emits_event(client, duckdb_test_db):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    assert r.status_code == 200
    assert _events_of_type(duckdb_test_db, "concept_create") >= 1


def test_concept_update_emits_event(client, duckdb_test_db):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    cid = r.json()["concept_id"]
    client.put(f"/api/v1/concepts/{cid}", json={"name": "Testcept2"}, headers=_auth())
    assert _events_of_type(duckdb_test_db, "concept_update") >= 1


def test_concept_delete_emits_event(client, duckdb_test_db):
    r = client.post("/api/v1/concepts", json={"name": "Testcept"}, headers=_auth())
    cid = r.json()["concept_id"]
    client.delete(f"/api/v1/concepts/{cid}", headers=_auth())
    assert _events_of_type(duckdb_test_db, "concept_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# agent_run_completed | agent_run_failed (one of them fires per run)
# ═══════════════════════════════════════════════════════════════════════════════


def test_agent_run_emits_completed_or_failed_event(client, duckdb_test_db):
    r = client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth())
    assert r.status_code == 200
    conn = duckdb.connect(duckdb_test_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM changefeed WHERE user_id = 'user-alice' "
        "AND event_type IN ('agent_run_completed', 'agent_run_failed')",
    ).fetchone()[0]
    conn.close()
    assert count >= 1, "Neither agent_run_completed nor agent_run_failed was emitted"


# ═══════════════════════════════════════════════════════════════════════════════
# highlight_create / highlight_delete
# ═══════════════════════════════════════════════════════════════════════════════


def test_highlight_create_emits_event(client, duckdb_test_db):
    r = client.post(
        "/api/v1/highlights",
        json={"content_id": "PC-001", "anchor": {"char_start": 0, "char_end": 10}},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert _events_of_type(duckdb_test_db, "highlight_create") >= 1


def test_highlight_delete_emits_event(client, duckdb_test_db):
    r = client.post(
        "/api/v1/highlights",
        json={"content_id": "PC-001", "anchor": {"char_start": 0, "char_end": 10}},
        headers=_auth(),
    )
    hid = r.json()["highlight_id"]
    client.delete(f"/api/v1/highlights/{hid}", headers=_auth())
    assert _events_of_type(duckdb_test_db, "highlight_delete") >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# view_create / view_default_changed
# ═══════════════════════════════════════════════════════════════════════════════


def test_view_create_emits_event(client, duckdb_test_db):
    r = client.post("/api/v1/views", json={"name": "My View"}, headers=_auth())
    assert r.status_code == 200
    assert _events_of_type(duckdb_test_db, "view_create") >= 1


def test_view_default_changed_emits_event(client, duckdb_test_db):
    r = client.post("/api/v1/views", json={"name": "Default View"}, headers=_auth())
    vid = r.json()["view_id"]
    r2 = client.post(f"/api/v1/views/{vid}/set-default", headers=_auth())
    assert r2.status_code == 200
    assert _events_of_type(duckdb_test_db, "view_default_changed") >= 1
