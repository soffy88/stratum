"""Tests for POST /api/v1/inbox/web-clip — server-side URL fetch."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stratum.api.routers.inbox import router, _fetch_url_html


# ── Test client fixture ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)

    from stratum.api.routers.inbox import router as inbox_router
    from stratum.common import jwt_auth

    app.dependency_overrides[jwt_auth] = lambda: "test-user-id"
    return TestClient(app, raise_server_exceptions=False)


# ── _fetch_url_html unit tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_url_html_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"<html><body>Hello</body></html>"
    mock_resp.text = "<html><body>Hello</body></html>"
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_url_html("https://example.com")
    assert result == "<html><body>Hello</body></html>"


@pytest.mark.asyncio
async def test_fetch_url_html_404():
    import httpx
    from fastapi import HTTPException

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.content = b""
    mock_resp.text = ""
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://example.com/missing")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_url_html_timeout():
    import httpx
    from fastapi import HTTPException

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await _fetch_url_html("https://slow.example.com")
    assert exc_info.value.status_code == 504


@pytest.mark.asyncio
async def test_fetch_url_html_too_large():
    from fastapi import HTTPException

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"x" * (11 * 1024 * 1024)  # 11 MB
    mock_resp.text = "x" * (11 * 1024 * 1024)
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("stratum.api.routers.inbox.httpx.AsyncClient", return_value=mock_client):
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
        patch("builtins.open", MagicMock()),
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
        r = client.post(
            "/api/v1/inbox/web-clip",
            data={"url": "https://example.com"},
        )
    assert r.status_code == 200
    mock_fetch.assert_awaited_once_with("https://example.com")


def test_webclip_url_timeout_returns_504(client):
    """URL fetch timeout → 504."""
    from fastapi import HTTPException

    mock_fetch = AsyncMock(side_effect=HTTPException(504, "Timeout"))

    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox._fetch_url_html", mock_fetch),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post(
            "/api/v1/inbox/web-clip",
            data={"url": "https://slow.example.com"},
        )
    assert r.status_code == 504


def test_webclip_url_404_returns_404(client):
    """URL fetch 404 → 404."""
    from fastapi import HTTPException

    mock_fetch = AsyncMock(side_effect=HTTPException(404, "Not found"))

    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", True),
        patch("stratum.api.routers.inbox._fetch_url_html", mock_fetch),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post(
            "/api/v1/inbox/web-clip",
            data={"url": "https://example.com/missing"},
        )
    assert r.status_code == 404


def test_webclip_not_implemented_when_no_omodul(client):
    """Returns not_implemented when _HAS_INBOX is False."""
    with (
        patch("stratum.api.routers.inbox._HAS_INBOX", False),
        patch("stratum.api.routers.inbox.ensure_dir"),
        patch("stratum.api.routers.inbox.user_inbox_dir", return_value="/tmp"),
    ):
        r = client.post(
            "/api/v1/inbox/web-clip",
            data={"url": "https://example.com"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "not_implemented"
