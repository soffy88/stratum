"""Phase 15 P1-B2: Scheduled jobs CRUD + run-now tests.

Coverage (≥10 tests):
  1-2.   POST create → job_id returned; GET list shows it
  3.     GET /{id} → 200 detail
  4.     GET /{id} cross-user → 404
  5.     PUT update name → updated
  6.     PUT update enabled=False → disabled
  7.     PUT unknown job → 404
  8.     DELETE → 200; subsequent GET → 404
  9.     DELETE cross-user → 404
  10.    POST run-now valid job (daily_digest) → run_id + non-pending status
  11.    POST run-now cross-user job → 404
  12.    POST run-now not-implemented agent → 501
  13.    GET /{id}/runs → list (may be empty)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402


def _auth(uid: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(uid)}"}


_JOB_BODY = {
    "name": "Morning digest",
    "agent_name": "daily_digest",
    "cron_expression": "0 8 * * *",
}

_STUB_JOB_BODY = {
    "name": "Stub job",
    "agent_name": "audio_generator",
    "cron_expression": "0 2 * * *",
}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── helpers ───────────────────────────────────────────────────────────────────


def _create(client, body=None, uid="user-alice") -> str:
    r = client.post("/api/v1/scheduled-jobs", json=body or _JOB_BODY, headers=_auth(uid))
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST create returns job_id
# ═══════════════════════════════════════════════════════════════════════════════


def test_create_job_returns_job_id(client):
    r = client.post("/api/v1/scheduled-jobs", json=_JOB_BODY, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "created"
    assert len(body["job_id"]) == 26  # ULID


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET list shows created job
# ═══════════════════════════════════════════════════════════════════════════════


def test_list_jobs_shows_created(client):
    jid = _create(client)
    r = client.get("/api/v1/scheduled-jobs", headers=_auth())
    assert r.status_code == 200
    jobs = r.json()
    assert isinstance(jobs, list)
    ids = [j["id"] for j in jobs]
    assert jid in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GET /{id} detail
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_job_detail(client):
    jid = _create(client)
    r = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth())
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == jid
    assert j["agent_name"] == "daily_digest"
    assert j["cron_expression"] == "0 8 * * *"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GET /{id} cross-user → 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_job_cross_user_404(client):
    jid = _create(client, uid="user-alice")
    r = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth("user-bob"))
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PUT update name
# ═══════════════════════════════════════════════════════════════════════════════


def test_update_job_name(client):
    jid = _create(client)
    r = client.put(
        f"/api/v1/scheduled-jobs/{jid}",
        json={"name": "Evening digest"},
        headers=_auth(),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "updated"
    detail = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth()).json()
    assert detail["name"] == "Evening digest"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PUT update enabled=False
# ═══════════════════════════════════════════════════════════════════════════════


def test_update_job_disable(client):
    jid = _create(client)
    r = client.put(
        f"/api/v1/scheduled-jobs/{jid}",
        json={"enabled": False},
        headers=_auth(),
    )
    assert r.status_code == 200
    detail = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth()).json()
    assert detail["enabled"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PUT unknown job → 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_update_unknown_job_404(client):
    r = client.put(
        "/api/v1/scheduled-jobs/NONEXISTENT000000000000000",
        json={"name": "X"},
        headers=_auth(),
    )
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 8. DELETE → 200; subsequent GET → 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_delete_job(client):
    jid = _create(client)
    r = client.delete(f"/api/v1/scheduled-jobs/{jid}", headers=_auth())
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    r2 = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth())
    assert r2.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 9. DELETE cross-user → 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_delete_job_cross_user_404(client):
    jid = _create(client, uid="user-alice")
    r = client.delete(f"/api/v1/scheduled-jobs/{jid}", headers=_auth("user-bob"))
    assert r.status_code == 404
    # Job still exists for alice
    r2 = client.get(f"/api/v1/scheduled-jobs/{jid}", headers=_auth("user-alice"))
    assert r2.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 10. POST run-now valid job → non-pending status + run_id
# ═══════════════════════════════════════════════════════════════════════════════


def test_run_now_daily_digest(client):
    jid = _create(client)
    r = client.post(f"/api/v1/scheduled-jobs/{jid}/run-now", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert body["agent_name"] == "daily_digest"
    assert body["status"] != "pending", f"R-1: got pending from run-now, {body}"
    assert body["status"] in ("completed", "failed", "not_implemented")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. POST run-now cross-user job → 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_run_now_cross_user_404(client):
    jid = _create(client, uid="user-alice")
    r = client.post(f"/api/v1/scheduled-jobs/{jid}/run-now", headers=_auth("user-bob"))
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 12. POST run-now stub agent → 501
# ═══════════════════════════════════════════════════════════════════════════════


def test_run_now_stub_agent_501(client):
    jid = _create(client, body=_STUB_JOB_BODY)
    r = client.post(f"/api/v1/scheduled-jobs/{jid}/run-now", headers=_auth())
    assert r.status_code == 501, f"Expected 501 for stub agent, got {r.status_code}"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. GET /{id}/runs → list response
# ═══════════════════════════════════════════════════════════════════════════════


def test_list_job_runs(client):
    jid = _create(client)
    r = client.get(f"/api/v1/scheduled-jobs/{jid}/runs", headers=_auth())
    assert r.status_code == 200
    assert isinstance(r.json(), list)
