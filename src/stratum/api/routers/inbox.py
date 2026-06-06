"""Content ingest — file upload + web-clip."""

import asyncio
import re
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


def _fill_derivative_content(substrate_id: str, findings: object) -> None:
    """Write parsed content from findings.derivative_ids into derivative.content.

    omodul stores content as a list of Python repr-strings, e.g.:
      ["{'markdown': '# Title...', 'plaintext': '...', 'chapters': '[...]'}"]
    We parse each item and UPDATE derivative rows by (substrate_id, kind).
    """
    deriv_ids = getattr(findings, "derivative_ids", None) or []
    if not deriv_ids:
        return
    log = logging.getLogger(__name__)
    for item in deriv_ids:
        try:
            d = ast.literal_eval(item) if isinstance(item, str) else item
        except (ValueError, SyntaxError):
            log.warning("deriv_parse_failed substrate_id=%s", substrate_id)
            continue
        if not isinstance(d, dict):
            continue
        for kind, content in d.items():
            if not content or not isinstance(content, str):
                continue
            try:
                db_execute(
                    "UPDATE derivative SET content = $content"
                    " WHERE substrate_id = $sid AND kind = $kind",
                    {"content": content, "sid": substrate_id, "kind": kind},
                )
            except Exception as exc:
                log.warning(
                    "deriv_content_update_failed substrate_id=%s kind=%s error=%s",
                    substrate_id,
                    kind,
                    exc,
                )


import ast
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from stratum.common import (
    dedup_cache,
    ensure_dir,
    generate_ulid,
    jwt_auth,
    now_utc,
    sha256_hex,
    user_inbox_dir,
)
from stratum.utils.user_id_hash import hash_user_id
from stratum.db import execute as db_execute, insert as db_insert, update as db_update

try:
    from oprim import url_fetch_ssrf_safe as _url_fetch_ssrf_safe

    _HAS_SSRF_SAFE = True
except ImportError:
    _HAS_SSRF_SAFE = False

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
        user_id_hash=hash_user_id(user_id),
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

    # UPDATE title + populate derivative.content from omodul findings.
    substrate_id = response["substrate_id"]
    if substrate_id and result.get("status") != "failed":
        stored_title = (
            file.filename or (getattr(findings, "title", None) if findings else None) or "untitled"
        )
        try:
            db_update("substrates", substrate_id, {"title": stored_title, "updated_at": now_utc()})
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "upload_title_update_failed substrate_id=%s error=%s", substrate_id, exc
            )
        if findings:
            _fill_derivative_content(substrate_id, findings)

    if result.get("status") == "completed":
        await dedup_cache.set(fp_key, response, ttl=120)
    return response


_WEB_CLIP_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_WEB_CLIP_TIMEOUT = 30  # seconds (int for url_fetch_ssrf_safe)


async def _fetch_url_html(url: str) -> str:
    """Fetch URL via oprim.url_fetch_ssrf_safe (DNS-pinned, SSRF-safe).

    Raises HTTPException on fetch failure with generic messages to avoid
    leaking internal network topology.
    """
    import logging

    log = logging.getLogger(__name__)

    if not _HAS_SSRF_SAFE:
        raise HTTPException(503, "URL fetch unavailable: oprim not installed")

    result = await asyncio.to_thread(
        _url_fetch_ssrf_safe,
        url=url,
        timeout=_WEB_CLIP_TIMEOUT,
        max_bytes=_WEB_CLIP_MAX_BYTES,
    )

    err = result.get("error")
    if err == "ssrf_blocked":
        raise HTTPException(403, "URL resolves to a disallowed address")
    if err and "timed out" in err:
        log.warning("web_clip_timeout url=%s", url)
        raise HTTPException(504, "URL fetch timed out")
    if err:
        log.warning("web_clip_fetch_error url=%s error=%s", url, err)
        raise HTTPException(502, "Failed to fetch URL")

    status = result.get("status_code")
    if status == 404:
        raise HTTPException(404, "URL not found")
    if status and status >= 400:
        raise HTTPException(status, "URL fetch failed")

    html = result.get("body_text") or ""
    if not html:
        raise HTTPException(502, "URL returned empty content")
    return html


def _extract_html_meta(html: str, url: str) -> dict:
    """Extract title and snippet from raw HTML for inline preview."""
    import html as html_lib
    import re

    # Title from <title> tag
    title_m = re.search(r"<title[^>]*>([^<]{1,300})</title>", html, re.I | re.S)
    title = html_lib.unescape(title_m.group(1).strip()) if title_m else url

    # Strip tags for snippet
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    snippet = text[:500] if text else ""
    word_count = len(text.split()) if text else 0

    return {"title": title, "snippet": snippet, "word_count": word_count}


@router.post("/web-clip")
async def inbox_webclip(
    url: str = Form(...),
    html: str = Form(None),
    title_override: str = Form(None),
    tags: str = Form(None),
    fetch_mode: str = Form("full"),
    note: str = Form(None),
    user_id: str = Depends(jwt_auth),
):
    """Save a web page clip to inbox. Fetches URL server-side if html not provided."""
    inbox_dir = ensure_dir(user_inbox_dir(user_id))

    if not _HAS_INBOX:
        return {
            "substrate_id": None,
            "status": "not_implemented",
            "message": "omodul web-clip pipeline not yet available",
        }

    if not html:
        html = await _fetch_url_html(url)

    # Extract title/snippet before writing — used in response preview
    html_meta = _extract_html_meta(html, url)
    display_title = (
        title_override.strip() if title_override and title_override.strip() else html_meta["title"]
    )
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    clip_path = inbox_dir / f"{generate_ulid()}.html"
    clip_path.write_text(html, encoding="utf-8")
    checksum = sha256_hex(clip_path.read_text())
    config = InboxConfig(
        file_path=str(clip_path),
        file_checksum=checksum,
        user_id_hash=hash_user_id(user_id),
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
    substrate_id = _extract_id(findings.substrate_id) if findings else None

    # UPDATE title + populate derivative.content from omodul findings.
    if substrate_id and result.get("status") != "failed":
        stored_title = (
            display_title or (getattr(findings, "title", None) if findings else None) or url
        )
        try:
            db_update("substrates", substrate_id, {"title": stored_title, "updated_at": now_utc()})
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "web_clip_title_update_failed substrate_id=%s error=%s", substrate_id, exc
            )
        if findings:
            _fill_derivative_content(substrate_id, findings)

    return {
        "substrate_id": substrate_id,
        "status": result.get("status", "completed"),
        "url": url,
        "title": display_title or html_meta["title"],
        "snippet": html_meta["snippet"],
        "word_count": html_meta["word_count"],
        "medium": getattr(findings, "medium", "webpage") if findings else "webpage",
        "tags": parsed_tags,
    }
