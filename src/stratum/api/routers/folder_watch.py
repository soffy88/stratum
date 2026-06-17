"""Folder watch — accept a local/remote path and trigger background scan."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import insert, query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/folder-watch", tags=["folder-watch"])


class FolderWatchRequest(BaseModel):
    path: str
    description: str | None = None


class FolderWatchResponse(BaseModel):
    id: str
    path: str
    description: str | None
    status: str


@router.post("", response_model=FolderWatchResponse)
async def add_folder_watch(
    body: FolderWatchRequest,
    user_id: str = Depends(jwt_auth),
):
    watch_id = generate_ulid()
    now = now_utc()

    insert(
        "folder_watches",
        {
            "id": watch_id,
            "user_id": user_id,
            "path": body.path,
            "description": body.description,
            "status": "active",
            "created_at": now,
        },
    )

    log.info("folder_watch created id=%s user=%s path=%s", watch_id, user_id, body.path)

    return FolderWatchResponse(
        id=watch_id,
        path=body.path,
        description=body.description,
        status="active",
    )


@router.get("", response_model=list[FolderWatchResponse])
async def list_folder_watches(user_id: str = Depends(jwt_auth)):
    rows = query(
        "SELECT id, path, description, status FROM folder_watches WHERE user_id = $1 ORDER BY created_at DESC",
        user_id,
    )
    return [
        FolderWatchResponse(
            id=r["id"],
            path=r["path"],
            description=r.get("description"),
            status=r["status"],
        )
        for r in rows
    ]
