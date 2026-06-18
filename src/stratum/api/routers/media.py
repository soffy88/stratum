"""Layer 4: /api/v1/media/* — 视频 URL 入库。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl

from stratum.common import jwt_auth
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter()
log = logging.getLogger(__name__)


class MediaIngestRequest(BaseModel):
    video_url: str


class MediaIngestResponse(BaseModel):
    status: str
    video_url: str


def _run_ingest(video_url: str, user_id_hash: str) -> None:
    from stratum.services.video_ingest_service import ingest_video_url
    try:
        result = ingest_video_url(url=video_url, user_id_hash=user_id_hash)
        log.info("media_ingest: done url=%s result=%s", video_url, result)
    except Exception as exc:
        log.error("media_ingest: failed url=%s: %s", video_url, exc, exc_info=True)


@router.post("/api/v1/media/ingest", status_code=202, response_model=MediaIngestResponse)
async def ingest_media(
    body: MediaIngestRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
) -> MediaIngestResponse:
    """提交视频 URL 入库（后台异步处理，字幕优先）。"""
    uh = hash_user_id(user_id)
    background_tasks.add_task(_run_ingest, body.video_url, uh)
    return MediaIngestResponse(status="queued", video_url=body.video_url)
