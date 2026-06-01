"""Content ingest — file upload + web-clip."""

import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from stratum.common import (
    dedup_cache,
    ensure_dir,
    generate_ulid,
    jwt_auth,
    sha256_hex,
    user_inbox_dir,
)

router = APIRouter(prefix="/api/v1/inbox", tags=["inbox"])

_UPLOAD_MAX_BYTES = 500 * 1024 * 1024  # 500 MB

# ── Optional omodul imports ───────────────────────────────────────────────────
try:
    from omodul.knowledge.process_inbox import process_inbox

    _HAS_INBOX = True
except ImportError:
    _HAS_INBOX = False


async def _save_upload(file: UploadFile, dest_dir: Path) -> tuple[Path, str]:
    """Stream upload to temp file, return (path, sha256)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload").suffix
    dest = dest_dir / f"{generate_ulid()}{suffix}"
    h = __import__("hashlib").sha256()
    with dest.open("wb") as fp:
        while chunk := await file.read(65536):
            fp.write(chunk)
            h.update(chunk)
    return dest, h.hexdigest()


@router.post("/submit")
async def inbox_submit(
    file: UploadFile = File(...),
    medium_hint: str = Form(None),
    user_id: str = Depends(jwt_auth),
):
    inbox_dir = ensure_dir(user_inbox_dir(user_id))

    # Check file size header early
    if file.size and file.size > _UPLOAD_MAX_BYTES:
        raise HTTPException(413, f"File too large (max {_UPLOAD_MAX_BYTES // 1048576} MB)")

    file_path, checksum = await _save_upload(file, inbox_dir)

    # Dedup check
    fp_key = f"inbox:{user_id}:{checksum}"
    cached = await dedup_cache.get(fp_key)
    if cached:
        return {**cached, "deduplicated": True}

    if not _HAS_INBOX:
        # omodul not available — record file, return stub
        return {
            "upload_id": checksum[:12],
            "substrate_id": generate_ulid(),
            "medium": medium_hint or "unknown",
            "status": "queued",
            "message": "omodul inbox pipeline not yet available; file saved to inbox dir",
        }

    # Run omodul process_inbox on the single-file inbox dir
    result = await process_inbox(inbox_dir=inbox_dir, archive_after_process=True)

    if result.failed:
        raise HTTPException(500, detail=result.failed[0].get("error", "Ingest failed"))

    processed = result.processed[0] if result.processed else None
    response = {
        "upload_id": checksum[:12],
        "substrate_id": str(processed.substrate_id) if processed else None,
        "medium": str(processed.medium) if processed else medium_hint,
        "status": "completed" if processed else "needs_review",
    }
    if processed:
        await dedup_cache.set(fp_key, response, ttl=120)
    return response


@router.post("/web-clip")
async def inbox_webclip(
    url: str = Form(...),
    html: str = Form(None),
    user_id: str = Depends(jwt_auth),
):
    """Save a web page clip to inbox."""
    inbox_dir = ensure_dir(user_inbox_dir(user_id))

    if not _HAS_INBOX:
        return {
            "substrate_id": None,
            "status": "not_implemented",
            "message": "omodul web-clip pipeline not yet available",
        }

    # Write HTML to a temp file and process
    clip_path = inbox_dir / f"{generate_ulid()}.html"
    clip_path.write_text(
        html or f"<html><head><title>{url}</title></head><body></body></html>",
        encoding="utf-8",
    )
    result = await process_inbox(inbox_dir=inbox_dir, archive_after_process=True)
    processed = result.processed[0] if result.processed else None
    return {
        "substrate_id": str(processed.substrate_id) if processed else None,
        "status": "completed" if processed else "needs_review",
        "url": url,
    }
