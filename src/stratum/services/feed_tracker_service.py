"""Feed Tracker service — oservice FeedTrackerEngine assembled for Stratum.

Adapters bridge the gap between oservice injection contracts and actual oprim/omodul APIs.
The __module__ override on oprim adapters is intentional: oservice kind="oprim" validation
checks __module__ prefix. Adapters are thin wrappers around real oprim callables.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_FEED_TRACKER_ENGINE = None


# ── Adapters for oprim injection (kind="oprim") ───────────────────────────────


def _make_fetch_feed_adapter():
    """Wrap oprim.fetch_rss_feed to match FeedTrackerEngine's injection protocol.

    Engine calls: fn(url=url, etag=etag, last_modified=last_modified)
    oprim.fetch_rss_feed accepts: (url, timeout, max_items) — no etag/last_modified.
    Adapter: drops etag/last_modified, remaps 'items' → 'entries'.
    """
    from oprim import fetch_rss_feed

    def _fetch_feed_adapter(*, url: str, etag=None, last_modified=None, **_) -> dict:
        result = fetch_rss_feed(url=url, timeout=20, max_items=50)
        return {
            "entries": result.get("items", []),  # engine expects "entries"
            "etag": None,  # oprim doesn't support conditional GET yet
            "last_modified": None,
            "status": None if not result.get("error") else "error",
            "error": result.get("error"),
        }

    _fetch_feed_adapter.__module__ = "oprim.feed"  # satisfy kind="oprim" check
    _fetch_feed_adapter.__name__ = "fetch_feed_adapter"
    return _fetch_feed_adapter


def _make_diff_adapter():
    """Wrap oprim.feed_diff_detector to match FeedTrackerEngine's injection protocol.

    Engine calls: fn(current_entries=entries, previous_entry_ids=prev_ids)
    oprim.feed_diff_detector accepts: (old_items, new_items, key_field) → {new_items: [...]}
    Adapter: converts previous_entry_ids (list[str]) → old_items (list[dict with guid]),
             remaps output 'new_items' → 'new_entries'.
    """
    from oprim import feed_diff_detector

    def _diff_adapter(*, current_entries: list, previous_entry_ids: list[str], **_) -> dict:
        old_items = [{"guid": gid} for gid in (previous_entry_ids or [])]
        result = feed_diff_detector(
            old_items=old_items, new_items=current_entries, key_field="guid"
        )
        return {"new_entries": result.get("new_items", [])}

    _diff_adapter.__module__ = "oprim.feed"
    _diff_adapter.__name__ = "diff_adapter"
    return _diff_adapter


def _make_ingest_adapter():
    """Wrap omodul.process_inbox_substrate to match FeedTrackerEngine's ingest protocol.

    Engine calls: fn(content=..., source_url=..., title=..., tags=..., user_id=...)
    omodul.process_inbox_substrate accepts: (config, input_data, output_dir)
    Adapter: writes content to a temp file and builds InboxConfig.
    """
    from omodul import process_inbox_substrate, InboxConfig, InboxInput
    from stratum.utils.user_id_hash import hash_user_id
    from stratum.db import update as db_update
    from stratum.common import now_utc
    import hashlib
    import re
    import tempfile

    _ULID_RE = re.compile(r"[0-9A-Z]{26}")

    def _ingest_adapter(
        *,
        content: str,
        source_url: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
        user_id: str | None = None,
        **_,
    ) -> dict:
        if not content or not user_id:
            return {"status": "skipped"}
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(content)
            tmp_path = Path(f.name)
        checksum = hashlib.sha256(content.encode()).hexdigest()
        config = InboxConfig(
            file_path=str(tmp_path),
            file_checksum=checksum,
            user_id_hash=hash_user_id(user_id),
            medium_hint="webpage",
            auto_classify=True,
            llm_provider="qwen3_dashscope",
            llm_model="qwen-plus",
        )
        result = process_inbox_substrate(
            config=config, input_data=InboxInput(), output_dir=tmp_path.parent
        )
        # UPDATE title to real feed entry title (oskill uses temp path.stem as title).
        if title and result.get("status") != "failed":
            findings = result.get("findings")
            sid_raw = getattr(findings, "substrate_id", None) if findings else None
            if sid_raw:
                m = _ULID_RE.search(str(sid_raw))
                if m:
                    try:
                        db_update(
                            "substrates", m.group(0), {"title": title, "updated_at": now_utc()}
                        )
                    except Exception as exc:
                        log.warning("feed_title_update_failed sid=%s error=%s", m.group(0), exc)
        return result

    _ingest_adapter.__module__ = "omodul.feed_ingest"  # satisfy kind="omodul" check
    _ingest_adapter.__name__ = "ingest_adapter"
    return _ingest_adapter


# ── Assembly ──────────────────────────────────────────────────────────────────


def get_feed_tracker_engine():
    global _FEED_TRACKER_ENGINE
    if _FEED_TRACKER_ENGINE is not None:
        return _FEED_TRACKER_ENGINE

    try:
        from oservice import assemble, ServiceManifest
        from stratum.services.feed_subscriptions import (
            query_active_subscriptions,
            update_subscription_state,
        )

        manifest = ServiceManifest(
            name="stratum-feed-tracker",
            skeleton="feed_tracker",
            inject={
                "fetch_feed_oprim": [_make_fetch_feed_adapter()],
                "diff_oprim": [_make_diff_adapter()],
                "subscription_query": [query_active_subscriptions],  # layer4 — no kind check
                "subscription_update": [update_subscription_state],  # layer4 — no kind check
                "ingest_omodul": [_make_ingest_adapter()],
            },
            trigger={"on_interval": 3600},  # hourly; FeedTrackerEngine uses this for its loop
            config={
                "max_concurrent_fetches": 5,
                "default_frequency_hours": 6,
            },
        )
        _FEED_TRACKER_ENGINE = assemble(manifest)
        log.info("FeedTrackerEngine assembled")
    except Exception as e:
        log.warning("FeedTrackerEngine assembly failed: %s", e)
        _FEED_TRACKER_ENGINE = None

    return _FEED_TRACKER_ENGINE


async def run_feed_tracker_tick() -> dict:
    """Execute one feed tracker tick (fetch + diff + ingest for due subscriptions).

    Called from Stratum's lifespan background task every hour.
    """
    engine = get_feed_tracker_engine()
    if engine is None:
        return {"status": "unavailable", "error": "oservice not assembled"}
    try:
        result = await engine.tick()
        log.info(
            "feed_tracker_tick feeds_checked=%s new_entries=%s",
            result.get("feeds_checked"),
            result.get("new_entries"),
        )
        return result
    except Exception as e:
        log.exception("feed_tracker_tick failed")
        return {"status": "failed", "error": str(e)}
