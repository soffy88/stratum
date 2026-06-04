"""Timeline endpoint — aggregate knowledge items by time bucket (Phase 17.8)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from stratum.common import jwt_auth
from stratum.db import query

router = APIRouter(prefix="/api/v1", tags=["timeline"])


@router.get("/timeline")
async def get_timeline(
    from_date: datetime = Query(..., description="Start date (ISO 8601)"),
    to_date: datetime = Query(..., description="End date (ISO 8601)"),
    medium: Optional[str] = Query(None, description="Filter by medium (pdf, webpage, etc.)"),
    user_id: str = Depends(jwt_auth),
):
    """Return substrates, notes, and highlights bucketed by month for the given range."""
    medium_filter = "AND mime LIKE %(medium_pat)s" if medium else ""
    params: dict = {
        "user_id": user_id,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
    }
    if medium:
        params["medium_pat"] = f"%{medium}%"

    substrates = query(
        f"SELECT id, title, mime, created_at, strftime(created_at, '%Y-%m') AS month "
        f"FROM substrates "
        f"WHERE user_id = %(user_id)s "
        f"AND created_at >= %(from_date)s AND created_at <= %(to_date)s "
        f"{medium_filter} "
        f"ORDER BY created_at DESC LIMIT 500",
        params,
    )

    notes = query(
        "SELECT id, title, created_at, strftime(created_at, '%Y-%m') AS month "
        "FROM notes "
        "WHERE user_id = %(user_id)s "
        "AND deleted_at IS NULL "
        "AND created_at >= %(from_date)s AND created_at <= %(to_date)s "
        "ORDER BY created_at DESC LIMIT 500",
        {"user_id": user_id, "from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
    )

    highlights = query(
        "SELECT id, text_excerpt, substrate_id, created_at, "
        "strftime(created_at, '%Y-%m') AS month "
        "FROM highlights "
        "WHERE user_id = %(user_id)s "
        "AND created_at >= %(from_date)s AND created_at <= %(to_date)s "
        "ORDER BY created_at DESC LIMIT 500",
        {"user_id": user_id, "from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
    )

    # Build monthly buckets
    buckets: dict[str, dict] = {}
    for item in [*substrates, *notes, *highlights]:
        month = item.get("month", "")
        if month not in buckets:
            buckets[month] = {"month": month, "substrates": [], "notes": [], "highlights": []}

    for s in substrates:
        m = s.get("month", "")
        if m in buckets:
            buckets[m]["substrates"].append(s)
    for n in notes:
        m = n.get("month", "")
        if m in buckets:
            buckets[m]["notes"].append(n)
    for h in highlights:
        m = h.get("month", "")
        if m in buckets:
            buckets[m]["highlights"].append(h)

    sorted_buckets = sorted(buckets.values(), key=lambda b: b["month"], reverse=True)
    return {
        "buckets": sorted_buckets,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
    }
