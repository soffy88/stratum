"""Canonical Stratum runtime for audio/video URL ingestion.

All callers converge here; extraction/transcription authority stays in 3O.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from stratum.services.media_platforms import canonical_media_metadata, cookie_path_for_platform, detect_media_platform

log = logging.getLogger(__name__)
_DEFAULT_PROXY = "socks5h://172.19.0.1:10808"

@dataclass(frozen=True)
class MediaRuntimeJob:
    url: str
    user_id_hash: str
    kind: str = "video"
    asr_backend: str = "local"
    transcribe: bool = True
    source_metadata: dict[str, Any] = field(default_factory=dict)

class MediaRuntimeError(RuntimeError):
    pass

def _load_runtime() -> tuple[Any, Any, Any]:
    try:
        m = importlib.import_module("omodul.process_media_substrate")
        return m.MediaConfig, m.MediaInput, m.process_media_substrate
    except (ImportError, AttributeError) as exc:
        raise MediaRuntimeError("omodul media runtime unavailable") from exc

def _transcript_source(result: dict[str, Any]) -> str:
    if result.get("has_subtitle"):
        return "subtitle"
    if result.get("transcribed"):
        return "asr"
    return "none"

def _project_completed_result(*, result: dict[str, Any], job: MediaRuntimeJob, platform: str) -> None:
    sid = str(result.get("substrate_id") or "").strip()
    if not sid:
        raise MediaRuntimeError("completed media result missing substrate_id")
    from stratum.db import get_conn
    title = str(result.get("title") or "").strip() or None
    with get_conn() as conn:
        row = conn.execute("SELECT meta_json FROM substrates WHERE id=?", (sid,)).fetchone()
        meta = json.loads(row[0] or "{}") if row else {}
        meta.update(canonical_media_metadata(job.url, job.kind))
        meta.update(job.source_metadata)
        meta["platform"] = platform
        meta["transcript_source"] = _transcript_source(result)
        payload = json.dumps(meta, ensure_ascii=False)
        if title:
            conn.execute("UPDATE substrates SET meta_json=?, title=? WHERE id=?", (payload, title, sid))
        else:
            conn.execute("UPDATE substrates SET meta_json=? WHERE id=?", (payload, sid))
    try:
        from stratum.services.md_export_service import export_one
        export_one(sid)
    except Exception as exc:
        log.warning("media_runtime: md_export failed sid=%s: %s", sid, exc)
    try:
        from stratum.services.layer_generator import generate_substrate_layers
        with get_conn() as conn:
            trow = conn.execute("SELECT title FROM substrates WHERE id=?", (sid,)).fetchone()
            crow = conn.execute("SELECT content FROM derivative WHERE substrate_id=? AND content IS NOT NULL AND content <> '' ORDER BY CASE WHEN kind='markdown' THEN 0 WHEN kind LIKE 'translation%%zh%%' THEN 1 ELSE 2 END LIMIT 1", (sid,)).fetchone()
        generate_substrate_layers(sid, title=(trow[0] if trow else None), content=(crow[0] if crow else None))
    except Exception as exc:
        log.warning("media_runtime: layer generation failed sid=%s: %s", sid, exc)

async def dispatch_media_job_async(job: MediaRuntimeJob, *, config_factory: Callable[..., Any] | None = None, input_factory: Callable[[], Any] | None = None, processor: Callable[..., Any] | None = None, projector: Callable[..., None] | None = None) -> dict[str, Any]:
    if not job.url.strip():
        raise MediaRuntimeError("media url is required")
    if not job.user_id_hash.strip():
        raise MediaRuntimeError("user_id_hash is required")
    if job.kind not in {"video", "audio"}:
        raise MediaRuntimeError("kind must be video or audio")
    if config_factory is None or input_factory is None or processor is None:
        cf, inf, proc = _load_runtime()
        config_factory = config_factory or cf
        input_factory = input_factory or inf
        processor = processor or proc
    platform = detect_media_platform(job.url)
    config = config_factory(video_url=job.url, user_id_hash=job.user_id_hash, proxy=os.environ.get("STRATUM_MEDIA_PROXY", _DEFAULT_PROXY), asr_backend=job.asr_backend, transcribe_if_no_subtitle=job.transcribe, llm_provider="qwen3", llm_model="qwen3-max", cookies_path=cookie_path_for_platform(platform))
    with tempfile.TemporaryDirectory(prefix="media_ingest_") as tmpdir:
        try:
            value = processor(config=config, input_data=input_factory(), output_dir=Path(tmpdir))
            result = await value if hasattr(value, "__await__") else value
        except Exception as exc:
            log.exception("media_runtime: processor failed platform=%s url=%s", platform, job.url)
            return {"status": "failed", "error": str(exc), "platform": platform, "source_url": job.url}
    if not isinstance(result, dict):
        return {"status": "failed", "error": "invalid media runtime result", "platform": platform, "source_url": job.url}
    result = dict(result)
    result.setdefault("platform", platform)
    result.setdefault("source_url", job.url)
    if result.get("status") == "completed":
        try:
            (projector or _project_completed_result)(result=result, job=job, platform=platform)
        except Exception as exc:
            log.exception("media_runtime: projection failed url=%s", job.url)
            return {**result, "status": "failed", "error": f"projection_failed: {exc}"}
    return result

def dispatch_media_job(job: MediaRuntimeJob, **kwargs: Any) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(dispatch_media_job_async(job, **kwargs))
    raise MediaRuntimeError("active event loop: use dispatch_media_job_async")
