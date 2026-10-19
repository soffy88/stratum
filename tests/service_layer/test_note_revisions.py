"""AII Notes: append-only version history (P0-1).

Route-level tests against real PostgreSQL — the same store the API uses.
DB comes from STRATUM_PG_* env (CI: disposable pgvector service on 5435;
locally: any throwaway PG with base schema + migrations applied).
"""

from __future__ import annotations

import os

os.environ.setdefault("STRATUM_PG_HOST", "127.0.0.1")
os.environ.setdefault("STRATUM_PG_PORT", "5435")
os.environ.setdefault("STRATUM_PG_USER", "aii")
os.environ.setdefault("STRATUM_PG_DB", "aii_kg")
os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

import pytest
from fastapi.testclient import TestClient

from stratum.common import create_token


def _auth(user_id: str) -> dict:
    return {"Authorization": f"Bearer {create_token(user_id)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _create_note(client, user_id: str, title: str, body: str) -> str:
    r = client.post(
        "/api/v1/notes",
        json={"title": title, "content_markdown": body},
        headers=_auth(user_id),
    )
    assert r.status_code == 200
    return r.json()["note_id"]


def _revisions(client, note_id: str, user_id: str):
    r = client.get(f"/api/v1/notes/{note_id}/revisions", headers=_auth(user_id))
    assert r.status_code == 200
    return r.json()


# ── append-only chain: create → edit → edit → restore ────────────────────────


def test_history_append_only_full_chain(client):
    alice = "user-hist-alice"
    nid = _create_note(client, alice, "v0-title", "v0-body")

    # Edit 1: snapshot-before semantics → revision v1 must hold the ORIGINAL.
    r = client.put(
        f"/api/v1/notes/{nid}",
        json={"title": "v1-title", "content_markdown": "v1-body"},
        headers=_auth(alice),
    )
    assert r.status_code == 200
    assert r.json()["version"] == 1

    # Edit 2 (title omitted → unchanged).
    r = client.put(
        f"/api/v1/notes/{nid}",
        json={"content_markdown": "v2-body"},
        headers=_auth(alice),
    )
    assert r.json()["version"] == 2

    revs = _revisions(client, nid, alice)
    assert [x["version"] for x in revs] == [2, 1]
    assert [x["cause"] for x in revs] == ["edit", "edit"]
    assert {x["author_user_id"] for x in revs} == {alice}
    by_v = {x["version"]: x for x in revs}
    assert (by_v[1]["title"], by_v[1]["content_markdown"]) == ("v0-title", "v0-body")
    assert (by_v[2]["title"], by_v[2]["content_markdown"]) == ("v1-title", "v1-body")

    old_ids = {x["id"] for x in revs}

    # Restore v1: current content is snapshotted first (cause='restore'),
    # then the note row takes v1's content. Rows only ever get added.
    r = client.post(f"/api/v1/notes/{nid}/revisions/1/restore", headers=_auth(alice))
    assert r.status_code == 200
    assert r.json()["status"] == "restored"
    assert r.json()["version"] == 3

    note = client.get(f"/api/v1/notes/{nid}", headers=_auth(alice)).json()
    assert note["title"] == "v0-title"
    assert note["content_markdown"] == "v0-body"

    revs = _revisions(client, nid, alice)
    assert [x["version"] for x in revs] == [3, 2, 1]
    assert [x["cause"] for x in revs] == ["restore", "edit", "edit"]
    by_v = {x["version"]: x for x in revs}
    # v3 captured the pre-restore content.
    assert (by_v[3]["title"], by_v[3]["content_markdown"]) == ("v1-title", "v2-body")
    # Append-only: earlier rows are byte-identical, nothing removed.
    assert old_ids.issubset({x["id"] for x in revs})
    assert len(revs) == 3


def test_unchanged_put_creates_no_revision(client):
    alice = "user-hist-unchanged"
    nid = _create_note(client, alice, "t", "b")
    r = client.put(f"/api/v1/notes/{nid}", json={}, headers=_auth(alice))
    assert r.json()["status"] == "unchanged"
    assert _revisions(client, nid, alice) == []


def test_restore_missing_revision_404(client):
    alice = "user-hist-missing"
    nid = _create_note(client, alice, "t", "b")
    r = client.post(f"/api/v1/notes/{nid}/revisions/99/restore", headers=_auth(alice))
    assert r.status_code == 404


def test_restore_revision_on_trashed_note_404(client):
    alice = "user-hist-trash"
    nid = _create_note(client, alice, "t", "b")
    client.put(f"/api/v1/notes/{nid}", json={"content_markdown": "b2"}, headers=_auth(alice))
    client.delete(f"/api/v1/notes/{nid}", headers=_auth(alice))
    # A trashed note must be restored from the trash bin first.
    r = client.post(f"/api/v1/notes/{nid}/revisions/1/restore", headers=_auth(alice))
    assert r.status_code == 404


# ── cross-user isolation (negative tests) ────────────────────────────────────


def test_revisions_cross_user_isolation(client):
    alice, bob = "user-hist-a", "user-hist-b"
    nid = _create_note(client, alice, "secret-title", "secret-body")
    client.put(f"/api/v1/notes/{nid}", json={"content_markdown": "v2"}, headers=_auth(alice))

    # Bob must not see, read, or restore Alice's revisions (404, not 403:
    # corpus isolation hides the note's existence).
    assert client.get(f"/api/v1/notes/{nid}/revisions", headers=_auth(bob)).status_code == 404
    assert (
        client.post(f"/api/v1/notes/{nid}/revisions/1/restore", headers=_auth(bob)).status_code
        == 404
    )
    assert client.get(f"/api/v1/notes/{nid}", headers=_auth(bob)).status_code == 404

    # Alice's history is untouched.
    revs = _revisions(client, nid, alice)
    assert len(revs) == 1
