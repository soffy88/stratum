"""Platform content — discovery feed + article detail."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from stratum.api.routers.billing import get_active_tier
from stratum.common import jwt_auth
from stratum.db import query, read
from stratum.services.access_policy import allowed_content_tiers, can_access_content
from stratum.services.note_queries import list_user_notes_for_content

router = APIRouter(prefix="/api/v1/content", tags=["content"])

@router.get("/feed")
async def content_feed(
    page: int = 1,
    page_size: int = 20,
    domain: str | None = None,
    user_id: str = Depends(jwt_auth),
):
    offset = (page - 1) * page_size
    allowed_tiers = allowed_content_tiers(get_active_tier(user_id))
    params: dict = {
        "limit": page_size,
        "offset": offset,
        "allowed_tiers": list(allowed_tiers),
    }
    where = "deleted_at IS NULL AND access_tier = ANY(%(allowed_tiers)s)"
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
    tier = get_active_tier(user_id)
    if not can_access_content(tier, content.get("access_tier")):
        raise HTTPException(
            402,
            detail={
                "code": "content_tier_required",
                "required_tier": content.get("access_tier") or "free",
                "current_tier": tier,
            },
        )

    related_user: list = []
    from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

    result = await asyncio.to_thread(
        KnowledgeView.search,
        KnowledgeViewRequest(
            query=content["title"], top_k=5, user_id=user_id,
            scopes=["user-authored"], channels=["metadata", "lexical", "dense"],
        ),
    )
    related_user = result["results"]

    highlights = query(
        "SELECT * FROM highlights WHERE user_id = %(uid)s AND content_id = %(cid)s",
        {"uid": user_id, "cid": content_id},
    )
    user_notes = list_user_notes_for_content(user_id, content_id)

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
            {"id": r["id"], "title": r["title"], "relevance": round(r["score"], 3)}
            for r in related_user
            if r["type"] == "user_substrate"
        ],
        "related_user_notes": [
            {"id": r["id"], "title": r["title"]} for r in related_user if r["type"] == "user_note"
        ],
        "user_highlights": highlights,
        "user_notes_on_this": user_notes,
        "related_concepts": content.get("related_concepts") or [],
        "related_content_ids": content.get("related_content_ids") or [],
    }
