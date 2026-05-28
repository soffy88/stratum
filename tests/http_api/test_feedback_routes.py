"""Tests for POST /api/feedback route."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(db):
    from stratum.http_api.routes.feedback import router, get_db
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


@pytest.fixture
def user_token(db):
    from stratum.dao.users import UserDAO
    from stratum.auth.password import hash_password
    from stratum.auth.jwt_handler import encode_access

    user = UserDAO(db).create_user(
        email="fb@example.com",
        username="fbuser",
        password_hash=hash_password("Test123456!"),
    )
    return encode_access(user.id, user.corpus_id), user.id


def test_feedback_requires_auth(client):
    r = client.post("/api/feedback", json={"content": "Hello"})
    assert r.status_code == 401


def test_feedback_submit_success(client, user_token):
    token, _ = user_token
    r = client.post(
        "/api/feedback",
        json={"content": "Great app!", "page_url": "/search"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "received"


def test_feedback_empty_content_rejected(client, user_token):
    token, _ = user_token
    r = client.post(
        "/api/feedback",
        json={"content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (400, 422)


def test_feedback_stored_in_db(client, db, user_token):
    token, user_id = user_token
    client.post(
        "/api/feedback",
        json={"content": "Bug report", "page_url": "/jobs"},
        headers={"Authorization": f"Bearer {token}"},
    )
    rows = db.execute("SELECT content, user_id FROM feedback").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Bug report"
    assert rows[0][1] == user_id
