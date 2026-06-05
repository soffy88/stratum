"""Layer 4 thin wrapper for Stratum feed_subscriptions table.

These functions are injected into oservice FeedTrackerEngine as kind="layer4" callables.
They bridge oservice's abstract interface to Stratum's DuckDB schema.

Schema: feed_subscriptions(id, user_id, feed_url, feed_title, frequency_hours,
        last_check_at, last_etag, last_modified, last_entries_count, status, error_message)
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any

from stratum.db import query, update
from stratum.common import now_utc


def query_active_subscriptions(
    *,
    last_check_before: str,
    status: str = "active",
) -> dict[str, Any]:
    """Return subscriptions due for re-check.

    FeedTrackerEngine calls this as:
        subscription_query_fn(last_check_before=cutoff, status="active")
    Returns {"findings": {"subscriptions": [...]}} matching omodul findings contract.
    """
    rows = query(
        "SELECT id, user_id, feed_url AS url, last_etag AS etag, last_modified, "
        "       last_entries_count, frequency_hours, status "
        "FROM feed_subscriptions "
        "WHERE status = $status "
        "  AND (last_check_at IS NULL OR last_check_at < CAST($cutoff AS TIMESTAMP))",
        {"status": status, "cutoff": last_check_before},
    )
    # FeedTrackerEngine expects sub["url"] (not feed_url) and sub["etag"] (not last_etag)
    return {"findings": {"subscriptions": list(rows)}}


def update_subscription_state(
    *,
    subscription_id: str,
    last_check_at: str,
    etag: str | None = None,
    last_modified: str | None = None,
    previous_entry_ids: list[str] | None = None,
    **_extra,
) -> None:
    """Update subscription after a fetch attempt.

    FeedTrackerEngine calls this with etag/last_modified/last_check_at/previous_entry_ids.
    Maps to Stratum DB columns (last_etag, last_modified, last_check_at, last_entries_count).
    """
    changes: dict[str, Any] = {
        "last_check_at": last_check_at,
        "updated_at": now_utc(),
    }
    if etag is not None:
        changes["last_etag"] = etag
    if last_modified is not None:
        changes["last_modified"] = last_modified
    if previous_entry_ids is not None:
        changes["last_entries_count"] = len(previous_entry_ids)
    update("feed_subscriptions", subscription_id, changes)
