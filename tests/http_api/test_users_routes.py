"""Tests for /api/users routes — by-username (public) + sessions list/revoke."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db):
    from stratum.http_api.routes.users import router, get_db
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api/users")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


@pytest.fixture
def registered_user(db):
    from stratum.dao.users import UserDAO
    from stratum.auth.password import hash_password

    return UserDAO(db).create_user(
        email="alice@example.com",
        username="alice",
        password_hash=hash_password("TestPass123!"),
    )


@pytest.fixture
def user_token(registered_user):
    from stratum.auth.jwt_handler import encode_access

    return encode_access(registered_user.id, registered_user.corpus_id)


# ── by-username ──────────────────────────────────────────────────────────────


def test_get_profile_by_username_exists(client, registered_user):
    r = client.get("/api/users/by-username/alice")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice"
    assert "email" not in body
    assert "user_id" not in body
    assert "corpus_id" not in body
    assert "password_hash" not in body


def test_get_profile_by_username_includes_display_name_and_bio(client, db, registered_user):
    from stratum.dao.profile import ProfileDAO

    ProfileDAO(db).create_profile(registered_user.id, display_name="Alice Smith", bio="Hello world")
    r = client.get("/api/users/by-username/alice")
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Alice Smith"
    assert body["bio"] == "Hello world"


def test_get_profile_by_username_not_found(client):
    r = client.get("/api/users/by-username/doesnotexist")
    assert r.status_code == 404


def test_get_profile_by_username_suspended_returns_404(client, db, registered_user):
    db.execute("UPDATE users SET is_suspended = TRUE WHERE id = ?", (registered_user.id,))
    r = client.get("/api/users/by-username/alice")
    assert r.status_code == 404


def test_get_profile_by_username_inactive_returns_404(client, db, registered_user):
    db.execute("UPDATE users SET is_active = FALSE WHERE id = ?", (registered_user.id,))
    r = client.get("/api/users/by-username/alice")
    assert r.status_code == 404


# ── sessions list ────────────────────────────────────────────────────────────


def test_list_sessions_requires_auth(client):
    r = client.get("/api/users/me/sessions")
    assert r.status_code == 401


def test_list_sessions_returns_active_sessions(client, db, registered_user, user_token):
    from stratum.dao.sessions import SessionDAO

    SessionDAO(db).create_session(
        user_id=registered_user.id,
        refresh_token_hash="hash1",
        user_agent="TestUA",
        ip="10.0.0.1",
    )
    r = client.get(
        "/api/users/me/sessions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["user_agent"] == "TestUA"
    assert "refresh_token_hash" not in item


def test_list_sessions_ip_masked(client, db, registered_user, user_token):
    from stratum.dao.sessions import SessionDAO

    SessionDAO(db).create_session(
        user_id=registered_user.id,
        refresh_token_hash="hash2",
        user_agent=None,
        ip="192.168.100.200",
    )
    r = client.get(
        "/api/users/me/sessions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert len(item.get("ip_address", "") or "") <= 16


def test_list_sessions_excludes_other_users(client, db, registered_user, user_token):
    from stratum.dao.users import UserDAO
    from stratum.auth.password import hash_password
    from stratum.dao.sessions import SessionDAO

    other = UserDAO(db).create_user(
        email="bob@example.com",
        username="bob",
        password_hash=hash_password("Test123456!"),
    )
    SessionDAO(db).create_session(
        user_id=other.id, refresh_token_hash="other_hash", user_agent=None, ip=None
    )
    r = client.get(
        "/api/users/me/sessions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 0


# ── sessions revoke ──────────────────────────────────────────────────────────


def test_revoke_own_session(client, db, registered_user, user_token):
    from stratum.dao.sessions import SessionDAO

    s = SessionDAO(db).create_session(
        user_id=registered_user.id, refresh_token_hash="h3", user_agent=None, ip=None
    )
    r = client.delete(
        f"/api/users/me/sessions/{s.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"


def test_revoke_other_users_session_returns_404(client, db, registered_user, user_token):
    from stratum.dao.users import UserDAO
    from stratum.auth.password import hash_password
    from stratum.dao.sessions import SessionDAO

    other = UserDAO(db).create_user(
        email="bob@example.com",
        username="bob",
        password_hash=hash_password("Test123456!"),
    )
    s = SessionDAO(db).create_session(
        user_id=other.id, refresh_token_hash="other_h", user_agent=None, ip=None
    )
    r = client.delete(
        f"/api/users/me/sessions/{s.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 404


def test_revoke_session_idempotent(client, db, registered_user, user_token):
    from stratum.dao.sessions import SessionDAO

    s = SessionDAO(db).create_session(
        user_id=registered_user.id, refresh_token_hash="h4", user_agent=None, ip=None
    )
    client.delete(
        f"/api/users/me/sessions/{s.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    r = client.delete(
        f"/api/users/me/sessions/{s.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
