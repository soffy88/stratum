"""OAPEN open-access book search — Stratum-layer implementation.

Proxies through host-side service at 172.19.0.1:8766/oapen-search,
because library.oapen.org (103.200.31.172) is unreachable from the container
network (TCP timeout), while the host can reach it fine.

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

log = logging.getLogger(__name__)

_PROXY_URL = "http://172.19.0.1:8766/oapen-search"


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

    url = _PROXY_URL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as exc:
        log.warning("oapen_direct: proxy request failed: %s", exc)
        return []

    results = []
    for r in data.get("results", []):
        results.append(SourceResult(
            external_id=r["external_id"],
            title=r["title"],
            download_url=r["download_url"],
            file_type="pdf",
            metadata=r.get("metadata", {}),
        ))

    log.info("oapen_direct: query=%r → %d results", query, len(results))
    return results
