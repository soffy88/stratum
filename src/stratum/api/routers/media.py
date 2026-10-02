"""Layer 4: /api/v1/media/* — 音视频 URL 入库。

调用链（全主库元素，不改主库）:
  omodul.process_media_substrate
    → oprim.media_extract (yt-dlp 字幕/音频)
    → oprim.transcribe_audio (faster-whisper 本地 / DashScope)
    → oskill.media_to_structured_md (LLM 语义分段+时间戳锚点)
    → oskill.ingest_substrate (DB+向量+全文索引)
  → md_export_service.export_one (导出 .md 到 AII)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Literal

from stratum.common import jwt_auth
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter()
log = logging.getLogger(__name__)

class MediaIngestRequest(BaseModel):
    video_url: str
    kind: Literal["video", "audio"] = "video"
    asr_backend: str = "local"
    transcribe_if_no_subtitle: bool = True


class MediaIngestResponse(BaseModel):
    status: str
    video_url: str


def _run_ingest(
    video_url: str,
    user_id_hash: str,
    kind: str,
    asr_backend: str,
    transcribe: bool,
) -> None:
    from stratum.services.media_runtime import MediaRuntimeJob, dispatch_media_job

    result = dispatch_media_job(
        MediaRuntimeJob(
            url=video_url,
            user_id_hash=user_id_hash,
            kind=kind,
            asr_backend=asr_backend,
            transcribe=transcribe,
        )
    )
    log.info(
        "media_ingest: done platform=%s url=%s status=%s error=%s",
        result.get("platform"),
        video_url,
        result.get("status"),
        result.get("error"),
    )


@router.post("/api/v1/media/ingest", status_code=202, response_model=MediaIngestResponse)
async def ingest_media(
    body: MediaIngestRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
) -> MediaIngestResponse:
    """提交音视频 URL 入库（后台异步，字幕优先→本地 ASR 兜底；kind=audio 走转写链路）。"""
    uh = hash_user_id(user_id)
    background_tasks.add_task(
        _run_ingest,
        body.video_url,
        uh,
        body.kind,
        body.asr_backend,
        body.transcribe_if_no_subtitle,
    )
    return MediaIngestResponse(status="queued", video_url=body.video_url)
