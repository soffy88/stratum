"""Minimal regression tests for the 2026-10-17 security audit fixes (🔴3/🔴4, 🟡7/8/9/13/14/18/22)."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stratum.common import jwt_auth

REPO = Path(__file__).resolve().parents[2]


@contextmanager
def _fake_conn():
    yield MagicMock()


def _client(*routers, user="alice@example.com"):
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    app.dependency_overrides[jwt_auth] = lambda: user
    return TestClient(app)


# ── 🔴3 /api/v1/admin/* needs X-Admin-Secret ────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/v1/admin/bundle-split-batch"),
        ("post", "/api/v1/admin/hash-backfill"),
        ("post", "/api/v1/admin/dedup-by-hash"),
        ("post", "/api/v1/admin/bulk-meta-patch"),
        ("post", "/api/v1/admin/bulk-delete"),
        ("post", "/api/v1/admin/ocr-batch"),
        ("get", "/api/v1/admin/ocr-candidates"),
    ],
)
def test_admin_routes_reject_plain_user(monkeypatch, method, path):
    from stratum.api.routers import bundle_split, scan_ocr

    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    c = _client(bundle_split.router, scan_ocr.router)
    m = method.upper()
    assert c.request(m, path, json={}).status_code == 403
    assert c.request(m, path, json={}, headers={"X-Admin-Secret": "wrong"}).status_code == 403
    monkeypatch.delenv("ADMIN_SECRET")
    assert c.request(m, path, json={}).status_code == 503  # unset → disabled


def test_admin_route_allows_admin_secret(monkeypatch):
    from stratum.api.routers import bundle_split

    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    with patch("stratum.services.bundle_split_service.split_batch", return_value={}):
        r = _client(bundle_split.router).post(
            "/api/v1/admin/bundle-split-batch", headers={"X-Admin-Secret": "s3cret"}
        )
    assert r.status_code == 200


# ── 🔴4 ownership on split / ocr / layers-ku ────────────────────────────────


def test_split_other_users_document_is_404():
    from stratum.api.routers import bundle_split

    with (
        patch.object(bundle_split, "get_conn", _fake_conn),
        patch.object(bundle_split, "_owns_substrate", return_value=False),
        patch("stratum.services.bundle_split_service.split_one") as split_one,
    ):
        r = _client(bundle_split.router).post("/api/v1/documents/sub-bob/split")
    assert r.status_code == 404
    split_one.assert_not_called()


def test_ocr_other_users_document_is_404():
    from stratum.api.routers import scan_ocr

    with (
        patch.object(scan_ocr, "get_conn", _fake_conn),
        patch.object(scan_ocr, "_owns_substrate", return_value=False),
        patch.object(scan_ocr, "_run_ocr_one") as run,
    ):
        r = _client(scan_ocr.router).post("/api/v1/documents/sub-bob/ocr")
    assert r.status_code == 404
    run.assert_not_called()


def test_layers_ku_requires_ownership_of_ku_substrate():
    from stratum.api.routers import layers

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("sub-bob",)

    @contextmanager
    def fake():
        yield conn

    with (
        patch("stratum.db.get_conn", fake),
        patch("stratum.api.routers.quality._owns_substrate", return_value=False),
        patch("stratum.services.layer_generator.get_ku_layers") as get_layers,
    ):
        r = _client(layers.router).get("/api/v1/layers/ku/42")
    assert r.status_code == 404
    get_layers.assert_not_called()


def test_layers_ku_owner_ok():
    from stratum.api.routers import layers

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ("sub-alice",)

    @contextmanager
    def fake():
        yield conn

    with (
        patch("stratum.db.get_conn", fake),
        patch("stratum.api.routers.quality._owns_substrate", return_value=True),
        patch(
            "stratum.services.layer_generator.get_ku_layers",
            return_value={"L0": {"content": "x"}},
        ),
    ):
        r = _client(layers.router).get("/api/v1/layers/ku/42")
    assert r.status_code == 200


# ── 🔴4 agent states isolated per user ──────────────────────────────────────


def test_agent_states_isolated_per_user(tmp_path, monkeypatch):
    from stratum.api.routers import retrieval
    from stratum.services import agent_state

    monkeypatch.setattr(agent_state, "STATES_DIR", tmp_path)
    glob = agent_state.StateManager(tmp_path)
    glob.save_state(agent_state.AgentState(agent_name="graph_builder", last_run=""))
    agent_state.get_user_manager("bob@example.com").save_state(
        agent_state.AgentState(agent_name="mine", last_run="")
    )

    c = _client(retrieval.router, user="alice@example.com")
    prefix, base = "", "/api/v1/agent/states"
    assert c.get(prefix + base).json()["states"] == []
    assert c.get(prefix + base + "/mine").json()["exists"] is False
    assert c.post(prefix + base + "/graph_builder/clear").json()["deleted"] is False
    assert (tmp_path / "graph_builder.json").exists()  # global state untouched
    assert c.get(prefix + base + "/bad%20name").status_code == 422


# ── 🟡7 STRATUM_API_KEY is read-only ────────────────────────────────────────


def test_stratum_key_read_only_in_sl_middleware(monkeypatch):
    from stratum.middleware import rate_limit

    monkeypatch.setenv("AII_API_KEY", "main")
    monkeypatch.setenv("STRATUM_API_KEY", "ro")
    app = FastAPI()
    app.middleware("http")(rate_limit.rate_limit_middleware)

    @app.api_route("/api/aii/api/x", methods=["GET", "POST", "DELETE"])
    async def x():
        return {"ok": True}

    c = TestClient(app)
    path = "/api/aii/api/x"
    if rate_limit._classify_path(path) != "aii":
        path = "/api/x"
        app.router.add_api_route(path, x, methods=["GET", "POST", "DELETE"])
    assert rate_limit._classify_path(path) == "aii"
    assert c.get(path, headers={"X-API-Key": "ro"}).status_code == 200
    assert c.post(path, headers={"X-API-Key": "ro"}).status_code == 403
    assert c.delete(path, headers={"X-API-Key": "ro"}).status_code == 403
    assert c.post(path, headers={"X-API-Key": "main"}).status_code == 200


def test_stratum_key_read_only_in_aii_backend(monkeypatch):
    sys.path.insert(0, str(REPO / "aii" / "aii"))
    auth = pytest.importorskip("aii.api._auth")
    APIKeyMiddleware = auth.APIKeyMiddleware
    monkeypatch.setenv("AII_API_KEY", "main")
    monkeypatch.setenv("STRATUM_API_KEY", "ro")
    app = FastAPI()

    @app.api_route("/api/x", methods=["GET", "POST"])
    async def x():
        return {"ok": True}

    app.add_middleware(APIKeyMiddleware)
    c = TestClient(app)
    assert c.get("/api/x", headers={"X-API-Key": "ro"}).status_code == 200
    assert c.post("/api/x", headers={"X-API-Key": "ro"}).status_code == 403


# ── 🟡8 / 🟡9 per-hop SSRF checks ───────────────────────────────────────────


def _fake_dns(mapping):
    def getaddrinfo(host, *a, **k):
        return [(2, 1, 6, "", (mapping[host], 0))]

    return getaddrinfo


def test_is_public_destination_resolves_dns(monkeypatch):
    from stratum.services import web_fetch

    monkeypatch.setattr(
        "socket.getaddrinfo",
        _fake_dns({"good.example.com": "93.184.216.34", "evil.example.com": "10.0.0.5"}),
    )
    assert web_fetch.is_public_destination("https://good.example.com/a")
    assert not web_fetch.is_public_destination("https://evil.example.com/a")  # rebinding-style name
    assert not web_fetch.is_public_destination("http://169.254.169.254/latest")


def test_proxy_redirect_to_private_is_blocked(monkeypatch):
    import urllib.error

    from stratum.services import web_fetch

    monkeypatch.setattr("socket.getaddrinfo", _fake_dns({"internal.example.com": "192.168.0.168"}))
    h = web_fetch._SSRFSafeRedirectHandler()
    with pytest.raises(urllib.error.URLError, match="ssrf_blocked"):
        h.redirect_request(MagicMock(), None, 302, "Found", {}, "http://internal.example.com/admin")


def test_proxy_fallback_skipped_for_private_resolving_host(monkeypatch):
    from stratum.services import web_fetch

    monkeypatch.setitem(sys.modules, "obase", MagicMock())
    monkeypatch.setenv("STRATUM_OUTBOUND_PROXY", "http://proxy:1")
    monkeypatch.setattr("socket.getaddrinfo", _fake_dns({"evil.example.com": "127.0.0.1"}))
    with (
        patch.object(web_fetch, "_direct_fetch", return_value={"error": "timeout"}),
        patch.object(web_fetch, "_proxy_fetch") as pf,
    ):
        web_fetch.fetch_url_ssrf_safe(url="https://evil.example.com/")
    pf.assert_not_called()


def test_cascade_client_blocks_redirect_hop_to_private(monkeypatch):
    import httpx

    from stratum.services import web_fetch_cascade as wc

    monkeypatch.setattr(
        "socket.getaddrinfo",
        _fake_dns({"pub.example.com": "93.184.216.34", "priv.example.com": "10.1.2.3"}),
    )

    def handler(request):
        if request.url.host == "pub.example.com":
            return httpx.Response(302, headers={"Location": "http://priv.example.com/secret"})
        return httpx.Response(200, text="secret")

    client = wc.make_client(5)
    client._transport = httpx.MockTransport(handler)
    with pytest.raises(wc.SSRFBlockedError):
        client.get("https://pub.example.com/")


# ── 🟡13 folder watch per-user roots ────────────────────────────────────────


def test_watch_path_restricted_to_users_own_subtree(tmp_path, monkeypatch):
    from stratum.services.vault_sync_service import assert_safe_watch_path, user_watch_roots
    from stratum.utils.user_id_hash import hash_user_id

    monkeypatch.setenv("STRATUM_FOLDER_WATCH_ROOTS", str(tmp_path))
    alice = tmp_path / hash_user_id("alice@example.com") / "docs"
    bob = tmp_path / hash_user_id("bob@example.com") / "docs"
    alice.mkdir(parents=True)
    bob.mkdir(parents=True)
    assert user_watch_roots("alice@example.com") == [
        (tmp_path / hash_user_id("alice@example.com")).resolve()
    ]
    assert assert_safe_watch_path(str(alice), user_id="alice@example.com")
    with pytest.raises(ValueError):
        assert_safe_watch_path(str(bob), user_id="alice@example.com")
    with pytest.raises(ValueError):
        assert_safe_watch_path(str(tmp_path), user_id="alice@example.com")


# ── 🟡14 /graph/* requires JWT, DB down → 503 ───────────────────────────────


def test_graph_requires_jwt_and_db_error_is_503():
    from stratum.api.routers import graph

    app = FastAPI()
    app.include_router(graph.router)
    anon = TestClient(app)
    assert anon.get("/graph/explain", params={"concept": "x"}).status_code == 401

    app.dependency_overrides[jwt_auth] = lambda: "alice@example.com"
    with patch.object(graph, "_load_graph", side_effect=RuntimeError("db down")):
        assert TestClient(app).get("/graph/explain", params={"concept": "x"}).status_code == 503


# ── 🟡22 suspended user / revoked sessions ──────────────────────────────────


def _token(sub, iat=None):
    import time

    import jwt

    from stratum import common

    now = int(time.time()) if iat is None else iat
    return jwt.encode(
        {"sub": sub, "iat": now, "exp": now + 3600}, common._jwt_secrets()[0], algorithm="HS256"
    )


def test_verify_token_rejects_suspended_and_revoked(monkeypatch):
    from datetime import datetime, timezone

    from fastapi import HTTPException

    from stratum import common

    monkeypatch.setenv("JWT_SECRET", "test-secret-for-audit")
    monkeypatch.delenv("STRATUM_AUTH_STATUS_CHECK", raising=False)
    common._status_cache.clear()

    def fake_conn_factory(user_row, sess_row):
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [user_row, sess_row]

        @contextmanager
        def fake():
            yield conn

        return fake

    with patch("stratum.db.get_conn", fake_conn_factory(("u1", True, True), None)):
        with pytest.raises(HTTPException) as e:
            common.verify_token(_token("sus@example.com"))
    assert e.value.status_code == 401

    common._status_cache.clear()
    revoked_at = datetime.now(timezone.utc)
    with patch("stratum.db.get_conn", fake_conn_factory(("u2", True, False), (2, 0, revoked_at))):
        with pytest.raises(HTTPException):
            common.verify_token(_token("out@example.com", iat=int(revoked_at.timestamp()) - 60))

    common._status_cache.clear()
    with patch("stratum.db.get_conn", fake_conn_factory(("u3", True, False), (1, 1, None))):
        assert common.verify_token(_token("ok@example.com")) == "ok@example.com"

    common._status_cache.clear()
    with patch("stratum.db.get_conn", fake_conn_factory(None, None)):
        assert common.verify_token(_token("svc-token")) == "svc-token"  # non-user principal


# ── 🟡18 subprocess log fd closed + child reaped ────────────────────────────


def test_pipeline_start_closes_log_fd_and_reaps(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "aii" / "aii"))
    try:
        import asyncpg  # noqa: F401
    except ImportError:  # root venv has no asyncpg; the route under test doesn't use it
        monkeypatch.setitem(sys.modules, "asyncpg", MagicMock())
    pipelines = pytest.importorskip("aii.api.routes.pipelines")
    import asyncio

    cid = next(iter(pipelines.CHANNELS))
    ch = dict(pipelines.CHANNELS[cid], log=tmp_path / "x.log", needs_key=False)
    monkeypatch.setitem(pipelines.CHANNELS, cid, ch)
    monkeypatch.setattr(pipelines, "_running_pids", lambda _cid: [])
    seen = {}

    def fake_popen(*a, **k):
        seen["fh"] = k["stdout"]
        proc = MagicMock()
        proc.wait.side_effect = lambda: seen.setdefault("waited", True)
        return proc

    with patch.object(pipelines.subprocess, "Popen", side_effect=fake_popen):
        asyncio.run(pipelines.start_pipeline(cid))
    import time

    time.sleep(0.1)
    assert seen["fh"].closed
    assert seen.get("waited") is True
