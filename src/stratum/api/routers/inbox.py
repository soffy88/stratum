"""Content ingest — file upload + web-clip."""

import asyncio
import ipaddress
import re
import shutil
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

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
from stratum.db import insert as db_insert

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


_WEB_CLIP_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_WEB_CLIP_TIMEOUT = 30.0


def _validate_fetch_url(url: str) -> None:
    """Reject SSRF-prone URLs before any network call.

    Checks: scheme is http/https, hostname resolves to a public IP (not
    loopback / private / link-local / reserved / multicast / unspecified).
    Raises HTTPException(400) for invalid URLs, HTTPException(403) for
    disallowed destinations — generic messages avoid SSRF reconnaissance.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "URL must use http or https scheme")
    host = parsed.hostname
    if not host:
        raise HTTPException(400, "Invalid URL")
    try:
        addrs = socket.getaddrinfo(host.lower().rstrip("."), None)
    except socket.gaierror:
        raise HTTPException(400, "Cannot resolve URL hostname")
    for *_, sockaddr in addrs:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(403, "URL resolves to a disallowed address")


async def _fetch_url_html(url: str) -> str:
    """Fetch URL and return HTML. Validates URL before fetching.

    Raises HTTPException on fetch failure with generic messages to avoid
    leaking internal network topology.

    SECURITY NOTE — TOCTOU / DNS rebinding (MEDIUM, tracked):
    _validate_fetch_url resolves the hostname and checks IPs, but httpx
    performs a second DNS lookup at connect time. A DNS rebinding attack
    could change the resolution between these two points. Full mitigation
    requires a pinned-IP custom transport (pre-resolve → pass exact IP to
    kernel, preserve Host/SNI for TLS). Not implemented here because:
    - endpoint is JWT-authenticated (attacker needs a valid token first)
    - single-user alpha; anyone with the JWT already has full API access
    Upgrade to pinned-IP transport before multi-user / public launch.
    """
    _validate_fetch_url(url)
    import logging

    log = logging.getLogger(__name__)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=_WEB_CLIP_TIMEOUT,
            headers={"User-Agent": "StratumBot/1.0 (+https://stratum.uex.hk)"},
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code == 404:
                    raise HTTPException(404, "URL not found")
                if resp.status_code in (301, 302, 307, 308):
                    raise HTTPException(400, "URL redirects are not followed; use the final URL")
                resp.raise_for_status()
                cl = resp.headers.get("content-length")
                if cl and int(cl) > _WEB_CLIP_MAX_BYTES:
                    raise HTTPException(413, "Page too large (max 10 MB)")
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > _WEB_CLIP_MAX_BYTES:
                        raise HTTPException(413, "Page too large (max 10 MB)")
                encoding = resp.encoding or "utf-8"
                return buf.decode(encoding, errors="replace")
    except HTTPException:
        raise
    except httpx.TimeoutException:
        log.warning("web_clip_timeout url=%s", url)
        raise HTTPException(504, "URL fetch timed out")
    except httpx.HTTPStatusError as exc:
        log.warning("web_clip_http_error status=%s url=%s", exc.response.status_code, url)
        raise HTTPException(exc.response.status_code, "URL fetch failed")
    except Exception as exc:
        log.warning("web_clip_fetch_error url=%s error=%s", url, exc)
        raise HTTPException(502, "Failed to fetch URL")


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
    substrate_id = _extract_id(findings.substrate_id) if findings else None

    # Write substrate into Stratum's own DB (substrates table, plural).
    # oskill's internal INSERT targets the old 'substrate' (singular) table
    # which was renamed during Phase 14 DB merge — it fails silently.
    # This ensures the substrate is visible to /api/substrates (stratum-api).
    if substrate_id and result.get("status") != "failed":
        omodul_title = getattr(findings, "title", None)
        medium = getattr(findings, "medium", "webpage") or "webpage"
        page_count = getattr(findings, "page_count", 0) or 0
        byte_size = clip_path.stat().st_size if clip_path.exists() else 0
        stored_title = display_title or omodul_title or url
        meta = {
            "source_url": url,
            "medium": medium,
            "tags": parsed_tags,
            "fetch_mode": fetch_mode,
        }
        if note:
            meta["note"] = note
        try:
            db_insert(
                "substrates",
                {
                    "id": substrate_id,
                    "user_id": user_id,
                    "title": stored_title,
                    "mime": f"text/html; medium={medium}",
                    "source_path": str(clip_path),
                    "file_hash": checksum,
                    "byte_size": byte_size,
                    "page_count": page_count,
                    "is_pinned": False,
                    "meta_json": json.dumps(meta),
                    "created_at": now_utc(),
                    "updated_at": now_utc(),
                },
            )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "web_clip_db_insert_failed substrate_id=%s error=%s", substrate_id, exc
            )

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
