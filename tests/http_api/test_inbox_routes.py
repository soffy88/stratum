"""Tests for POST /api/v1/inbox/web-clip — server-side URL fetch + SSRF guard."""

import socket
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from stratum.api.routers.inbox import router, _fetch_url_html, _validate_fetch_url


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_stream_resp(body: bytes, status: int = 200, encoding: str = "utf-8"):
    """Build an async-context-manager mock for httpx streaming response."""

    async def _aiter_bytes():
        yield body

    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}
    resp.encoding = encoding
    resp.raise_for_status = MagicMock()
    resp.aiter_bytes = _aiter_bytes

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_client_mock(stream_cm):
    client = MagicMock()
    client.stream = MagicMock(return_value=stream_cm)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ── Test client fixture ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    from stratum.common import jwt_auth

    app.dependency_overrides[jwt_auth] = lambda: "test-user-id"
    return TestClient(app, raise_server_exceptions=False)


# ── _validate_fetch_url tests ─────────────────────────────────────────────────


def test_validate_url_rejects_non_http_scheme():
    with pytest.raises(HTTPException) as exc:
        _validate_fetch_url("file:///etc/passwd")
    assert exc.value.status_code == 400


def test_validate_url_rejects_ftp():
    with pytest.raises(HTTPException) as exc:
        _validate_fetch_url("ftp://example.com/file")
    assert exc.value.status_code == 400


def test_validate_url_rejects_loopback():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
        with pytest.raises(HTTPException) as exc:
            _validate_fetch_url("http://localhost/admin")
        assert exc.value.status_code == 403


def test_validate_url_rejects_private_rfc1918():
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.1", 0))]):
        with pytest.raises(HTTPException) as exc:
            _validate_fetch_url("http://internal.corp/secret")
        assert exc.value.status_code == 403


def test_validate_url_rejects_link_local():
    # AWS metadata endpoint
    with patch(
        "socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 0))]
    ):
        with pytest.raises(HTTPException) as exc:
            _validate_fetch_url("http://169.254.169.254/latest/meta-data/")
        assert exc.value.status_code == 403


def test_validate_url_rejects_unresolvable():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("nxdomain")):
        with pytest.raises(HTTPException) as exc:
            _validate_fetch_url("https://does-not-exist.invalid/")
        assert exc.value.status_code == 400


def test_validate_url_passes_public_domain():
    # example.com resolves to a public IP — no exception expected
    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
        _validate_fetch_url("https://example.com/article")  # must not raise


# ── _fetch_url_html unit tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_url_html_success():
    stream_cm = _make_stream_resp(b"<html><body>Hello</body></html>", status=200)
    mock_client = _make_client_mock(stream_cm)

    with (
        patch("stratum.api.routers.inbox._validate_fetch_url"),
        patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await _fetch_url_html("https://example.com")
    assert "Hello" in result


@pytest.mark.asyncio
async def test_fetch_url_html_404():
    stream_cm = _make_stream_resp(b"", status=404)
    mock_client = _make_client_mock(stream_cm)

    with (
        patch("stratum.api.routers.inbox._validate_fetch_url"),
        patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://example.com/missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_url_html_timeout():
    import httpx

    mock_client = MagicMock()
    mock_client.stream = MagicMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("stratum.api.routers.inbox._validate_fetch_url"),
        patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://slow.example.com")
    assert exc_info.value.status_code == 504


@pytest.mark.asyncio
async def test_fetch_url_html_too_large_via_content_length():
    """Content-Length header exceeds limit → 413 before streaming body."""

    async def _aiter_bytes():
        yield b""  # never reached

    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-length": str(11 * 1024 * 1024)}
    resp.encoding = "utf-8"
    resp.raise_for_status = MagicMock()
    resp.aiter_bytes = _aiter_bytes

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_client = _make_client_mock(cm)

    with (
        patch("stratum.api.routers.inbox._validate_fetch_url"),
        patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://huge.example.com")
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_fetch_url_html_too_large_streaming():
    """Chunked body exceeds limit mid-stream → 413."""

    chunk = b"x" * (6 * 1024 * 1024)  # 6 MB × 2 chunks = 12 MB total

    async def _aiter_bytes():
        yield chunk
        yield chunk

    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.encoding = "utf-8"
    resp.raise_for_status = MagicMock()
    resp.aiter_bytes = _aiter_bytes

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_client = _make_client_mock(cm)

    with (
        patch("stratum.api.routers.inbox._validate_fetch_url"),
        patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://huge.example.com")
    assert exc_info.value.status_code == 413


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
