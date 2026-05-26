"""Tests for stratum.middleware.rate_limit — ≥10 tests per §5.7."""
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from stratum.middleware.rate_limit import rate_limit_middleware, reset_rate_limits, LIMITS


@pytest.fixture(autouse=True)
def clean_state():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def app():
    _app = FastAPI()

    @_app.middleware("http")
    async def mw(request: Request, call_next):
        return await rate_limit_middleware(request, call_next)

    @_app.exception_handler(Exception)
    async def exc_handler(request, exc):
        from fastapi.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @_app.post("/api/auth/register")
    async def register():
        return {"ok": True}

    @_app.post("/api/auth/login")
    async def login():
        return {"ok": True}

    @_app.post("/api/auth/refresh")
    async def refresh():
        return {"ok": True}

    @_app.get("/api/data")
    async def data():
        return {"ok": True}

    @_app.get("/health")
    async def health():
        return {"ok": True}

    return TestClient(_app, raise_server_exceptions=False)


def test_register_allows_under_limit(app):
    for _ in range(3):
        r = app.post("/api/auth/register")
        assert r.status_code == 200


def test_register_blocks_over_limit(app):
    for _ in range(3):
        app.post("/api/auth/register")
    r = app.post("/api/auth/register")
    assert r.status_code == 429


def test_login_allows_under_limit(app):
    for _ in range(10):
        r = app.post("/api/auth/login")
        assert r.status_code == 200


def test_login_blocks_over_limit(app):
    for _ in range(10):
        app.post("/api/auth/login")
    r = app.post("/api/auth/login")
    assert r.status_code == 429


def test_api_default_allows_under_limit(app):
    for _ in range(60):
        r = app.get("/api/data")
        assert r.status_code == 200


def test_api_default_blocks_over_limit(app):
    for _ in range(60):
        app.get("/api/data")
    r = app.get("/api/data")
    assert r.status_code == 429


def test_health_not_rate_limited(app):
    for _ in range(100):
        r = app.get("/health")
        assert r.status_code == 200


def test_429_response_has_detail(app):
    for _ in range(3):
        app.post("/api/auth/register")
    r = app.post("/api/auth/register")
    assert r.json()["detail"] == "Rate limit exceeded"


def test_different_ips_independent(app):
    """Different X-Real-IP headers get independent limits."""
    for _ in range(3):
        app.post("/api/auth/register", headers={"X-Real-IP": "1.1.1.1"})
    # IP 1 blocked
    r = app.post("/api/auth/register", headers={"X-Real-IP": "1.1.1.1"})
    assert r.status_code == 429
    # IP 2 still allowed
    r = app.post("/api/auth/register", headers={"X-Real-IP": "2.2.2.2"})
    assert r.status_code == 200


def test_refresh_limit_separate_from_login(app):
    """Refresh has its own counter (30/hour), not shared with login."""
    for _ in range(10):
        app.post("/api/auth/login")
    # Login exhausted
    assert app.post("/api/auth/login").status_code == 429
    # Refresh still works
    assert app.post("/api/auth/refresh").status_code == 200
