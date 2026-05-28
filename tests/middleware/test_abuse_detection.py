"""Tests for stratum.middleware.abuse_detection — ≥10 tests per §5.7."""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from stratum.middleware.abuse_detection import (
    abuse_detection_middleware, record_auth_event, reset_abuse_state,
    _is_blocked, _blocked_cache, REGISTER_THRESHOLD, LOGIN_FAIL_THRESHOLD,
)


@pytest.fixture(autouse=True)
def clean_state():
    reset_abuse_state()
    yield
    reset_abuse_state()


@pytest.fixture
def app():
    _app = FastAPI()

    @_app.middleware("http")
    async def mw(request: Request, call_next):
        return await abuse_detection_middleware(request, call_next)

    @_app.exception_handler(Exception)
    async def exc_handler(request, exc):
        from fastapi.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @_app.get("/api/data")
    async def data():
        return {"ok": True}

    return TestClient(_app, raise_server_exceptions=False)


def test_normal_request_passes(app):
    r = app.get("/api/data")
    assert r.status_code == 200


def test_blocked_ip_returns_403(app):
    import time
    _blocked_cache["5.5.5.5"] = time.time() + 3600
    r = app.get("/api/data", headers={"X-Real-IP": "5.5.5.5"})
    assert r.status_code == 403


def test_expired_block_allows_request(app):
    import time
    _blocked_cache["7.7.7.7"] = time.time() - 1  # expired
    r = app.get("/api/data", headers={"X-Real-IP": "7.7.7.7"})
    assert r.status_code == 200


def test_register_abuse_triggers_block():
    ip = "10.0.0.1"
    for _ in range(REGISTER_THRESHOLD):
        record_auth_event("register", ip)
    assert _is_blocked(ip)


def test_register_under_threshold_no_block():
    ip = "10.0.0.2"
    for _ in range(REGISTER_THRESHOLD - 1):
        record_auth_event("register", ip)
    assert not _is_blocked(ip)


def test_login_fail_abuse_triggers_block():
    ip = "10.0.0.3"
    for _ in range(LOGIN_FAIL_THRESHOLD):
        record_auth_event("login_failed", ip)
    assert _is_blocked(ip)


def test_login_fail_under_threshold_no_block():
    ip = "10.0.0.4"
    for _ in range(LOGIN_FAIL_THRESHOLD - 1):
        record_auth_event("login_failed", ip)
    assert not _is_blocked(ip)


def test_different_ips_independent():
    ip_a = "10.0.0.5"
    ip_b = "10.0.0.6"
    for _ in range(REGISTER_THRESHOLD):
        record_auth_event("register", ip_a)
    assert _is_blocked(ip_a)
    assert not _is_blocked(ip_b)


def test_blocked_ip_detail_message(app):
    import time
    _blocked_cache["6.6.6.6"] = time.time() + 3600
    r = app.get("/api/data", headers={"X-Real-IP": "6.6.6.6"})
    assert "blocked" in r.json()["detail"].lower()


def test_login_success_does_not_count():
    ip = "10.0.0.7"
    for _ in range(50):
        record_auth_event("login_success", ip)
    assert not _is_blocked(ip)


def test_reset_clears_all_state():
    ip = "10.0.0.8"
    for _ in range(REGISTER_THRESHOLD):
        record_auth_event("register", ip)
    assert _is_blocked(ip)
    reset_abuse_state()
    assert not _is_blocked(ip)
