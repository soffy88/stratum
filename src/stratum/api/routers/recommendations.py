"""Platform content recommendations."""

import asyncio

from fastapi import APIRouter, Depends

from stratum.common import jwt_auth
from stratum.db import query

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

try:
    from oskill.recommend_content import (
        ContentMeta,
        Recommendation,
        UserBehaviorProfile,
        recommend_content,
    )

    _HAS_REC = True
except ImportError:
    _HAS_REC = False


def _parse_dt(s: str):
    from datetime import datetime, timezone

    try:
        return datetime.fromisoformat(str(s)).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


@router.get("")
async def get_recommendations(user_id: str = Depends(jwt_auth)):
    if not _HAS_REC:
        return {"recommendations": []}

    viewed = query(
        "SELECT content_id FROM user_content_interaction "
        "WHERE user_id = %(uid)s AND interaction_type = 'view' "
        "ORDER BY created_at DESC",
        {"uid": user_id},
        limit=50,
    )
    bookmarked = query(
        "SELECT content_id FROM user_content_interaction "
        "WHERE user_id = %(uid)s AND interaction_type = 'bookmark'",
        {"uid": user_id},
        limit=50,
    )

    profile = UserBehaviorProfile(
        recent_viewed=[r["content_id"] for r in viewed],
        bookmarked=[r["content_id"] for r in bookmarked],
    )

    candidates_raw = query(
        "SELECT id, title, domain, tags, related_concepts, published_at "
        "FROM platform_content WHERE deleted_at IS NULL "
        "ORDER BY published_at DESC",
        limit=100,
    )
    candidates = [
        ContentMeta(
            content_id=c["id"],
            title=c["title"],
            domain=c.get("domain") or [],
            tags=c.get("tags") or [],
            related_concept_ids=c.get("related_concepts") or [],
            published_at=_parse_dt(c["published_at"]),
        )
        for c in candidates_raw
    ]

    recs: list[Recommendation] = await asyncio.to_thread(
        recommend_content,
        user_profile=profile,
        candidate_pool=candidates,
        top_k=10,
    )

    return {
        "recommendations": [
            {
                "content_id": r.content_id,
                "title": r.title,
                "score": round(r.score, 4),
                "reason": r.reason,
            }
            for r in recs
        ]
    }
