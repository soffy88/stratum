"""Integration tests for stratum.http_api.routes.auth — ≥15 tests per §3.7."""
import pytest
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from stratum.auth.jwt_handler import encode_access, decode_access


@pytest.fixture
def client(db):
    """TestClient with patched DB connection."""
    from stratum.http_api.routes.auth import router, get_db
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/auth")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_register_success(client):
    r = client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_register_duplicate_email(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/register", json={"email": "a@b.com", "username": "bob", "password": "Test123456!"})
    assert r.status_code == 400


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/register", json={"email": "c@d.com", "username": "alice", "password": "Test123456!"})
    assert r.status_code == 400


def test_register_weak_password(client):
    r = client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "short"})
    assert r.status_code in (400, 422)


def test_register_invalid_username(client):
    r = client.post("/api/auth/register", json={"email": "a@b.com", "username": "a b", "password": "Test123456!"})
    assert r.status_code == 422


def test_login_success(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "Test123456!"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_by_username(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/login", json={"email_or_username": "alice", "password": "Test123456!"})
    assert r.status_code == 200


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "WrongPass1!"})
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    r = client.post("/api/auth/login", json={"email_or_username": "nobody@x.com", "password": "Test123456!"})
    assert r.status_code == 401


def test_login_sets_refresh_cookie(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    r = client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "Test123456!"})
    assert "refresh_token" in r.cookies


def test_me_with_valid_token(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    login_r = client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "Test123456!"})
    token = login_r.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_me_without_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token"})
    assert r.status_code == 401


def test_refresh_success(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    login_r = client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "Test123456!"})
    # Cookie is set by login response, TestClient persists it
    refresh_token = login_r.cookies.get("refresh_token")
    r = client.post("/api/auth/refresh", cookies={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_without_cookie(client):
    r = client.post("/api/auth/refresh", cookies={"refresh_token": ""})
    assert r.status_code == 401


def test_logout_success(client):
    client.post("/api/auth/register", json={"email": "a@b.com", "username": "alice", "password": "Test123456!"})
    client.post("/api/auth/login", json={"email_or_username": "a@b.com", "password": "Test123456!"})
    r = client.post("/api/auth/logout")
    assert r.status_code == 200


def test_full_flow_register_login_me_refresh_logout(client):
    """End-to-end: register → login → me → refresh → logout."""
    reg = client.post("/api/auth/register", json={"email": "flow@t.com", "username": "flow", "password": "FlowTest12!"})
    assert reg.status_code == 200
    login = client.post("/api/auth/login", json={"email_or_username": "flow@t.com", "password": "FlowTest12!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    refresh_cookie = login.cookies.get("refresh_token")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "flow@t.com"
    refresh = client.post("/api/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert refresh.status_code == 200
    new_token = refresh.json()["access_token"]
    # Verify new token is valid (may equal old token if within same second)
    new_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert new_me.status_code == 200
    logout = client.post("/api/auth/logout", cookies={"refresh_token": refresh_cookie})
    assert logout.status_code == 200
