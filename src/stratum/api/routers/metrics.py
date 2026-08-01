"""Telemetry & Metrics API (admin-gated)."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


def _require_admin_secret(x_admin_secret: Optional[str] = Header(None)) -> None:
    """Require X-Admin-Secret matching ADMIN_SECRET env (same as /api/admin/*)."""
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(503, "Admin endpoint not configured")
    if not hmac.compare_digest(x_admin_secret or "", admin_secret):
        raise HTTPException(403, "Forbidden")


@router.get("/metrics", dependencies=[Depends(_require_admin_secret)])
async def get_metrics():
    """Get all telemetry metrics as JSON (admin only)."""
    from stratum.services.telemetry import get_all_metrics
    return get_all_metrics()


@router.get("/metrics/prometheus", dependencies=[Depends(_require_admin_secret)])
async def get_metrics_prometheus():
    """Get metrics in Prometheus exposition format (admin only)."""
    from stratum.services.telemetry import get_all_metrics, format_prometheus
    metrics = get_all_metrics()
    return PlainTextResponse(format_prometheus(metrics), media_type="text/plain")
