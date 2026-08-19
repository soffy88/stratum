"""stratum.services.web_fetch — SSRF-safe URL fetch with outbound-proxy fallback.

Why not oprim.url_fetch_ssrf_safe directly: stratum-sl runs with HTTP(S)_PROXY
pointing at the outbound relay (deploy/docker-compose.yml). urllib.request's
default ProxyHandler then routes every request through the relay, and obase's
DNS-pinned transport rejects the relay address as private
(SSRFBlockedError for e.g. 172.19.0.1), so all web fetches fail.

Strategy: try direct first (env proxies stripped via an empty ProxyHandler,
DNS pinned by obase). On failure, and when STRATUM_OUTBOUND_PROXY is set,
retry through that HTTP proxy. The proxy path resolves DNS remotely and
cannot DNS-pin, so only public FQDNs are accepted there (no IP literals,
no localhost / *.local / *.internal / *.lan).

Keeps oprim's result shape: {url, status_code, content_type, body_bytes,
body_text, error}.
"""
from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

_DEFAULT_OUTBOUND_PROXY = "http://172.19.0.1:10808"  # deploy/docker-compose.yml relay
_NON_PUBLIC_TLDS = (".local", ".internal", ".lan", ".home.arpa", ".localdomain")
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _is_public_url(url: str) -> bool:
    """Reject IP literals and obviously non-public hostnames (proxy-path guard)."""
    import ipaddress

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        return False
    if hostname == "localhost":
        return False
    try:
        ipaddress.ip_address(hostname)
        return False  # IP literal — proxy path has no DNS pinning
    except ValueError:
        pass
    if hostname.endswith(_NON_PUBLIC_TLDS):
        return False
    return True


def _perform(opener: urllib.request.OpenerDirector, url: str, timeout: int, max_bytes: int, headers: dict | None) -> dict:
    merged_headers = dict(_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)
    req = urllib.request.Request(url, headers=merged_headers)
    with opener.open(req, timeout=timeout) as resp:
        body = resp.read(max_bytes)
        return {
            "url": url,
            "status_code": resp.status,
            "content_type": resp.headers.get("Content-Type"),
            "body_bytes": body,
            "body_text": body.decode("utf-8", errors="replace"),
            "error": None,
        }


def _direct_fetch(url: str, timeout: int, max_bytes: int, headers: dict | None) -> dict:
    from obase.http.dns_pinned_transport import (
        DNSPinnedHTTPHandler,
        DNSPinnedHTTPSHandler,
        SSRFBlockedError,
    )

    # build_opener installs the env ProxyHandler only if none is passed;
    # an explicit empty ProxyHandler strips HTTP(S)_PROXY so DNS pinning
    # resolves the real hostname instead of the relay address.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        DNSPinnedHTTPHandler,
        DNSPinnedHTTPSHandler,
    )
    try:
        return _perform(opener, url, timeout, max_bytes, headers)
    except SSRFBlockedError:
        return {
            "url": url, "status_code": None, "content_type": None,
            "body_bytes": b"", "body_text": None, "error": "ssrf_blocked",
        }
    except urllib.error.HTTPError as exc:
        return {
            "url": url, "status_code": exc.code, "content_type": None,
            "body_bytes": b"", "body_text": None, "error": str(exc),
        }
    except Exception as exc:
        return {
            "url": url, "status_code": None, "content_type": None,
            "body_bytes": b"", "body_text": None, "error": str(exc),
        }


def _proxy_fetch(proxy: str, url: str, timeout: int, max_bytes: int, headers: dict | None) -> dict:
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )
    try:
        return _perform(opener, url, timeout, max_bytes, headers)
    except urllib.error.HTTPError as exc:
        return {
            "url": url, "status_code": exc.code, "content_type": None,
            "body_bytes": b"", "body_text": None, "error": str(exc),
        }
    except Exception as exc:
        return {
            "url": url, "status_code": None, "content_type": None,
            "body_bytes": b"", "body_text": None, "error": str(exc),
        }


def fetch_url_ssrf_safe(
    *,
    url: str,
    timeout: int = 30,
    max_bytes: int = 10 * 1024 * 1024,
    headers: dict[str, str] | None = None,
) -> dict:
    """Fetch URL content: DNS-pinned direct first, outbound-proxy fallback.

    Drop-in for oprim.url_fetch_ssrf_safe (same kwargs and result shape).
    Returns: {url, status_code, content_type, body_bytes, body_text, error}
    """
    try:
        import obase  # noqa: F401  (capability gate; platform pkg only in image)
    except Exception as exc:
        return {
            "url": url, "status_code": None, "content_type": None,
            "body_bytes": b"", "body_text": None,
            "error": f"ssrf_transport_unavailable: {exc}",
        }

    result = _direct_fetch(url, timeout, max_bytes, headers)
    if result["error"] is None or result["error"] == "ssrf_blocked":
        return result

    proxy = os.environ.get("STRATUM_OUTBOUND_PROXY") or _DEFAULT_OUTBOUND_PROXY
    if proxy and _is_public_url(url):
        log.warning("web_fetch: direct failed url=%s err=%s retry via proxy", url, result["error"])
        result = _proxy_fetch(proxy, url, timeout, max_bytes, headers)
        if result["error"] is None:
            return result

    return result
