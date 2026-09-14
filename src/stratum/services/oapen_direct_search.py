"""OAPEN open-access book search — Stratum-layer implementation.

Optionally proxies through a configured OAPEN service when direct access is
unavailable.

Root cause of oprim._oapen_search failure:
  1. library.oapen.org unreachable from container (routing, not DNS)
  2. Even if reachable: _TRUSTED_PDF_HOSTS = ("link.springer.com",) drops
     99% of books whose PDFs are hosted on library.oapen.org itself.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from stratum.config import OAPEN_PROXY_URL

log = logging.getLogger(__name__)

_PROXY_URL = OAPEN_PROXY_URL


def oapen_direct_search(
    *,
    query: str,
    language: str | None = None,
    max_results: int = 10,
    rate_limit_sleep: float = 2.0,
) -> list:
    """Search OAPEN via host proxy. Returns list[SourceResult]."""
    import time
    from oprim._media_types import SourceResult

    if rate_limit_sleep > 0:
        time.sleep(rate_limit_sleep)

    params: dict[str, str] = {"query": query, "max_results": str(max_results)}
    if language:
        params["language"] = language

    if not _PROXY_URL:
        log.warning("OAPEN proxy is not configured")
        return []
    url = _PROXY_URL + "/oapen-search?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as exc:
        log.warning("oapen_direct: proxy request failed: %s", exc)
        return []

    results = []
    for r in data.get("results", []):
        results.append(
            SourceResult(
                external_id=r["external_id"],
                title=r["title"],
                download_url=r["download_url"],
                file_type="pdf",
                metadata=r.get("metadata", {}),
            )
        )

    log.info("oapen_direct: query=%r → %d results", query, len(results))
    return results
