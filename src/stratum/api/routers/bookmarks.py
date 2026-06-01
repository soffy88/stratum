"""Bookmarks."""

from fastapi import APIRouter, Depends

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query

router = APIRouter(prefix="/api/v1/bookmarks", tags=["bookmarks"])


@router.post("")
async def add_bookmark(content_id: str, user_id: str = Depends(jwt_auth)):
    insert(
        "user_content_interaction",
        {
            "id": generate_ulid(),
            "user_id": user_id,
            "content_id": content_id,
            "interaction_type": "bookmark",
            "created_at": now_utc(),
        },
    )
    return {"status": "bookmarked", "content_id": content_id}


@router.get("")
async def list_bookmarks(user_id: str = Depends(jwt_auth)):
    return query(
        "SELECT uci.id, uci.content_id, uci.created_at, pc.title AS content_title "
        "FROM user_content_interaction uci "
        "LEFT JOIN platform_content pc ON uci.content_id = pc.id "
        "WHERE uci.user_id = %(uid)s AND uci.interaction_type = 'bookmark' "
        "ORDER BY uci.created_at DESC",
        {"uid": user_id},
    )
