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


def _extract_source_metadata(findings: object, fallback_source: str | None = None) -> dict:
    """Return {source, published_at} from omodul findings, falling back to provided values."""
    source = (
        getattr(findings, "source_url", None)
        or getattr(findings, "source", None)
        or fallback_source
    )
    published_at = getattr(findings, "published_at", None) or getattr(
        findings, "creation_date", None
    )
    return {"source": source, "published_at": published_at}


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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

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

_DERIVATIVE_AGENT_MAP: dict[str, str] = {
    "translation": "translation_worker",
    "audio": "audio_generator",
    "illustration": "illustration_agent",
}


async def _run_agent_background(agent_name: str, params: dict, user_id: str) -> None:
    """Fire-and-forget: run an omodul agent after upload without blocking the response."""
    try:
        if not _HAS_INBOX:
            return
        import os
        from datetime import datetime, timezone
        from omodul.knowledge.agents.base import AgentContext

        if agent_name == "translation_worker":
            from omodul.knowledge.agents.builtin.translation_worker import (
                TranslationWorkerAgent as _Cls,
            )
        elif agent_name == "audio_generator":
            from omodul.knowledge.agents.builtin.audio_generator import AudioGeneratorAgent as _Cls
        elif agent_name == "illustration_agent":
            from omodul.knowledge.agents.builtin.illustration_agent import IllustrationAgent as _Cls
        else:
            return
        context = AgentContext(
            user_id=user_id,
            agent_run_id=generate_ulid(),
            invoked_at=datetime.now(timezone.utc),
        )
        agent = _Cls()
        agent.llm_provider = os.environ.get("STRATUM_LLM_PROVIDER", "qwen3_dashscope")
        agent.llm_model = os.environ.get("STRATUM_LLM_MODEL", "qwen-plus")
        enriched = dict(params)
        enriched.setdefault("corpus_id", f"user_{user_id}")
        await agent.run(enriched, context)
    except Exception as exc:
        logging.getLogger(__name__).warning("bg_agent_failed name=%s error=%s", agent_name, exc)


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

try:
    from stratum.services.graph_builder_service import build_graph_from_substrate as _build_graph
    _HAS_GRAPH = True
except ImportError:
    _HAS_GRAPH = False


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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    medium_hint: str = Form(None),
    title_override: str = Form(None),
    tags: str = Form(None),
    derivatives: list[str] | None = Form(None),
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
    substrate_id = _extract_id(findings.substrate_id) if findings else None
    stored_title = "untitled"
    derivatives_queued: list[str] = []

    # UPDATE title + populate derivative.content from omodul findings.
    if substrate_id and result.get("status") != "failed":
        stored_title = (
            (title_override.strip() if title_override and title_override.strip() else None)
            or file.filename
            or (getattr(findings, "title", None) if findings else None)
            or "untitled"
        )
        source_meta = (
            _extract_source_metadata(findings, fallback_source=file.filename)
            if findings
            else {"source": file.filename, "published_at": None}
        )
        update_data = {"title": stored_title, "updated_at": now_utc()}
        if source_meta.get("source"):
            update_data["source"] = source_meta["source"]
        if source_meta.get("published_at"):
            update_data["published_at"] = source_meta["published_at"]
        try:
            db_update("substrates", substrate_id, update_data)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "upload_title_update_failed substrate_id=%s error=%s", substrate_id, exc
            )
        if findings:
            _fill_derivative_content(substrate_id, findings)
            from stratum.services.md_export_service import export_one
            export_one(substrate_id)
        if substrate_id and _HAS_GRAPH:
            background_tasks.add_task(
                _build_graph,
                substrate_id=substrate_id,
                user_id_hash=hash_user_id(user_id),
            )
        # Schedule optional derivative agents as background tasks.
        for d in derivatives or []:
            agent_name = _DERIVATIVE_AGENT_MAP.get(d)
            if agent_name:
                background_tasks.add_task(
                    _run_agent_background,
                    agent_name,
                    {"substrate_id": substrate_id},
                    user_id,
                )
                derivatives_queued.append(d)

    response = {
        "upload_id": checksum[:12],
        "substrate_id": substrate_id,
        "title": stored_title,
        "medium": str(findings.medium) if findings else medium_hint,
        "status": result.get("status", "completed"),
        "derivatives_queued": derivatives_queued,
    }
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
    background_tasks: BackgroundTasks,
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
        source_meta = (
            _extract_source_metadata(findings, fallback_source=url)
            if findings
            else {"source": url, "published_at": None}
        )
        wc_update = {"title": stored_title, "updated_at": now_utc()}
        if source_meta.get("source"):
            wc_update["source"] = source_meta["source"]
        if source_meta.get("published_at"):
            wc_update["published_at"] = source_meta["published_at"]
        try:
            db_update("substrates", substrate_id, wc_update)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "web_clip_title_update_failed substrate_id=%s error=%s", substrate_id, exc
            )
        if findings:
            _fill_derivative_content(substrate_id, findings)
            from stratum.services.md_export_service import export_one
            export_one(substrate_id)
        if substrate_id and _HAS_GRAPH:
            background_tasks.add_task(
                _build_graph,
                substrate_id=substrate_id,
                user_id_hash=hash_user_id(user_id),
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
