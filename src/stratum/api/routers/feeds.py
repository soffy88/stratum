"""RSS feed subscription management (Phase 17.7).

Supports:
  POST   /api/v1/feeds              — subscribe to a feed
  GET    /api/v1/feeds              — list user's subscriptions
  DELETE /api/v1/feeds/{id}         — unsubscribe
  PUT    /api/v1/feeds/{id}         — update frequency / status
  POST   /api/v1/feeds/{id}/check   — immediate fetch + ingest new entries
  GET    /api/v1/feeds/discover     — auto-detect RSS URL from a homepage

FeedTrackerAgent scheduler (hourly auto-check) is blocked on omodul ship.
Track: omodul FeedTrackerAgent + builtin_jobs wiring (Phase 17.7 R-3).
"""

import asyncio
import html as html_lib
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query, read, update

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feeds", tags=["feeds"])

# ── oprim imports ──────────────────────────────────────────────────────────────

try:
    from oprim import detect_feed_url, fetch_rss_feed

    _HAS_OPRIM_FEEDS = True
except ImportError:
    _HAS_OPRIM_FEEDS = False

try:
    from omodul.process_inbox_substrate import InboxConfig, InboxInput, process_inbox_substrate
    from stratum.common import sha256_hex, user_inbox_dir, ensure_dir
    from stratum.utils.user_id_hash import hash_user_id

    _HAS_INBOX = True
except ImportError:
    _HAS_INBOX = False


# ── Schemas ────────────────────────────────────────────────────────────────────


class FeedSubscribeRequest(BaseModel):
    url: str
    frequency_hours: int = 6


class FeedUpdateRequest(BaseModel):
    frequency_hours: int | None = None
    status: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _validate_feed_url(url: str) -> None:
    """SSRF guard: reject non-public URLs before any network call."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "URL must use http or https scheme")
    host = parsed.hostname
    if not host:
        raise HTTPException(400, "Invalid URL")
    try:
        addrs = socket.getaddrinfo(host.lower().rstrip("."), None)
    except socket.gaierror:
        raise HTTPException(400, "Cannot resolve URL hostname")
    for *_, sockaddr in addrs:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(403, "URL resolves to a disallowed address")


async def _fetch_page_html(url: str) -> str:
    """Fetch page HTML for feed discovery. Validates URL before fetching."""
    import httpx

    _validate_feed_url(url)
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,  # no redirects — avoids SSRF bypass
            headers={"User-Agent": "StratumBot/1.0"},
        ) as client:
            resp = await client.get(url)
            # Accept successful responses only; ignore redirects (SSRF guard)
            if resp.status_code in (301, 302, 307, 308):
                raise HTTPException(400, "URL redirects are not followed; use the final URL")
            resp.raise_for_status()
            return resp.text
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(504, "Page fetch timed out")
    except Exception:
        log.warning("feed_page_fetch_error url=%s", url, exc_info=True)
        raise HTTPException(502, "Failed to fetch page")


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/discover")
async def discover_feed(
    url: str = Query(..., description="Homepage or feed URL to inspect"),
    user_id: str = Depends(jwt_auth),
):
    """Auto-detect RSS/Atom feed URL(s) from a given page."""
    if not _HAS_OPRIM_FEEDS:
        raise HTTPException(501, "oprim feed functions not available")

    html = await _fetch_page_html(url)
    result = await asyncio.to_thread(detect_feed_url, html=html, base_url=url)
    feeds = result.get("feeds", [])
    return {"url": url, "feeds": feeds}


@router.post("")
async def subscribe_feed(req: FeedSubscribeRequest, user_id: str = Depends(jwt_auth)):
    """Subscribe to an RSS/Atom feed. Validates the feed before saving."""
    if not _HAS_OPRIM_FEEDS:
        raise HTTPException(501, "oprim feed functions not available")

    if req.frequency_hours < 1 or req.frequency_hours > 168:
        raise HTTPException(400, "frequency_hours must be between 1 and 168")

    # SSRF guard before any network call
    _validate_feed_url(req.url)

    # Validate feed is fetchable
    try:
        feed_data = await asyncio.to_thread(fetch_rss_feed, url=req.url, max_items=5)
    except Exception as exc:
        log.warning("feed_validate_error url=%s error=%s", req.url, exc)
        raise HTTPException(400, "Cannot fetch feed")

    if not feed_data.get("items"):
        raise HTTPException(422, "No feed items found — is this a valid RSS/Atom URL?")

    feed_title = feed_data.get("title") or req.url
    feed_description = feed_data.get("description") or ""
    entry_count = len(feed_data.get("items", []))

    sub_id = generate_ulid()
    ts = now_utc()
    try:
        insert(
            "feed_subscriptions",
            {
                "id": sub_id,
                "user_id": user_id,
                "feed_url": req.url,
                "feed_title": feed_title,
                "feed_description": feed_description,
                "frequency_hours": req.frequency_hours,
                "last_check_at": ts,
                "last_entries_count": entry_count,
                "status": "active",
                "created_at": ts,
                "updated_at": ts,
            },
        )
    except Exception as exc:
        err = str(exc)
        if "UNIQUE" in err.upper() or "duplicate" in err.lower():
            raise HTTPException(409, "Already subscribed to this feed")
        raise HTTPException(500, "Failed to save subscription")

    return {
        "id": sub_id,
        "feed_url": req.url,
        "feed_title": feed_title,
        "frequency_hours": req.frequency_hours,
        "last_entries_count": entry_count,
        "status": "active",
        "created_at": ts,
    }


@router.get("")
async def list_feeds(user_id: str = Depends(jwt_auth)):
    """List all feed subscriptions for the current user."""
    rows = query(
        "SELECT * FROM feed_subscriptions WHERE user_id = %(user_id)s ORDER BY created_at DESC",
        {"user_id": user_id},
    )
    return {"items": rows}


@router.delete("/{feed_id}")
async def unsubscribe_feed(feed_id: str, user_id: str = Depends(jwt_auth)):
    """Unsubscribe from a feed."""
    row = read("feed_subscriptions", feed_id)
    if not row or row.get("user_id") != user_id:
        raise HTTPException(404, "Feed subscription not found")
    update("feed_subscriptions", feed_id, {"status": "deleted", "updated_at": now_utc()})
    return {"status": "deleted"}


@router.put("/{feed_id}")
async def update_feed(feed_id: str, req: FeedUpdateRequest, user_id: str = Depends(jwt_auth)):
    """Update feed frequency or pause/resume."""
    row = read("feed_subscriptions", feed_id)
    if not row or row.get("user_id") != user_id:
        raise HTTPException(404, "Feed subscription not found")

    changes: dict = {"updated_at": now_utc()}
    if req.frequency_hours is not None:
        if req.frequency_hours < 1 or req.frequency_hours > 168:
            raise HTTPException(400, "frequency_hours must be 1–168")
        changes["frequency_hours"] = req.frequency_hours
    if req.status is not None:
        if req.status not in ("active", "paused"):
            raise HTTPException(400, "status must be 'active' or 'paused'")
        changes["status"] = req.status

    update("feed_subscriptions", feed_id, changes)
    return {**row, **changes}


@router.post("/{feed_id}/check")
async def check_feed_now(feed_id: str, user_id: str = Depends(jwt_auth)):
    """Immediately fetch feed and ingest new articles."""
    if not _HAS_OPRIM_FEEDS:
        raise HTTPException(501, "oprim feed functions not available")

    row = read("feed_subscriptions", feed_id)
    if not row or row.get("user_id") != user_id:
        raise HTTPException(404, "Feed subscription not found")
    if row.get("status") == "deleted":
        raise HTTPException(410, "Feed subscription is deleted")

    feed_url: str = row["feed_url"]

    # Re-validate stored URL (defense-in-depth; URL was validated on subscribe)
    _validate_feed_url(feed_url)

    try:
        feed_data = await asyncio.to_thread(fetch_rss_feed, url=feed_url)
    except Exception as exc:
        log.warning("feed_check_error feed_id=%s error=%s", feed_id, exc)
        update(
            "feed_subscriptions",
            feed_id,
            {"status": "error", "error_message": "fetch_failed", "updated_at": now_utc()},
        )
        raise HTTPException(502, "Cannot fetch feed")

    new_items = feed_data.get("items", [])
    ingested = 0

    if _HAS_INBOX:
        inbox_dir = ensure_dir(user_inbox_dir(user_id))
        for item in new_items[:20]:  # cap at 20 per manual check
            item_url = item.get("link") or item.get("url")
            if not item_url:
                continue
            try:
                import hashlib
                import re

                # Strip all HTML tags from title and content — store as plain text
                # to prevent feed-origin script injection reaching the substrate renderer
                raw_title = html_lib.unescape(item.get("title") or "")
                safe_title = html_lib.escape(re.sub(r"<[^>]+>", " ", raw_title).strip())
                raw_content = item.get("content") or item.get("summary") or ""
                safe_content = html_lib.escape(re.sub(r"<[^>]+>", " ", raw_content))

                item_id = hashlib.sha256(item_url.encode()).hexdigest()[:12]
                html_path = inbox_dir / f"feed_{item_id}.html"
                html_path.write_text(
                    f"<html><head><title>{safe_title}</title></head>"
                    f"<body><pre>{safe_content}</pre></body></html>",
                    encoding="utf-8",
                )
                checksum = sha256_hex(html_path.read_text())
                config = InboxConfig(
                    file_path=str(html_path),
                    file_checksum=checksum,
                    user_id_hash=hash_user_id(user_id),
                    medium_hint="webpage",
                    auto_classify=True,
                    llm_provider="qwen3",
                    llm_model="qwen3-max",
                )
                await asyncio.to_thread(
                    process_inbox_substrate,
                    config=config,
                    input_data=InboxInput(),
                    output_dir=inbox_dir,
                )
                ingested += 1
            except Exception as exc:
                log.warning("feed_item_ingest_error url=%s error=%s", item_url, exc)

    ts = now_utc()
    update(
        "feed_subscriptions",
        feed_id,
        {
            "last_check_at": ts,
            "last_entries_count": len(new_items),
            "status": "active",
            "error_message": None,
            "updated_at": ts,
        },
    )

    return {
        "feed_id": feed_id,
        "feed_url": feed_url,
        "new_items_found": len(new_items),
        "ingested": ingested,
        "checked_at": ts,
    }
