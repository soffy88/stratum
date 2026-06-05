"""Tests for POST /api/v1/inbox/web-clip — server-side URL fetch + SSRF guard.

SSRF protection is now delegated to oprim.url_fetch_ssrf_safe (DNS-pinned transport).
Tests verify that _fetch_url_html correctly maps oprim results to HTTP exceptions.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from stratum.api.routers.inbox import router, _fetch_url_html


# ── Test client fixture ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    from stratum.common import jwt_auth

    app.dependency_overrides[jwt_auth] = lambda: "test-user-id"
    return TestClient(app, raise_server_exceptions=False)


# ── _fetch_url_html unit tests ────────────────────────────────────────────────


def _ssrf_result(**kwargs):
    base = {
        "url": "https://example.com",
        "status_code": 200,
        "content_type": "text/html",
        "body_bytes": b"",
        "body_text": None,
        "error": None,
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_fetch_url_html_success():
    ok_result = _ssrf_result(body_text="<html><body>Hello</body></html>")
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=ok_result),
    ):
        result = await _fetch_url_html("https://example.com")
    assert "Hello" in result


@pytest.mark.asyncio
async def test_fetch_url_html_ssrf_blocked():
    blocked = _ssrf_result(error="ssrf_blocked", body_bytes=b"", body_text=None, status_code=None)
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=blocked),
    ):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("http://192.168.1.1/")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_fetch_url_html_404():
    not_found = _ssrf_result(status_code=404, body_text=None)
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=not_found),
    ):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("https://example.com/missing")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_url_html_timeout():
    timeout = _ssrf_result(error="<urlopen error timed out>", body_bytes=b"", status_code=None)
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=timeout),
    ):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("https://slow.example.com")
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_fetch_url_html_generic_error():
    err = _ssrf_result(error="connection refused", body_bytes=b"", status_code=None)
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=err),
    ):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("https://example.com")
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_url_html_empty_body():
    empty = _ssrf_result(body_text="", status_code=200)
    with (
        patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", True),
        patch("stratum.api.routers.inbox._url_fetch_ssrf_safe", return_value=empty),
    ):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("https://example.com")
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_fetch_url_html_no_oprim():
    with patch("stratum.api.routers.inbox._HAS_SSRF_SAFE", False):
        with pytest.raises(HTTPException) as exc:
            await _fetch_url_html("https://example.com")
    assert exc.value.status_code == 503


# ── web-clip endpoint integration tests ──────────────────────────────────────


def _mock_process_result(substrate_id="01ARZ3NDEKTSV4RRFFQ69G5FAV"):
    findings = MagicMock()
    findings.substrate_id = substrate_id
    return {"status": "completed", "findings": findings}


def test_webclip_with_html_provided(client):
    """When html is provided, no URL fetch should happen."""
    fake_result = _mock_process_result()
    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox.process_inbox_substrate", return_value=fake_result),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
        patch("pathlib.Path.write_text"),
        patch("pathlib.Path.read_text", return_value="<html></html>"),
        patch("stratum.api.routers.inbox.sha256_hex", return_value="abc123"),
        patch("stratum.api.routers.inbox.generate_ulid", return_value="01ARZ3NDEKTSV4RRFFQ69G5FAV"),
    ):
        r = client.post(
            "/api/v1/inbox/web-clip",
            data={"url": "https://example.com", "html": "<html><body>Test</body></html>"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["url"] == "https://example.com"


def test_webclip_url_only_fetches_server_side(client):
    """When no html provided, server fetches the URL."""
    fake_result = _mock_process_result()
    mock_fetch = AsyncMock(return_value="<html><body>Fetched</body></html>")

    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox._fetch_url_html", mock_fetch),
        patch("stratum.api.routers.inbox.process_inbox_substrate", return_value=fake_result),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
        patch("pathlib.Path.write_text"),
        patch("pathlib.Path.read_text", return_value="<html></html>"),
        patch("stratum.api.routers.inbox.sha256_hex", return_value="abc123"),
        patch("stratum.api.routers.inbox.generate_ulid", return_value="01ARZ3NDEKTSV4RRFFQ69G5FAV"),
    ):
        r = client.post("/api/v1/inbox/web-clip", data={"url": "https://example.com"})
    assert r.status_code == 200
    mock_fetch.assert_awaited_once_with("https://example.com")


def test_webclip_url_timeout_returns_504(client):
    mock_fetch = AsyncMock(side_effect=HTTPException(504, "Timeout"))
    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox._fetch_url_html", mock_fetch),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post("/api/v1/inbox/web-clip", data={"url": "https://slow.example.com"})
    assert r.status_code == 504


def test_webclip_url_404_returns_404(client):
    mock_fetch = AsyncMock(side_effect=HTTPException(404, "Not found"))
    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox._fetch_url_html", mock_fetch),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post("/api/v1/inbox/web-clip", data={"url": "https://example.com/missing"})
    assert r.status_code == 404


def test_webclip_not_implemented_when_no_omodul(client):
    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", False),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post("/api/v1/inbox/web-clip", data={"url": "https://example.com"})
    assert r.status_code == 200
    assert r.json()["status"] == "not_implemented"
