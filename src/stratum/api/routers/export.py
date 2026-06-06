"""Export router — AII integration: stream substrate markdown to shared volume."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from stratum.common import jwt_auth
from stratum.db import _conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_ALLOWED_MEDIUMS = {"paper", "book", "article", "webpage", "note", "report", "other"}


@router.get("/markdown")
async def export_markdown(
    medium: list[str] | None = Query(default=None),
    tag_exclude: list[str] | None = Query(default=None),
    user_id: str = Depends(jwt_auth),
):
    """Return substrates + markdown derivative content for AII ingestion.

    Filters:
      medium — allowlist of medium values (e.g. paper, book)
      tag_exclude — reserved; not yet implemented
    """
    uid_hash = hash_user_id(user_id)

    # Validate medium values against known set to prevent SQL injection
    medium_filter = [m for m in (medium or []) if m in _ALLOWED_MEDIUMS] or None

    sql = """
        SELECT
            s.id                                          AS substrate_id,
            s.title,
            json_extract_string(s.meta_json, '$.medium') AS medium,
            s.source,
            s.published_at,
            s.created_at,
            d.content
        FROM substrates s
        JOIN derivative d
          ON d.substrate_id = s.id
         AND d.kind = 'markdown'
         AND d.content IS NOT NULL
         AND d.content != ''
        WHERE s.user_id = $uid
    """
    params: dict = {"uid": uid_hash}

    if medium_filter:
        placeholders = ", ".join(f"$m{i}" for i in range(len(medium_filter)))
        sql += f"\n  AND json_extract_string(s.meta_json, '$.medium') IN ({placeholders})"
        for i, m in enumerate(medium_filter):
            params[f"m{i}"] = m

    sql += "\nORDER BY s.created_at DESC"

    with _conn() as conn:
        cursor = conn.execute(sql, params)
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

    items = []
    for row in rows:
        items.append(
            {
                "substrate_id": row["substrate_id"],
                "title": row["title"],
                "medium": row["medium"],
                "source": row["source"],
                "published_at": row["published_at"].isoformat() if row["published_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "content": row["content"],
            }
        )

    return {"count": len(items), "items": items}
