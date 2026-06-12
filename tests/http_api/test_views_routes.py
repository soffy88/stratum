import pytest
from fastapi.testclient import TestClient
from stratum.common import create_token
from stratum.api.main import app

def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_list_views_seeds_presets(client, db):
    # db is the in-memory duckdb from conftest
    resp = client.get("/api/v1/views", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    # Expect 5 presets to be seeded
    presets = [v for v in data if v["is_preset"]]
    assert len(presets) == 5
    assert any(p["name"] == "量化金融" for p in presets)

def test_create_view(client, db):
    resp = client.post("/api/v1/views", json={
        "name": "My Custom View",
        "description": "test desc",
        "filter_json": {"tags": ["finance"]}
    }, headers=_auth())
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Custom View"
    assert data["is_preset"] is False

def test_update_view(client, db):
    # Create first
    r = client.post("/api/v1/views", json={"name": "Old Name"}, headers=_auth())
    vid = r.json()["id"]
    
    # Update
    resp = client.put(f"/api/v1/views/{vid}", json={"name": "New Name"}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

def test_delete_view(client, db):
    r = client.post("/api/v1/views", json={"name": "To Delete"}, headers=_auth())
    vid = r.json()["id"]
    
    resp = client.delete(f"/api/v1/views/{vid}", headers=_auth())
    assert resp.status_code == 204
    
    # Verify gone
    r2 = client.get("/api/v1/views", headers=_auth())
    assert all(v["id"] != vid for v in r2.json())

def test_modify_preset_forbidden(client, db):
    r = client.get("/api/v1/views", headers=_auth())
    preset_id = next(v["id"] for v in r.json() if v["is_preset"])
    
    resp = client.put(f"/api/v1/views/{preset_id}", json={"name": "Evil"}, headers=_auth())
    assert resp.status_code == 403
