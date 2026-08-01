"""Export router — AII integration + 整库 Markdown vault 导出."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

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
            s.meta_json ->> 'medium'                      AS medium,
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
        sql += f"\n  AND s.meta_json ->> 'medium' IN ({placeholders})"
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


@router.get("/vault/preview")
async def export_vault_preview(user_id: str = Depends(jwt_auth)):
    """Preview counts for full knowledge-base vault export."""
    from stratum.services.vault_export_service import vault_stats

    return {"status": "ok", "stats": vault_stats(user_id)}


@router.get("/vault")
async def export_vault_zip(user_id: str = Depends(jwt_auth)):
    """Download migratable Markdown vault as ZIP (notes + concepts + sources).

    MVP 验收 #4: 一键导出整个知识库为可迁移的 Markdown 文件夹。
    """
    from stratum.services.vault_export_service import build_vault_zip

    data = build_vault_zip(user_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="aii-note-vault.zip"',
        },
    )
