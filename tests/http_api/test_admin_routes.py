"""Tests for admin stats endpoint."""

import os
import pytest
from fastapi.testclient import TestClient

from stratum.http_api.app import app
from tests.conftest import SCHEMA_SQL

import duckdb


@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    conn.execute(SCHEMA_SQL)
    return conn


@pytest.fixture
def client_with_admin(monkeypatch, db):
    monkeypatch.setenv("ADMIN_SECRET", "test-secret-abc")

    def override_db():
        yield db

    from stratum.http_api.routes.admin import get_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_secret(monkeypatch, db):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)

    def override_db():
        yield db

    from stratum.http_api.routes.admin import get_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_admin_stats_no_secret_env_returns_503(client_no_secret):
    res = client_no_secret.get("/api/admin/stats", headers={"X-Admin-Secret": "anything"})
    assert res.status_code == 503


def test_admin_stats_wrong_secret_returns_403(client_with_admin):
    res = client_with_admin.get("/api/admin/stats", headers={"X-Admin-Secret": "wrong"})
    assert res.status_code == 403


def test_admin_stats_no_header_returns_403(client_with_admin):
    res = client_with_admin.get("/api/admin/stats")
    assert res.status_code == 403


def test_admin_stats_returns_counts(client_with_admin):
    res = client_with_admin.get("/api/admin/stats", headers={"X-Admin-Secret": "test-secret-abc"})
    assert res.status_code == 200
    body = res.json()
    assert "users" in body
    assert "substrates" in body
    assert "active_sessions" in body
    assert "feedback_submissions" in body
    assert "share_tokens" in body
    # Empty DB — all zeros
    assert body["users"] == 0
    assert body["substrates"] == 0


def test_admin_feedback_returns_list(client_with_admin, db):
    # Insert a feedback row
    db.execute("INSERT INTO feedback (id, user_id, content, page_url) VALUES ('fb1', 'u1', 'Great app', '/search')")
    res = client_with_admin.get("/api/admin/feedback", headers={"X-Admin-Secret": "test-secret-abc"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["content"] == "Great app"
