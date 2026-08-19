"""Multi-tenant ownership helpers (raw JWT sub + hash_user_id)."""

from __future__ import annotations

from typing import Any

from stratum.utils.user_id_hash import hash_user_id


def owner_ids(user_id: str) -> tuple[str, str]:
    """Return (raw_user_id, hashed_user_id)."""
    return user_id, hash_user_id(user_id)


def owns_substrate_row(user_id: str, row_user_id: str | None) -> bool:
    if row_user_id is None:
        return False
    raw, uh = owner_ids(user_id)
    return row_user_id in (raw, uh)


def fetch_owned_substrate(
    substrate_id: str, user_id: str, columns: str = "id, title, source_path, user_id"
) -> dict[str, Any] | None:
    """Load substrate if owned by user (raw or hash). Uses get_conn (? placeholders)."""
    from stratum.db import get_conn

    raw, uh = owner_ids(user_id)
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {columns} FROM substrates WHERE id = ? AND (user_id = ? OR user_id = ?)",
            (substrate_id, raw, uh),
        ).fetchone()
    if not row:
        return None
    # Map by column order for common set
    cols = [c.strip() for c in columns.split(",")]
    return {cols[i]: row[i] for i in range(len(cols))}
