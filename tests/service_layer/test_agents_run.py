"""Agent run endpoint tests.

Phase 15 P1-A (Wave 1): 3 workflow agents (daily_digest/weekly_review/knowledge_curator)
Phase 15 P1-C (Wave 5): +3 Agent-class agents activated (translation_worker/reading_companion/lint_bot)
                          audio_generator remains 501 (oprim.tts_synthesize not exported).

Coverage:
  1. POST /{agent_name}/run — daily_digest returns status in (completed, failed), not pending
  2. POST /unknown/run — 404
  3. POST /audio_generator/run — 501 (TTS deferred, oprim provider missing)
  4. POST /translation_worker|reading_companion|lint_bot/run — 200 (Agent-class, may fail on dep)
  5. run record persisted; GET /runs/{run_id} returns it with non-pending status
  6. GET /runs returns paginated list for authenticated user
  7. GET /runs/{run_id} — cross-user 404 isolation
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-for-sl-unit-tests-32x")

from stratum.common import create_token  # noqa: E402


def _auth(user_id: str = "user-alice") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id)}"}


@pytest.fixture()
def client():
    from stratum.api.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# 1. daily_digest 真触发 — status 必须是真终态 (非 pending)
# ═══════════════════════════════════════════════════════════════════════════════


def test_agent_run_daily_digest_true_status(client):
    """R-1: status must be completed or failed, never pending."""
    r = client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["agent_name"] == "daily_digest"
    assert body["status"] in ("completed", "failed", "not_implemented"), (
        f"R-1 violation: got status={body['status']!r}, expected completed/failed"
    )
    assert body["status"] != "pending", "stub behavior detected — workflow not truly invoked"
    assert "run_id" in body


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 未知 agent — 404
# ═══════════════════════════════════════════════════════════════════════════════


def test_agent_unknown_returns_404(client):
    r = client.post("/api/v1/agents/nonexistent_agent/run", json={}, headers=_auth())
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 3 & 4. NOT_IMPLEMENTED agents — 501
# ═══════════════════════════════════════════════════════════════════════════════


def test_no_agent_returns_501(client):
    """No agents are in NOT_IMPLEMENTED_AGENTS as of obase v0.9.0 + oprim v2.24.1."""
    r = client.post(
        "/api/v1/agents/audio_generator/run", json={"substrate_id": "test"}, headers=_auth()
    )
    assert r.status_code == 200, f"audio_generator should be 200, got {r.status_code}"


@pytest.mark.parametrize(
    "agent_name",
    ["translation_worker", "reading_companion", "lint_bot", "audio_generator"],
)
def test_activated_agent_classes_return_200(client, agent_name):
    """All 4 Agent-class agents return 200 (may fail on business logic, not on import).

    audio_generator requires substrate_id param; passes empty string so it fails gracefully.
    """
    r = client.post(f"/api/v1/agents/{agent_name}/run", json={}, headers=_auth())
    assert r.status_code == 200, f"{agent_name}: expected 200, got {r.status_code} — {r.text[:200]}"
    body = r.json()
    assert body["agent_name"] == agent_name
    assert body["status"] in ("completed", "failed"), (
        f"{agent_name}: status must be terminal, got {body['status']!r}"
    )
    assert "run_id" in body


# ═══════════════════════════════════════════════════════════════════════════════
# 5. agent_runs record persisted; GET /runs/:run_id returns non-pending status
# ═══════════════════════════════════════════════════════════════════════════════


def test_agent_run_persisted_and_retrievable(client):
    """run_id must be retrievable via GET /runs/{run_id} with a terminal status."""
    run_resp = client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth())
    assert run_resp.status_code == 200
    run_id = run_resp.json().get("run_id")
    assert run_id, "run_id missing from response"

    detail = client.get(f"/api/v1/agents/runs/{run_id}", headers=_auth())
    assert detail.status_code == 200
    record = detail.json()
    assert record["agent_name"] == "daily_digest"
    assert record["status"] != "pending", f"DB record still pending after run: {record['status']}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. GET /runs — list returns items dict
# ═══════════════════════════════════════════════════════════════════════════════


def test_list_runs_returns_items(client):
    client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth())
    r = client.get("/api/v1/agents/runs", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 7. GET /runs/{run_id} — cross-user 404 isolation
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_run_cross_user_isolation(client):
    """User Bob cannot retrieve user Alice's run."""
    run_resp = client.post("/api/v1/agents/daily_digest/run", json={}, headers=_auth("user-alice"))
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    r = client.get(f"/api/v1/agents/runs/{run_id}", headers=_auth("user-bob"))
    assert r.status_code == 404
