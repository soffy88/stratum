"""stratum.services.web_fetch — direct-first, proxy-fallback fetch logic.

Local runs skip the network transport (obase lives in the image); these tests
exercise hostname guards and fallback decision logic with fakes.
"""

import os
import sys
import types
from unittest.mock import patch

import pytest

from stratum.services import web_fetch


def _obase_available():
    return patch.dict("sys.modules", {"obase": types.ModuleType("obase")})


def test_is_public_url_accepts_fqdn():
    assert web_fetch._is_public_url("https://example.com/path?q=1")
    assert web_fetch._is_public_url("http://aiinote.com")


def test_is_public_url_rejects_private():
    assert not web_fetch._is_public_url("https://172.19.0.1:10808/")
    assert not web_fetch._is_public_url("https://10.0.0.5/")
    assert not web_fetch._is_public_url("http://localhost/")
    assert not web_fetch._is_public_url("https://router.local/")
    assert not web_fetch._is_public_url("https://pg.internal/")
    assert not web_fetch._is_public_url("ftp://example.com/")
    assert not web_fetch._is_public_url("not a url")


def test_transport_unavailable_when_no_obase():
    with patch.dict("sys.modules", {"obase": None}):
        result = web_fetch.fetch_url_ssrf_safe(url="https://example.com")
    assert result["error"].startswith("ssrf_transport_unavailable")


def test_direct_success_no_proxy_retry():
    direct_ok = {
        "url": "https://example.com", "status_code": 200, "content_type": "text/html",
        "body_bytes": b"<html>", "body_text": "<html>", "error": None,
    }
    with _obase_available(), patch.object(web_fetch, "_direct_fetch", return_value=direct_ok) as direct:
        with patch.object(web_fetch, "_proxy_fetch") as proxied:
            result = web_fetch.fetch_url_ssrf_safe(url="https://example.com")
    direct.assert_called_once()
    proxied.assert_not_called()
    assert result["error"] is None


def test_direct_failure_retries_via_proxy_for_public_url():
    direct_failed = {
        "url": "https://example.com", "status_code": None, "content_type": None,
        "body_bytes": b"", "body_text": None, "error": "timed out",
    }
    proxy_ok = dict(direct_failed, status_code=200, body_text="ok", error=None)
    with _obase_available():
        with patch.object(web_fetch, "_direct_fetch", return_value=direct_failed) as direct:
            with patch.object(web_fetch, "_proxy_fetch", return_value=proxy_ok) as proxied:
                with patch.dict(os.environ, {"STRATUM_OUTBOUND_PROXY": "http://relay:10808"}):
                    result = web_fetch.fetch_url_ssrf_safe(url="https://example.com")
    direct.assert_called_once()
    proxied.assert_called_once()
    assert result["status_code"] == 200


def test_direct_failure_no_proxy_retry_for_private_url():
    direct_failed = {
        "url": "https://pg.internal/", "status_code": None, "content_type": None,
        "body_bytes": b"", "body_text": None, "error": "timed out",
    }
    with _obase_available():
        with patch.object(web_fetch, "_direct_fetch", return_value=direct_failed) as direct:
            with patch.object(web_fetch, "_proxy_fetch") as proxied:
                with patch.dict(os.environ, {"STRATUM_OUTBOUND_PROXY": "http://relay:10808"}):
                    result = web_fetch.fetch_url_ssrf_safe(url="https://pg.internal/")
    direct.assert_called_once()
    proxied.assert_not_called()
    assert result["error"] == "timed out"


def test_ssrf_blocked_never_forwards_to_proxy():
    direct_blocked = {
        "url": "https://example.com", "status_code": None, "content_type": None,
        "body_bytes": b"", "body_text": None, "error": "ssrf_blocked",
    }
    with _obase_available():
        with patch.object(web_fetch, "_direct_fetch", return_value=direct_blocked) as direct:
            with patch.object(web_fetch, "_proxy_fetch") as proxied:
                result = web_fetch.fetch_url_ssrf_safe(url="https://example.com")
    direct.assert_called_once()
    proxied.assert_not_called()
    assert result["error"] == "ssrf_blocked"
