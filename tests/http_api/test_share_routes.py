"""Tests for share routes + data leak red-line tests — §6.6."""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stratum.http_api.routes.share import router, get_db
from stratum.auth.jwt_handler import encode_access
from stratum.dao.users import UserDAO
from stratum.dao.note import NoteDAO
from stratum.dao.share_tokens import ShareTokenDAO


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: (yield db)
    return TestClient(app)


@pytest.fixture
def user_a(db):
    return UserDAO(db).create_user(email="a@t.com", username="alice", password_hash="h")


@pytest.fixture
def user_b(db):
    return UserDAO(db).create_user(email="b@t.com", username="bob", password_hash="h")


@pytest.fixture
def note_a(db, user_a):
    return NoteDAO(db).create_note(corpus_id=user_a.corpus_id, title="Alice Note", content="Hello world [[_private_ref]]")


def _auth(user):
    return {"Authorization": f"Bearer {encode_access(user.id, user.corpus_id)}"}


# --- Create share ---

def test_create_share_success(client, user_a, note_a):
    r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    assert r.status_code == 200
    assert "token" in r.json()
    assert r.json()["share_url"].startswith("/share/")


def test_create_share_nonexistent_note(client, user_a):
    r = client.post("/api/share/note/fake_id", json={}, headers=_auth(user_a))
    assert r.status_code == 404


def test_create_share_other_users_note(client, user_a, user_b, db):
    note_b = NoteDAO(db).create_note(corpus_id=user_b.corpus_id, title="Bob Note", content="x")
    r = client.post(f"/api/share/note/{note_b.id}", json={}, headers=_auth(user_a))
    assert r.status_code == 404  # A can't see B's note


def test_create_share_with_expiry(client, user_a, note_a):
    r = client.post(f"/api/share/note/{note_a.id}", json={"expires_in_days": 7}, headers=_auth(user_a))
    assert r.json()["expires_at"] is not None


# --- List shares ---

def test_list_shares(client, user_a, note_a):
    client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    r = client.get("/api/shares", headers=_auth(user_a))
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_shares_empty(client, user_a):
    r = client.get("/api/shares", headers=_auth(user_a))
    assert r.json()["total"] == 0


# --- Revoke ---

def test_revoke_share(client, user_a, note_a):
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.delete(f"/api/share/{token}", headers=_auth(user_a))
    assert r.status_code == 200


def test_user_B_cannot_revoke_user_A_share(client, user_a, user_b, note_a):
    """Red-line: B cannot revoke A's share."""
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.delete(f"/api/share/{token}", headers=_auth(user_b))
    assert r.status_code == 403


# --- Public access ---

def test_public_access_success(client, user_a, note_a):
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.get(f"/share/{token}")
    assert r.status_code == 200
    assert r.json()["title"] == "Alice Note"
    assert r.json()["shared_by_username"] == "alice"


def test_public_access_nonexistent_token(client):
    r = client.get("/share/nonexistent_token")
    assert r.status_code == 404


def test_public_access_revoked_returns_410(client, user_a, note_a):
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    client.delete(f"/api/share/{token}", headers=_auth(user_a))
    r = client.get(f"/share/{token}")
    assert r.status_code == 410


def test_public_access_expired_returns_410(client, user_a, note_a, db):
    """Expired share returns 410."""
    create_r = client.post(f"/api/share/note/{note_a.id}", json={"expires_in_days": 1}, headers=_auth(user_a))
    token = create_r.json()["token"]
    # Manually expire it
    past = datetime.now(timezone.utc) - timedelta(days=2)
    db.execute("UPDATE share_tokens SET expires_at = ? WHERE token = ?", (past, token))
    r = client.get(f"/share/{token}")
    assert r.status_code == 410


# --- Data leak red-line tests ---

def test_public_response_no_user_id(client, user_a, note_a):
    """Red-line: public response must not contain user_id."""
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.get(f"/share/{token}")
    body = r.json()
    assert "user_id" not in body
    assert "corpus_id" not in body
    assert "email" not in body


def test_public_response_strips_private_refs(client, user_a, note_a):
    """Red-line: private wikilinks stripped from public content."""
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.get(f"/share/{token}")
    assert "[[_private" not in r.json()["content"]
    assert "私有引用" in r.json()["content"]


def test_public_access_increments_count(client, user_a, note_a, db):
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    client.get(f"/share/{token}")
    client.get(f"/share/{token}")
    share = ShareTokenDAO(db).get_share_token(token)
    assert share.access_count == 2


def test_no_auth_required_for_public(client, user_a, note_a):
    """Public share accessible without any Authorization header."""
    create_r = client.post(f"/api/share/note/{note_a.id}", json={}, headers=_auth(user_a))
    token = create_r.json()["token"]
    r = client.get(f"/share/{token}")  # No auth header
    assert r.status_code == 200
