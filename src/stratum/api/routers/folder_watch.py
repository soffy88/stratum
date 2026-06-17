"""Folder watch — accept a local/remote path and trigger background scan."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import execute as db_execute, insert, query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/folder-watch", tags=["folder-watch"])


class FolderWatchRequest(BaseModel):
    path: str
    description: str | None = None


class FolderWatchResponse(BaseModel):
    id: str
    path: str
    description: str | None = None
    status: str
    last_scan_at: datetime | None = None
    file_count: int = 0


@router.post("", response_model=FolderWatchResponse)
async def add_folder_watch(
    body: FolderWatchRequest,
    user_id: str = Depends(jwt_auth),
):
    watch_id = generate_ulid()

    insert(
        "folder_watches",
        {
            "id": watch_id,
            "user_id": user_id,
            "path": body.path,
            "description": body.description,
            "status": "active",
            "created_at": now_utc(),
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
        "SELECT id, path, description, status, last_scan_at, file_count "
        "FROM folder_watches WHERE user_id = %(uid)s ORDER BY created_at DESC",
        {"uid": user_id},
        limit=500,
    )
    return [
        FolderWatchResponse(
            id=r["id"],
            path=r["path"],
            description=r.get("description"),
            status=r["status"],
            last_scan_at=r.get("last_scan_at"),
            file_count=r.get("file_count") or 0,
        )
        for r in rows
    ]


@router.delete("/{watch_id}", status_code=204)
async def delete_folder_watch(watch_id: str, user_id: str = Depends(jwt_auth)):
    db_execute(
        "DELETE FROM folder_watches WHERE id = %(id)s AND user_id = %(uid)s",
        {"id": watch_id, "uid": user_id},
    )


@router.patch("/{watch_id}/pause", response_model=FolderWatchResponse)
async def pause_folder_watch(watch_id: str, user_id: str = Depends(jwt_auth)):
    db_execute(
        "UPDATE folder_watches SET status = 'paused' WHERE id = %(id)s AND user_id = %(uid)s",
        {"id": watch_id, "uid": user_id},
    )
    rows = query(
        "SELECT id, path, description, status, last_scan_at, file_count "
        "FROM folder_watches WHERE id = %(id)s",
        {"id": watch_id},
        limit=1,
    )
    r = rows[0]
    return FolderWatchResponse(
        id=r["id"], path=r["path"], description=r.get("description"),
        status=r["status"], last_scan_at=r.get("last_scan_at"),
        file_count=r.get("file_count") or 0,
    )


@router.patch("/{watch_id}/resume", response_model=FolderWatchResponse)
async def resume_folder_watch(watch_id: str, user_id: str = Depends(jwt_auth)):
    db_execute(
        "UPDATE folder_watches SET status = 'active' WHERE id = %(id)s AND user_id = %(uid)s",
        {"id": watch_id, "uid": user_id},
    )
    rows = query(
        "SELECT id, path, description, status, last_scan_at, file_count "
        "FROM folder_watches WHERE id = %(id)s",
        {"id": watch_id},
        limit=1,
    )
    r = rows[0]
    return FolderWatchResponse(
        id=r["id"], path=r["path"], description=r.get("description"),
        status=r["status"], last_scan_at=r.get("last_scan_at"),
        file_count=r.get("file_count") or 0,
    )
