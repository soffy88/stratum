"""Tests for stratum.middleware.corpus_isolation — ≥10 tests per §4.6."""
import time
import pytest
import jwt as pyjwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from stratum.middleware.corpus_isolation import corpus_isolation_middleware
from stratum.auth.jwt_handler import encode_access, SECRET_KEY, ALGORITHM


@pytest.fixture
def app_with_middleware():
    app = FastAPI()

    @app.middleware("http")
    async def mw(request: Request, call_next):
        return await corpus_isolation_middleware(request, call_next)

    @app.exception_handler(Exception)
    async def catch_all(request, exc):
        from fastapi.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.get("/api/data")
    async def get_data(request: Request):
        return {"corpus_id": request.state.corpus_id, "user_id": request.state.user_id}

    @app.get("/api/auth/login")
    async def auth_login():
        return {"ok": True}

    @app.get("/share/abc")
    async def share():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/openapi.json")
    async def openapi():
        return {"paths": {}}

    return TestClient(app, raise_server_exceptions=False)


def test_api_route_requires_auth(app_with_middleware):
    r = app_with_middleware.get("/api/data")
    assert r.status_code == 401


def test_api_route_with_valid_token(app_with_middleware):
    token = encode_access("u1", "corpus_u1")
    r = app_with_middleware.get("/api/data", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["corpus_id"] == "corpus_u1"
    assert r.json()["user_id"] == "u1"


def test_auth_path_exempt(app_with_middleware):
    r = app_with_middleware.get("/api/auth/login")
    assert r.status_code == 200


def test_share_path_exempt(app_with_middleware):
    r = app_with_middleware.get("/share/abc")
    assert r.status_code == 200


def test_health_path_exempt(app_with_middleware):
    r = app_with_middleware.get("/health")
    assert r.status_code == 200


def test_openapi_path_exempt(app_with_middleware):
    r = app_with_middleware.get("/openapi.json")
    assert r.status_code == 200


def test_invalid_token_returns_401(app_with_middleware):
    r = app_with_middleware.get("/api/data", headers={"Authorization": "Bearer bad.token"})
    assert r.status_code == 401


def test_missing_bearer_prefix_returns_401(app_with_middleware):
    token = encode_access("u1", "c1")
    r = app_with_middleware.get("/api/data", headers={"Authorization": f"Token {token}"})
    assert r.status_code == 401


def test_corpus_id_from_token_not_query(app_with_middleware):
    """Middleware injects corpus_id from JWT, ignoring any query param."""
    token = encode_access("u1", "corpus_u1")
    r = app_with_middleware.get("/api/data?corpus_id=hacked", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["corpus_id"] == "corpus_u1"


def test_expired_token_returns_401(app_with_middleware):
    payload = {"sub": "u1", "corpus_id": "c1", "exp": int(time.time()) - 100, "iat": int(time.time()) - 200}
    token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    r = app_with_middleware.get("/api/data", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
