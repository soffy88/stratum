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

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402
from stratum.db import hard_delete as _pg_hard_delete  # noqa: E402
from stratum.db import insert as _pg_insert  # noqa: E402
from stratum.utils.user_id_hash import hash_user_id  # noqa: E402


def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _seed_substrate_row(sid: str) -> None:
    """Seed a substrate in Postgres — the documents router resolves ownership
    there and matches on the hashed user id."""
    _pg_insert("substrates", {"id": sid, "user_id": hash_user_id("user-alice")})


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


def _seed_substrate_pin(client, sid: str) -> None:
    _seed_substrate_row(sid)
    r = client.post(f"/api/v1/documents/{sid}/pin", headers=_auth())
    assert r.status_code == 200, r.text


def _seed_concept(client) -> None:
    client.post("/api/v1/concepts", json={"name": "ScopeCept"}, headers=_auth())


def _seed_highlight(client, sid: str) -> str:
    r = client.post(
        "/api/v1/highlights",
        json={"substrate_id": sid, "text": "scope highlight"},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. scope=notes → only note_* events
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_notes_only(client):
    _seed_note(client)
    try:
        _seed_substrate_pin(client, "SUB-SCOPE-01")
    finally:
        _pg_hard_delete("substrates", "SUB-SCOPE-01")

    events = _pull(client, "notes")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("note_") for t in types), f"No note events: {types}"
    assert not any(t.startswith("substrate_") for t in types), (
        f"Substrate leaked into notes scope: {types}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. scope=substrates → only substrate_* events
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_substrates_only(client):
    _seed_note(client)
    try:
        _seed_substrate_pin(client, "SUB-SCOPE-02")
    finally:
        _pg_hard_delete("substrates", "SUB-SCOPE-02")

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


def test_scope_notes_and_substrates(client):
    _seed_note(client)
    try:
        _seed_substrate_pin(client, "SUB-SCOPE-03")
    finally:
        _pg_hard_delete("substrates", "SUB-SCOPE-03")
    _seed_concept(client)

    events = _pull(client, "notes,substrates")
    types = {e["event_type"] for e in events}
    assert any(t.startswith("note_") for t in types), f"No note events: {types}"
    assert any(t.startswith("substrate_") for t in types), f"No substrate events: {types}"
    assert not any(t.startswith("concept_") for t in types), f"Concepts leaked: {types}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. scope=notes,substrates,highlights,concepts (default) → all 4 scopes
# ═══════════════════════════════════════════════════════════════════════════════


def test_scope_default_four_scopes(client):
    _seed_note(client)
    highlight_id = None
    try:
        _seed_substrate_pin(client, "SUB-SCOPE-04")
        _seed_concept(client)
        highlight_id = _seed_highlight(client, "SUB-SCOPE-04")
    finally:
        # The legacy http_api suite asserts user-alice's highlights are empty,
        # so don't leave the seeded row behind in the shared dev database.
        if highlight_id:
            _pg_hard_delete("highlights", highlight_id)
        _pg_hard_delete("substrates", "SUB-SCOPE-04")

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
