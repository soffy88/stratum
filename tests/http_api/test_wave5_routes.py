"""Tests for Wave 5 REST API routes + corpus isolation — §7.3."""

import pytest
import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from stratum.auth.jwt_handler import encode_access
from stratum.middleware.corpus_isolation import corpus_isolation_middleware
from stratum.http_api.routes import search, substrates, notes, agents, scheduled_jobs
from stratum.dao.users import UserDAO
from stratum.dao.note import NoteDAO
from stratum.utils.user_id_hash import hash_user_id


@pytest.fixture
def app_client(db):
    """Full app with middleware + all Wave 5 routes, using in-memory DB."""
    app = FastAPI()

    @app.middleware("http")
    async def mw(request: Request, call_next):
        return await corpus_isolation_middleware(request, call_next)

    @app.exception_handler(Exception)
    async def exc(request, exc):
        from fastapi.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # Override get_db for all route modules
    def override_db():
        yield db

    from stratum.http_api.routes.search import get_db as search_get_db
    from stratum.http_api.routes.substrates import get_db as sub_get_db
    from stratum.http_api.routes.notes import get_db as notes_get_db
    from stratum.http_api.routes.agents import get_db as agents_get_db
    from stratum.http_api.routes.scheduled_jobs import get_db as jobs_get_db

    app.include_router(search.router, prefix="/api")
    app.include_router(substrates.router, prefix="/api")
    app.include_router(notes.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(scheduled_jobs.router, prefix="/api")

    app.dependency_overrides[search_get_db] = override_db
    app.dependency_overrides[sub_get_db] = override_db
    app.dependency_overrides[notes_get_db] = override_db
    app.dependency_overrides[agents_get_db] = override_db
    app.dependency_overrides[jobs_get_db] = override_db

    return TestClient(app, raise_server_exceptions=False), db


@pytest.fixture
def users(db):
    dao = UserDAO(db)
    a = dao.create_user(email="a@w5.com", username="userA_w5", password_hash="h")
    b = dao.create_user(email="b@w5.com", username="userB_w5", password_hash="h")
    return a, b


def _h(user):
    return {"Authorization": f"Bearer {encode_access(user.id, user.corpus_id)}"}


# --- Search ---


def test_search_requires_auth(app_client):
    client, _ = app_client
    r = client.post("/api/search", json={"query": "test"})
    assert r.status_code == 401


def test_search_returns_results(app_client, users):
    client, db = app_client
    a, _ = users
    # substrates (plural, user_id) — Phase 14 schema used by SubstrateDAO post-filter
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(a.id), "Machine Learning Intro"),
    )
    from unittest.mock import patch, AsyncMock
    from types import SimpleNamespace

    mock_results = [
        SimpleNamespace(
            type="substrate", id="s1", title="Machine Learning Intro", score=0.9, highlight=None
        )
    ]
    with patch(
        "stratum.service.search.hybrid_search", new_callable=AsyncMock, return_value=mock_results
    ):
        with patch("stratum.service.search.duckdb") as mock_ddb:
            mock_ddb.connect.return_value = db
            r = client.post("/api/search", json={"query": "Machine"}, headers=_h(a))
    assert r.status_code == 200
    assert len(r.json()["results"]) >= 1


def test_search_corpus_isolated(app_client, users):
    client, db = app_client
    a, b = users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(b.id), "Secret B Doc"),
    )
    r = client.post("/api/search", json={"query": "Secret"}, headers=_h(a))
    assert all(item["id"] != "s1" for item in r.json()["results"])


# --- Substrates ---


def test_list_substrates(app_client, users):
    client, db = app_client
    a, _ = users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(a.id), "Doc A"),
    )
    r = client.get("/api/substrates", headers=_h(a))
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_substrates_corpus_isolated(app_client, users):
    client, db = app_client
    a, b = users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(b.id), "B Doc"),
    )
    r = client.get("/api/substrates", headers=_h(a))
    assert r.json()["total"] == 0


def test_get_substrate_by_id(app_client, users):
    client, db = app_client
    a, _ = users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(a.id), "My Doc"),
    )
    r = client.get("/api/substrates/s1", headers=_h(a))
    assert r.status_code == 200
    assert r.json()["title"] == "My Doc"


def test_get_substrate_cross_corpus_404(app_client, users):
    client, db = app_client
    a, b = users
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(b.id), "B Doc"),
    )
    r = client.get("/api/substrates/s1", headers=_h(a))
    assert r.status_code == 404


def test_get_derivatives(app_client, users):
    client, db = app_client
    a, _ = users
    # substrates (plural) for ownership check; derivative keeps corpus_id
    db.execute(
        "INSERT INTO substrates (id, user_id, title) VALUES (?,?,?)",
        ("s1", hash_user_id(a.id), "Doc"),
    )
    db.execute(
        "INSERT INTO derivative (id, substrate_id, kind, seq, content, corpus_id) VALUES (?,?,?,?,?,?)",
        ("d1", "s1", "chunk", 0, "text content", a.corpus_id),
    )
    r = client.get("/api/substrates/s1/derivatives", headers=_h(a))
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


# --- Notes/Backlinks ---


def test_get_backlinks(app_client, users):
    client, db = app_client
    a, _ = users
    n1 = NoteDAO(db).create_note(corpus_id=a.corpus_id, title="Target", content="main")
    db.execute(
        "INSERT INTO note (id, corpus_id, title, content, wikilinks) VALUES (?,?,?,?,?)",
        ("n2", a.corpus_id, "Referrer", "see target", n1.id),
    )
    r = client.get(f"/api/notes/{n1.id}/backlinks", headers=_h(a))
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_backlinks_cross_corpus_404(app_client, users):
    client, db = app_client
    a, b = users
    n = NoteDAO(db).create_note(corpus_id=b.corpus_id, title="B Note", content="x")
    r = client.get(f"/api/notes/{n.id}/backlinks", headers=_h(a))
    assert r.status_code == 404


# --- Agents ---


def test_run_agent(app_client, users):
    client, db = app_client
    a, _ = users
    r = client.post("/api/agents/daily_digest/run", json={"params": {}}, headers=_h(a))
    assert r.status_code == 200
    assert r.json()["agent_run"]["status"] == "pending"


def test_list_agent_runs(app_client, users):
    client, db = app_client
    a, _ = users
    client.post("/api/agents/reading_companion/run", json={"params": {}}, headers=_h(a))
    r = client.get("/api/agents/runs", headers=_h(a))
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_agent_runs_corpus_isolated(app_client, users):
    client, db = app_client
    a, b = users
    client.post("/api/agents/test/run", json={"params": {}}, headers=_h(a))
    r = client.get("/api/agents/runs", headers=_h(b))
    assert r.json()["total"] == 0


# --- Scheduled Jobs ---


def test_create_scheduled_job(app_client, users):
    client, _ = app_client
    a, _ = users
    r = client.post(
        "/api/scheduled_jobs",
        json={"name": "Daily Digest", "agent_name": "daily_digest", "cron_expression": "0 8 * * *"},
        headers=_h(a),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Daily Digest"


def test_list_scheduled_jobs(app_client, users):
    client, _ = app_client
    a, _ = users
    client.post(
        "/api/scheduled_jobs",
        json={"name": "J1", "agent_name": "a1", "cron_expression": "0 * * * *"},
        headers=_h(a),
    )
    r = client.get("/api/scheduled_jobs", headers=_h(a))
    assert r.json()["total"] == 1


def test_update_scheduled_job(app_client, users):
    client, _ = app_client
    a, _ = users
    create_r = client.post(
        "/api/scheduled_jobs",
        json={"name": "J1", "agent_name": "a1", "cron_expression": "0 * * * *"},
        headers=_h(a),
    )
    job_id = create_r.json()["id"]
    r = client.put(f"/api/scheduled_jobs/{job_id}", json={"enabled": False}, headers=_h(a))
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_delete_scheduled_job(app_client, users):
    client, _ = app_client
    a, _ = users
    create_r = client.post(
        "/api/scheduled_jobs",
        json={"name": "J1", "agent_name": "a1", "cron_expression": "0 * * * *"},
        headers=_h(a),
    )
    job_id = create_r.json()["id"]
    r = client.delete(f"/api/scheduled_jobs/{job_id}", headers=_h(a))
    assert r.status_code == 200


def test_scheduled_jobs_corpus_isolated(app_client, users):
    client, _ = app_client
    a, b = users
    client.post(
        "/api/scheduled_jobs",
        json={"name": "A Job", "agent_name": "a1", "cron_expression": "0 * * * *"},
        headers=_h(a),
    )
    r = client.get("/api/scheduled_jobs", headers=_h(b))
    assert r.json()["total"] == 0


def test_delete_cross_corpus_404(app_client, users):
    client, _ = app_client
    a, b = users
    create_r = client.post(
        "/api/scheduled_jobs",
        json={"name": "A Job", "agent_name": "a1", "cron_expression": "0 * * * *"},
        headers=_h(a),
    )
    job_id = create_r.json()["id"]
    r = client.delete(f"/api/scheduled_jobs/{job_id}", headers=_h(b))
    assert r.status_code == 404


# --- All routes require auth ---


def test_all_api_routes_require_auth(app_client):
    client, _ = app_client
    endpoints = [
        ("post", "/api/search", {"query": "test"}),
        ("get", "/api/substrates", None),
        ("get", "/api/substrates/fake", None),
        ("get", "/api/notes/fake/backlinks", None),
        ("post", "/api/agents/test/run", {"params": {}}),
        ("get", "/api/agents/runs", None),
        ("get", "/api/scheduled_jobs", None),
        (
            "post",
            "/api/scheduled_jobs",
            {"name": "x", "agent_name": "a", "cron_expression": "* * * * *"},
        ),
    ]
    for method, path, body in endpoints:
        if body:
            r = getattr(client, method)(path, json=body)
        else:
            r = getattr(client, method)(path)
        assert r.status_code == 401, (
            f"{method.upper()} {path} should require auth, got {r.status_code}"
        )
