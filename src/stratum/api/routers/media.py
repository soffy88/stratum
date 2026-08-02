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

import asyncio
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Literal

from stratum.common import jwt_auth
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter()
log = logging.getLogger(__name__)

_PROXY = "socks5h://172.19.0.1:10808"  # sing-box mixed inbound (host 0.0.0.0:10808), WSL clash 已死


class MediaIngestRequest(BaseModel):
    video_url: str
    kind: Literal["video", "audio"] = "video"
    asr_backend: str = "local"
    transcribe_if_no_subtitle: bool = True


class MediaIngestResponse(BaseModel):
    status: str
    video_url: str


def _run_ingest(
    video_url: str, user_id_hash: str, kind: str, asr_backend: str, transcribe: bool,
) -> None:
    from omodul.process_media_substrate import (
        MediaConfig, MediaInput, process_media_substrate,
    )

    config = MediaConfig(
        video_url=video_url,
        user_id_hash=user_id_hash,
        proxy=_PROXY,
        asr_backend=asr_backend,
        transcribe_if_no_subtitle=transcribe,
        llm_provider="qwen3",
        llm_model="qwen3-max",
        cookies_path="~/.stratum/youtube_cookies.txt",
    )

    with tempfile.TemporaryDirectory(prefix="media_ingest_") as tmpdir:
        try:
            result = asyncio.run(
                process_media_substrate(
                    config=config,
                    input_data=MediaInput(),
                    output_dir=Path(tmpdir),
                )
            )
        except Exception as exc:
            log.error("media_ingest: process_media_substrate failed url=%s: %s", video_url, exc, exc_info=True)
            return

    status = result.get("status")
    log.info(
        "media_ingest: done url=%s status=%s has_subtitle=%s transcribed=%s error=%s",
        video_url, status, result.get("has_subtitle"), result.get("transcribed"),
        result.get("error"),
    )

    if status == "completed":
        sid = result.get("substrate_id") or ""
        if sid:
            # ingest_substrate classifies .md → medium="other"; patch meta_json+title for media.
            try:
                import json as _json
                from stratum.db import get_conn
                title = (result.get("title") or "").strip() or None
                with get_conn() as conn:
                    row = conn.execute(
                        "SELECT meta_json FROM substrates WHERE id=?", (sid,)
                    ).fetchone()
                    meta = _json.loads(row[0] or "{}") if row else {}
                    meta["medium"] = kind
                    meta_str = _json.dumps(meta, ensure_ascii=False)
                    if title:
                        conn.execute(
                            "UPDATE substrates SET meta_json=?, title=? WHERE id=?",
                            (meta_str, title, sid),
                        )
                    else:
                        conn.execute(
                            "UPDATE substrates SET meta_json=? WHERE id=?",
                            (meta_str, sid),
                        )
                    log.info("media_ingest: patched medium=%s title=%s sid=%s", kind, title, sid)
            except Exception as exc:
                log.warning("media_ingest: medium/title patch failed sid=%s: %s", sid, exc)

            try:
                from stratum.services.md_export_service import export_one
                export_one(sid)
            except Exception as exc:
                log.warning("media_ingest: md_export failed sid=%s: %s", sid, exc)


@router.post("/api/v1/media/ingest", status_code=202, response_model=MediaIngestResponse)
async def ingest_media(
    body: MediaIngestRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
) -> MediaIngestResponse:
    """提交音视频 URL 入库（后台异步，字幕优先→本地 ASR 兜底；kind=audio 走转写链路）。"""
    uh = hash_user_id(user_id)
    background_tasks.add_task(
        _run_ingest, body.video_url, uh, body.kind, body.asr_backend, body.transcribe_if_no_subtitle,
    )
    return MediaIngestResponse(status="queued", video_url=body.video_url)
