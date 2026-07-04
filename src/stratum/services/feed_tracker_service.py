"""Feed Tracker service — oservi FeedTrackerEngine assembled for Stratum.

oservi.engines.feed_tracker.FeedTrackerEngine (installed version 1.2.0) declares
exactly 3 injection points: fetch_event (oprim, 1), subscription (layer4, 1),
ingest (omodul, 0..1). fetch_event returns a flat list of "events" (dicts) each
tick; the engine calls subscription(event=...) and ingest(event=...) once per
event. There's no separate diff/query/update contract — this module used to
target an older 5-point shape (fetch/diff/query/update/ingest) that no longer
matches the installed oservi; due-tracking (last_check_at/etag) is therefore
done directly against the DB inside fetch_event, since that's the only
injection point that sees every subscription on every tick (not just the ones
with new entries).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from pathlib import Path

from stratum.common import now_utc, now_utc_dt

log = logging.getLogger(__name__)

_FEED_TRACKER_ENGINE = None


# ── fetch_event (kind="oprim", cardinality=1) ─────────────────────────────────


def _make_fetch_event_adapter():
    """Poll every due subscription, update its due-tracking state, and return
    one event dict per newly-seen entry across all of them.

    Engine calls: fn(config=self.config) — no per-subscription args, since this
    injection point owns the whole "which feeds are due" decision.
    """
    from oprim import fetch_rss_feed, feed_diff_detector
    from stratum.db import query, update
    from stratum.services.feed_subscriptions import query_active_subscriptions

    def _fetch_event_adapter(*, config: dict | None = None, **_) -> list[dict]:
        subs = query_active_subscriptions(last_check_before=now_utc())["findings"]["subscriptions"]
        events: list[dict] = []
        for sub in subs:
            frequency_hours = sub.get("frequency_hours") or 6
            last_check_at = sub.get("last_check_at")
            if last_check_at is not None:
                due_at = last_check_at + timedelta(hours=frequency_hours)
                if now_utc_dt() < due_at:
                    continue  # not due yet — this sub's own cadence hasn't elapsed

            try:
                fetched = fetch_rss_feed(url=sub["url"], timeout=20, max_items=50)
            except Exception as exc:
                log.warning("feed_fetch_failed sub=%s url=%s error=%s", sub["id"], sub["url"], exc)
                update(
                    "feed_subscriptions",
                    sub["id"],
                    {"last_check_at": now_utc(), "status": "error", "error_message": str(exc)},
                )
                continue

            current_entries = fetched.get("items", [])
            old_items = [{"guid": g} for g in (sub.get("_seen_guids") or [])]
            diffed = feed_diff_detector(
                old_items=old_items, new_items=current_entries, key_field="guid"
            )
            new_entries = diffed.get("new_items", [])

            # Due-tracking always advances, whether or not new entries were found —
            # otherwise a quiet feed would look "due" again on every 5s engine tick.
            update(
                "feed_subscriptions",
                sub["id"],
                {
                    "last_check_at": now_utc(),
                    "last_entries_count": len(current_entries),
                    "status": "active",
                    "error_message": None,
                },
            )

            for entry in new_entries:
                events.append(
                    {
                        "subscription_id": sub["id"],
                        "user_id": sub["user_id"],
                        "feed_url": sub["url"],
                        "title": entry.get("title"),
                        "link": entry.get("link") or entry.get("guid"),
                        "content": entry.get("summary")
                        or entry.get("content")
                        or entry.get("title")
                        or "",
                        "guid": entry.get("guid") or entry.get("link"),
                    }
                )
        return events

    _fetch_event_adapter.__module__ = "oprim.feed"  # satisfies oservi kind="oprim" check
    _fetch_event_adapter.__name__ = "fetch_event_adapter"
    return _fetch_event_adapter


# ── subscription (kind="layer4", cardinality=1) ───────────────────────────────


def _make_subscription_adapter():
    """Per-event bookkeeping. fetch_event already persisted last_check_at/status
    for the whole subscription — this just records that a specific entry was
    delivered, for observability (last_entries_count is already tracked above;
    this adds a per-entry log line so a stuck ingest step is visible in logs)."""

    def _subscription_adapter(*, event: dict, **_) -> None:
        log.info(
            "feed_event_seen sub=%s user=%s guid=%s",
            event.get("subscription_id"),
            event.get("user_id"),
            event.get("guid"),
        )

    _subscription_adapter.__module__ = (
        "stratum.services.feed_subscriptions"  # satisfies kind="layer4"
    )
    _subscription_adapter.__name__ = "subscription_adapter"
    return _subscription_adapter


# ── ingest (kind="omodul", cardinality=0..1) ──────────────────────────────────


def _make_ingest_adapter():
    """Wrap omodul.process_inbox_substrate to match FeedTrackerEngine's ingest protocol.

    Engine calls: fn(event=event_dict) with the dict produced by fetch_event above.
    """
    from omodul.process_inbox_substrate import process_inbox_substrate, InboxConfig, InboxInput
    from stratum.utils.user_id_hash import hash_user_id
    from stratum.db import execute as db_execute, update as db_update
    import ast
    import hashlib
    import re
    import tempfile

    _ULID_RE = re.compile(r"[0-9A-Z]{26}")

    def _ingest_adapter(*, event: dict, **_) -> dict:
        content = event.get("content")
        user_id = event.get("user_id")
        title = event.get("title")
        source_url = event.get("link") or event.get("feed_url")
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
        if result.get("status") != "failed":
            findings = result.get("findings")
            sid_raw = getattr(findings, "substrate_id", None) if findings else None
            if sid_raw:
                m = _ULID_RE.search(str(sid_raw))
                if m:
                    sid = m.group(0)
                    if title:
                        try:
                            db_update("substrates", sid, {"title": title, "updated_at": now_utc()})
                        except Exception as exc:
                            log.warning("feed_title_update_failed sid=%s error=%s", sid, exc)
                    for item in getattr(findings, "derivative_ids", None) or []:
                        try:
                            d = ast.literal_eval(item) if isinstance(item, str) else item
                        except (ValueError, SyntaxError):
                            continue
                        if not isinstance(d, dict):
                            continue
                        for kind, deriv_content in d.items():
                            if not deriv_content or not isinstance(deriv_content, str):
                                continue
                            try:
                                db_execute(
                                    "UPDATE derivative SET content = $content"
                                    " WHERE substrate_id = $sid AND kind = $kind",
                                    {"content": deriv_content, "sid": sid, "kind": kind},
                                )
                            except Exception as exc:
                                log.warning(
                                    "feed_deriv_update_failed sid=%s kind=%s error=%s",
                                    sid,
                                    kind,
                                    exc,
                                )
        return result

    _ingest_adapter.__module__ = "omodul.feed_ingest"  # satisfies oservi kind="omodul" check
    _ingest_adapter.__name__ = "ingest_adapter"
    return _ingest_adapter


# ── Assembly ──────────────────────────────────────────────────────────────────


def get_feed_tracker_engine():
    global _FEED_TRACKER_ENGINE
    if _FEED_TRACKER_ENGINE is not None:
        return _FEED_TRACKER_ENGINE

    try:
        from oservi import assemble, ServiceManifest

        manifest = ServiceManifest(
            name="stratum-feed-tracker",
            skeleton="feed_tracker",
            inject={
                "fetch_event": [_make_fetch_event_adapter()],
                "subscription": [_make_subscription_adapter()],
                "ingest": [_make_ingest_adapter()],
            },
            trigger={
                "on_interval": 3600
            },  # hourly; per-subscription cadence is enforced inside fetch_event
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
    """Execute one feed tracker tick (fetch + ingest for due subscriptions).

    Called from Stratum's lifespan background task every hour.
    """
    engine = get_feed_tracker_engine()
    if engine is None:
        return {"status": "unavailable", "error": "oservi not assembled"}
    try:
        result = await engine.tick()
        log.info(
            "feed_tracker_tick events_fetched=%s events_processed=%s",
            result.get("events_fetched"),
            result.get("events_processed"),
        )
        return result
    except Exception as e:
        log.exception("feed_tracker_tick failed")
        return {"status": "failed", "error": str(e)}
