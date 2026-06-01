"""Reading progress + interaction recording."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, read

router = APIRouter(prefix="/api/v1/interactions", tags=["interactions"])


class ProgressUpdate(BaseModel):
    position: str
    completed: bool = False


@router.post("/content/{content_id}/progress")
async def record_progress(content_id: str, body: ProgressUpdate, user_id: str = Depends(jwt_auth)):
    insert(
        "user_content_interaction",
        {
            "id": generate_ulid(),
            "user_id": user_id,
            "content_id": content_id,
            "interaction_type": "view",
            "payload": {"position": body.position, "completed": body.completed},
            "created_at": now_utc(),
        },
    )
    return {"status": "recorded"}


@router.get("/content/{content_id}/progress")
async def get_progress(content_id: str, user_id: str = Depends(jwt_auth)):
    from stratum.db import query

    rows = query(
        "SELECT payload FROM user_content_interaction "
        "WHERE user_id = %(uid)s AND content_id = %(cid)s AND interaction_type = 'view' "
        "ORDER BY created_at DESC",
        {"uid": user_id, "cid": content_id},
        limit=1,
    )
    if rows:
        return rows[0].get("payload") or {"position": "start", "completed": False}
    return {"position": "start", "completed": False}
