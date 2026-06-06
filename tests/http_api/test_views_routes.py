"""Tests for /api/v1/views — CRUD + lazy preset seed."""

import json
import pytest
import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from stratum.api.routers.views import router
from stratum.common import create_token, jwt_auth


# ── Fixtures ─────────────────────────────────────────────────────────────────

USER_A = "user_a_test_id"
USER_B = "user_b_test_id"

USV_DDL = """
CREATE TABLE IF NOT EXISTS user_saved_views (
    id           VARCHAR PRIMARY KEY,
    user_id      VARCHAR NOT NULL,
    name         VARCHAR NOT NULL,
    description  VARCHAR,
    is_preset    BOOLEAN DEFAULT FALSE,
    icon         VARCHAR,
    filter_json  JSON DEFAULT '{}',
    sort_by      VARCHAR DEFAULT 'created_at',
    sort_order   VARCHAR DEFAULT 'desc',
    display_mode VARCHAR DEFAULT 'list',
    position     INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);
"""


@pytest.fixture
def mem_db():
    conn = duckdb.connect(":memory:")
    conn.execute(USV_DDL)
    yield conn
    conn.close()


@pytest.fixture
def client(mem_db):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[jwt_auth] = lambda: USER_A

    with patch("stratum.api.routers.views._conn") as mock_conn:
        mock_conn.return_value.__enter__ = lambda s: mem_db
        mock_conn.return_value.__exit__ = lambda s, *a: None
        yield TestClient(app)


def _auth():
    return {"Authorization": f"Bearer {create_token(USER_A)}"}


# ── Tests: GET /api/v1/views ──────────────────────────────────────────────────

def test_list_views_seeds_presets(client):
    """First call seeds 5 preset views."""
    r = client.get("/api/v1/views", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    names = [v["name"] for v in data]
    assert "通用" in names
    assert "量化金融" in names


def test_list_views_no_double_seed(client):
    """Second call does NOT duplicate presets."""
    client.get("/api/v1/views", headers=_auth())
    r = client.get("/api/v1/views", headers=_auth())
    assert len(r.json()) == 5


def test_list_views_returns_filter_json_as_dict(client):
    r = client.get("/api/v1/views", headers=_auth())
    for v in r.json():
        assert isinstance(v["filter_json"], dict)


# ── Tests: POST /api/v1/views ─────────────────────────────────────────────────

def test_create_view(client):
    r = client.post("/api/v1/views", json={
        "name": "我的论文",
        "icon": "📄",
        "filter_json": {"medium": ["paper"], "tags": ["ml"]},
        "sort_by": "created_at",
        "sort_order": "desc",
    }, headers=_auth())
    assert r.status_code == 201
    d = r.json()
    assert d["name"] == "我的论文"
    assert d["is_preset"] is False
    assert d["filter_json"]["medium"] == ["paper"]


def test_create_view_appears_in_list(client):
    client.post("/api/v1/views", json={"name": "测试视图"}, headers=_auth())
    r = client.get("/api/v1/views", headers=_auth())
    names = [v["name"] for v in r.json()]
    assert "测试视图" in names


# ── Tests: PUT /api/v1/views/{id} ─────────────────────────────────────────────

def test_update_custom_view(client):
    # Create a custom view first
    create_r = client.post("/api/v1/views", json={"name": "原名"}, headers=_auth())
    vid = create_r.json()["id"]

    r = client.put(f"/api/v1/views/{vid}", json={"name": "新名"}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["name"] == "新名"


def test_update_preset_returns_403(client):
    views = client.get("/api/v1/views", headers=_auth()).json()
    preset_id = next(v["id"] for v in views if v["is_preset"])
    r = client.put(f"/api/v1/views/{preset_id}", json={"name": "hack"}, headers=_auth())
    assert r.status_code == 403


def test_update_nonexistent_returns_404(client):
    r = client.put("/api/v1/views/fake_id", json={"name": "x"}, headers=_auth())
    assert r.status_code == 404


# ── Tests: DELETE /api/v1/views/{id} ─────────────────────────────────────────

def test_delete_custom_view(client):
    create_r = client.post("/api/v1/views", json={"name": "删我"}, headers=_auth())
    vid = create_r.json()["id"]
    r = client.delete(f"/api/v1/views/{vid}", headers=_auth())
    assert r.status_code == 204
    # Confirm gone
    names = [v["name"] for v in client.get("/api/v1/views", headers=_auth()).json()]
    assert "删我" not in names


def test_delete_preset_returns_403(client):
    views = client.get("/api/v1/views", headers=_auth()).json()
    preset_id = next(v["id"] for v in views if v["is_preset"])
    r = client.delete(f"/api/v1/views/{preset_id}", headers=_auth())
    assert r.status_code == 403


def test_delete_nonexistent_returns_404(client):
    r = client.delete("/api/v1/views/fake_id", headers=_auth())
    assert r.status_code == 404
