"""Folder watch — accept a local/remote path and trigger background scan."""

import json
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
    generate_derivatives: list[str] = []


class FolderWatchResponse(BaseModel):
    id: str
    path: str
    description: str | None = None
    status: str
    last_scan_at: datetime | None = None
    file_count: int = 0
    scan_status: str = "idle"
    scanned_count: int = 0
    ingested_count: int = 0
    current_file: str = ""


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
            "generate_derivatives": json.dumps(body.generate_derivatives),
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


def _row_to_response(r: dict) -> FolderWatchResponse:
    return FolderWatchResponse(
        id=r["id"],
        path=r["path"],
        description=r.get("description"),
        status=r["status"],
        last_scan_at=r.get("last_scan_at"),
        file_count=r.get("file_count") or 0,
        scan_status=r.get("scan_status") or "idle",
        scanned_count=r.get("scanned_count") or 0,
        ingested_count=r.get("ingested_count") or 0,
        current_file=r.get("current_file") or "",
    )


_SELECT = (
    "SELECT id, path, description, status, last_scan_at, file_count, "
    "scan_status, scanned_count, ingested_count, current_file "
    "FROM folder_watches"
)


@router.get("", response_model=list[FolderWatchResponse])
async def list_folder_watches(user_id: str = Depends(jwt_auth)):
    rows = query(
        _SELECT + " WHERE user_id = %(uid)s ORDER BY created_at DESC",
        {"uid": user_id},
        limit=500,
    )
    return [_row_to_response(r) for r in rows]


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
    rows = query(_SELECT + " WHERE id = %(id)s", {"id": watch_id}, limit=1)
    return _row_to_response(rows[0])


@router.patch("/{watch_id}/resume", response_model=FolderWatchResponse)
async def resume_folder_watch(watch_id: str, user_id: str = Depends(jwt_auth)):
    db_execute(
        "UPDATE folder_watches SET status = 'active' WHERE id = %(id)s AND user_id = %(uid)s",
        {"id": watch_id, "uid": user_id},
    )
    rows = query(_SELECT + " WHERE id = %(id)s", {"id": watch_id}, limit=1)
    return _row_to_response(rows[0])
