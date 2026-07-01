"""Platform content — discovery feed + article detail."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from stratum.common import jwt_auth
from stratum.db import query, read

router = APIRouter(prefix="/api/v1/content", tags=["content"])

try:
    from oskill.cross_layer_search import cross_layer_search

    _HAS_SEARCH = True
except ImportError:
    _HAS_SEARCH = False


@router.get("/feed")
async def content_feed(
    page: int = 1,
    page_size: int = 20,
    domain: str | None = None,
    user_id: str = Depends(jwt_auth),
):
    offset = (page - 1) * page_size
    params: dict = {"limit": page_size, "offset": offset}
    where = "deleted_at IS NULL"
    if domain:
        where += " AND $domain = ANY(domain)"
        params["domain"] = domain

    rows = query(
        f"SELECT id, type, title, author, domain, tags, access_tier, "
        f"published_at, audio_url, duration_seconds "
        f"FROM platform_content WHERE {where} "
        f"ORDER BY published_at DESC "
        f"LIMIT %(limit)s OFFSET %(offset)s",
        params,
        limit=page_size,
    )
    return {"items": rows, "page": page, "has_more": len(rows) == page_size}


@router.get("/{content_id}")
async def content_detail(content_id: str, user_id: str = Depends(jwt_auth)):
    content = read("platform_content", content_id)
    if not content:
        raise HTTPException(404, "Content not found")

    related_user: list = []
    if _HAS_SEARCH:
        result = await asyncio.to_thread(
            cross_layer_search,
            query=content["title"],
            scope=["user_substrate", "user_notes"],
            top_k=5,
            lancedb_mgr=None,
            tantivy_mgr=None,
            pgvector_mgr=None,
        )
        # Defensive post-filter: only include rows that belong to this user
        # when the backend sets user_id on results.
        related_user = [r for r in result.results if getattr(r, "user_id", None) in (None, user_id)]

    highlights = query(
        "SELECT * FROM highlights WHERE user_id = %(uid)s AND content_id = %(cid)s",
        {"uid": user_id, "cid": content_id},
    )
    user_notes = query(
        "SELECT id, title FROM notes_sl "
        "WHERE $cid = ANY(content_refs) AND user_id = $uid AND deleted_at IS NULL",
        {"cid": content_id, "uid": user_id},
    )

    return {
        **{
            k: content.get(k)
            for k in (
                "id",
                "title",
                "author",
                "type",
                "body_markdown",
                "body_html",
                "audio_url",
                "published_at",
                "version",
                "access_tier",
            )
        },
        "domain": content.get("domain") or [],
        "tags": content.get("tags") or [],
        "related_user_substrate": [
            {"id": r.id, "title": r.title, "relevance": round(r.score, 3)}
            for r in related_user
            if r.type == "user_substrate"
        ],
        "related_user_notes": [
            {"id": r.id, "title": r.title} for r in related_user if r.type == "user_note"
        ],
        "user_highlights": highlights,
        "user_notes_on_this": user_notes,
        "related_concepts": content.get("related_concepts") or [],
        "related_content_ids": content.get("related_content_ids") or [],
    }
