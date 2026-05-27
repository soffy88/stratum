"""Admin stats endpoint — wiki-only, ADMIN_SECRET gated."""

import os

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional

router = APIRouter()


def get_db():
    conn = duckdb.connect(os.path.expanduser("~/.stratum/meta.duckdb"))
    try:
        yield conn
    finally:
        conn.close()


def _require_admin(x_admin_secret: Optional[str] = Header(None)) -> None:
    """Validate X-Admin-Secret header against ADMIN_SECRET env var.

    If ADMIN_SECRET is not set in environment, this endpoint is disabled.
    """
    admin_secret = os.getenv("ADMIN_SECRET")
    if not admin_secret:
        raise HTTPException(503, "Admin endpoint not configured")
    if x_admin_secret != admin_secret:
        raise HTTPException(403, "Forbidden")


@router.get("/admin/stats", dependencies=[Depends(_require_admin)])
def get_admin_stats(db=Depends(get_db)) -> dict:
    """Return aggregate platform stats. Requires X-Admin-Secret header."""
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_substrates = db.execute("SELECT COUNT(*) FROM substrate").fetchone()[0]
    total_sessions = db.execute(
        "SELECT COUNT(*) FROM sessions WHERE revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP"
    ).fetchone()[0]
    total_feedback = db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    total_shares = db.execute("SELECT COUNT(*) FROM share_tokens").fetchone()[0]

    return {
        "users": total_users,
        "substrates": total_substrates,
        "active_sessions": total_sessions,
        "feedback_submissions": total_feedback,
        "share_links": total_shares,
    }
