"""Content ingest — file upload + web-clip."""

import asyncio
import re
import shutil
import tempfile
from pathlib import Path

_ULID_RE = re.compile(r"[0-9A-Z]{26}")


def _extract_id(raw: object) -> str | None:
    """Extract bare ULID from a findings.substrate_id that may be an IngestResult repr."""
    s = str(raw) if raw is not None else ""
    # Happy path: already a plain ULID
    if _ULID_RE.fullmatch(s):
        return s
    # Fallback: parse first ULID from IngestResult(substrate_id='...') repr
    m = _ULID_RE.search(s)
    return m.group(0) if m else None


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
    from omodul.process_inbox_substrate import (
        process_inbox_substrate,
        InboxConfig,
        InboxInput,
    )

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
        return {
            "upload_id": checksum[:12],
            "substrate_id": generate_ulid(),
            "medium": medium_hint or "unknown",
            "status": "queued",
            "message": "omodul inbox pipeline not yet available; file saved to inbox dir",
        }

    config = InboxConfig(
        file_path=str(file_path),
        file_checksum=checksum,
        user_id_hash=sha256_hex(user_id)[:16],
        medium_hint=medium_hint,
        auto_classify=True,
        llm_provider="qwen3",
        llm_model="qwen3-max",
    )
    result = await asyncio.to_thread(
        process_inbox_substrate,
        config=config,
        input_data=InboxInput(),
        output_dir=inbox_dir,
    )

    if result.get("status") == "failed":
        err = result.get("error") or {}
        raise HTTPException(500, detail=err.get("error_message", "Ingest failed"))

    findings = result.get("findings")
    response = {
        "upload_id": checksum[:12],
        "substrate_id": _extract_id(findings.substrate_id) if findings else None,
        "medium": str(findings.medium) if findings else medium_hint,
        "status": result.get("status", "completed"),
    }
    if result.get("status") == "completed":
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

    clip_path = inbox_dir / f"{generate_ulid()}.html"
    clip_path.write_text(
        html or f"<html><head><title>{url}</title></head><body></body></html>",
        encoding="utf-8",
    )
    checksum = sha256_hex(clip_path.read_text())
    config = InboxConfig(
        file_path=str(clip_path),
        file_checksum=checksum,
        user_id_hash=sha256_hex(user_id)[:16],
        medium_hint="webpage",
        auto_classify=True,
        llm_provider="qwen3",
        llm_model="qwen3-max",
    )
    result = await asyncio.to_thread(
        process_inbox_substrate,
        config=config,
        input_data=InboxInput(),
        output_dir=inbox_dir,
    )
    findings = result.get("findings")
    return {
        "substrate_id": _extract_id(findings.substrate_id) if findings else None,
        "status": result.get("status", "completed"),
        "url": url,
    }
