"""Canonical read helpers for the PostgreSQL ``stratum.notes_sl`` store."""

from __future__ import annotations

from typing import Any

from stratum.db import query, read


def get_user_note(user_id: str, note_id: str) -> dict[str, Any] | None:
    """Return one live note only when it belongs to the authenticated user."""
    note = read("notes_sl", note_id)
    if not note or note.get("user_id") != user_id or note.get("deleted_at"):
        return None
    return note


def list_recent_user_notes(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    return query(
        "SELECT id, title, updated_at FROM notes_sl "
        "WHERE user_id = %(uid)s AND deleted_at IS NULL "
        "ORDER BY updated_at DESC",
        {"uid": user_id},
        limit=limit,
    )


def list_user_notes_for_content(user_id: str, content_id: str) -> list[dict[str, Any]]:
    return query(
        "SELECT id, title FROM notes_sl "
        "WHERE %(cid)s = ANY(content_refs) AND user_id = %(uid)s "
        "AND deleted_at IS NULL ORDER BY updated_at DESC",
        {"cid": content_id, "uid": user_id},
    )


def list_user_notes_in_range(user_id: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
    """List timeline notes using PostgreSQL's portable month formatter."""
    return query(
        "SELECT id, title, created_at, to_char(created_at, 'YYYY-MM') AS month "
        "FROM notes_sl WHERE user_id = %(user_id)s "
        "AND deleted_at IS NULL AND created_at >= %(from_date)s "
        "AND created_at <= %(to_date)s ORDER BY created_at DESC LIMIT 500",
        {"user_id": user_id, "from_date": from_date, "to_date": to_date},
    )
