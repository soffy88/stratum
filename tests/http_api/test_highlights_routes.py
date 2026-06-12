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

def test_list_highlights_empty(client, db):
    resp = client.get("/api/v1/highlights", headers=_auth())
    assert resp.status_code == 200
    assert resp.json() == []

def test_delete_highlight_not_found(client, db):
    resp = client.delete("/api/v1/highlights/non-existent", headers=_auth())
    assert resp.status_code == 404
