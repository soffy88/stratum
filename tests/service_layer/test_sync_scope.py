"""Phase 15 P1-C1: Sync changefeed scope filter tests.

Tests verify that ?scope= correctly filters returned event_types.
Events are seeded by calling the mutation endpoints; the changefeed table
is then queried via GET /api/v1/sync/changefeed?scope=...

Coverage (≥5 tests):
  1. scope=notes       → only note_* events
  2. scope=substrates  → only substrate_* events
  3. scope=concepts    → only concept_* events
  4. scope=notes,substrates → events from both scopes, not others
  5. scope=notes,substrates,highlights,concepts (default) → all 4 scopes
  6. unknown scope → empty events list
  7. since cursor filters correctly
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


def _db_insert(db_path: str, table: str, data: dict) -> None:
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f"${k}" for k in data)
    conn = duckdb.connect(db_path)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", data)
    conn.close()


def _pull(client, scope: str, since: int = 0) -> list[dict]:
    r = client.get(
        f"/api/v1/sync/changefeed?scope={scope}&since={since}",
        headers=_auth(),
    )
    assert r.status_code == 200, r.text
    return r.json()["events"]


# ═══════════════════════════════════════════════════════════════════════════════
# Seed helpers — trigger mutations to produce events
# ═══════════════════════════════════════════════════════════════════════════════


def _seed_note(client) -> None:
    client.post("/api/v1/notes", json={"title": "T", "content_markdown": "x"}, headers=_auth())


def _seed_substrate_pin(client, duckdb_test_db) -> None:
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-SCOPE-01", "user_id": "user-alice"})
    client.post("/api/v1/substrate/SUB-SCOPE-01/pin", headers=_auth())


def _seed_concept(client) -> None:
    client.post("/api/v1/concepts", json={"name": "ScopeCept"}, headers=_auth())


def _seed_highlight(client) -> None:
    client.post(
        "/api/v1/highlights",
        json={"content_id": "PC-SCOPE-01", "anchor": {"char_start": 0, "char_end": 5}},
        headers=_auth(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. scope=notes → only note_* events
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_notes_only(client, duckdb_test_db):
    _seed_note(client)
    _seed_substrate_pin(client, duckdb_test_db)

    events = _pull(client, "notes")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("note_") for t in types), f"No note events: {types}"
    assert not any(t.startswith("substrate_") for t in types), (
        f"Substrate leaked into notes scope: {types}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. scope=substrates → only substrate_* events
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_substrates_only(client, duckdb_test_db):
    _seed_note(client)
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-SCOPE-02", "user_id": "user-alice"})
    client.post("/api/v1/substrate/SUB-SCOPE-02/pin", headers=_auth())

    events = _pull(client, "substrates")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("substrate_") for t in types), f"No substrate events: {types}"
    assert not any(t.startswith("note_") for t in types), (
        f"Notes leaked into substrate scope: {types}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. scope=concepts → only concept_* events
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_concepts_only(client, duckdb_test_db):
    _seed_note(client)
    _seed_concept(client)

    events = _pull(client, "concepts")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("concept_") for t in types), f"No concept events: {types}"
    assert not any(t.startswith("note_") for t in types), (
        f"Notes leaked into concepts scope: {types}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. scope=notes,substrates → both scopes, not concepts
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_notes_and_substrates(client, duckdb_test_db):
    _seed_note(client)
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-SCOPE-03", "user_id": "user-alice"})
    client.post("/api/v1/substrate/SUB-SCOPE-03/pin", headers=_auth())
    _seed_concept(client)

    events = _pull(client, "notes,substrates")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("note_") for t in types), f"No note events: {types}"
    assert any(t.startswith("substrate_") for t in types), f"No substrate events: {types}"
    assert not any(t.startswith("concept_") for t in types), f"Concepts leaked: {types}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. scope=notes,substrates,highlights,concepts (default) → all 4 scopes
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_default_four_scopes(client, duckdb_test_db):
    _seed_note(client)
    _db_insert(duckdb_test_db, "substrates", {"id": "SUB-SCOPE-04", "user_id": "user-alice"})
    client.post("/api/v1/substrate/SUB-SCOPE-04/pin", headers=_auth())
    _seed_concept(client)
    _seed_highlight(client)

    events = _pull(client, "notes,substrates,highlights,concepts")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("note_") for t in types)
    assert any(t.startswith("substrate_") for t in types)
    assert any(t.startswith("concept_") for t in types)
    assert any(t.startswith("highlight_") for t in types)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Unknown scope → empty events list
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_unknown_returns_empty(client):
    _seed_note(client)
    events = _pull(client, "nonexistent_scope")
    assert events == [], f"Expected [], got {events}"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. since cursor filters to only newer events
# ═══════════════════════════════════════════════════════════════════════════════


def test_since_cursor_filters(client):
    # Create first note — get its seq
    _seed_note(client)
    first_events = _pull(client, "notes")
    assert first_events, "No note events after seed"
    first_seq = first_events[-1]["seq"]

    # Create second note after first_seq
    _seed_note(client)
    new_events = _pull(client, "notes", since=first_seq)
    assert new_events, f"No events after seq={first_seq}"
    assert all(e["seq"] > first_seq for e in new_events), "Got events before since cursor"
