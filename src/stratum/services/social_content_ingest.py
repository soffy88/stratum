"""Canonical ingest for Xiaohongshu and X social content.

This is deliberately a composition boundary.  Text is written through the
canonical Source/fragment writers, images through the existing multimodal
asset path, and audio/video through ``media_runtime``.  It does not introduce
another downloader, store, index, or MCP authority.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Sequence
from urllib.parse import urlparse

log = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = frozenset({"xiaohongshu", "x"})
_PLATFORM_ALIASES = {
    "xhs": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "twitter": "x",
    "x": "x",
}
_MEDIA_KINDS = frozenset({"audio", "video"})


class SocialContentIngestError(ValueError):
    """Raised when a social ingest request is malformed or unsupported."""


@dataclass(frozen=True)
class SocialAttachment:
    """One attachment from a social post."""

    url: str
    kind: str
    title: str | None = None


@dataclass(frozen=True)
class SocialContentRequest:
    """Validated input for one X or Xiaohongshu post."""

    authenticated_user: str
    source_platform: str
    source_url: str
    body: str | None = None
    title: str | None = None
    attachments: Sequence[SocialAttachment | Mapping[str, Any]] = field(default_factory=tuple)


# Descriptive aliases keep the public boundary discoverable for callers that
# use the longer service name.
SocialContentIngestRequest = SocialContentRequest
SocialIngestRequest = SocialContentRequest


BodyFetcher = Callable[[str, str], str | Awaitable[str]]
BodyIngester = Callable[[SocialContentRequest, str], str | Awaitable[str]]
ImageIngester = Callable[[str, str, str, dict[str, str]], Any]
MediaDispatcher = Callable[[Any], Any]


def _normalise_platform(value: str) -> str:
    platform = _PLATFORM_ALIASES.get(value.strip().lower())
    if platform not in SUPPORTED_PLATFORMS:
        raise SocialContentIngestError("source_platform must be xiaohongshu or x")
    return platform


def _validate_url(value: str, field_name: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SocialContentIngestError(f"{field_name} must be an absolute http(s) URL")
    return url


def _detect_platform(url: str) -> str:
    """Use the canonical platform detector when the P1 media module is present."""
    try:
        from stratum.services.media_platforms import detect_media_platform

        return detect_media_platform(url)
    except ImportError:
        # Keeps this module importable in a partial checkout; production uses
        # the canonical detector above and never takes this compatibility path.
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if host == "x.com" or host.endswith(".x.com") or host in {"twitter.com", "t.co"}:
            return "x"
        if (
            host == "xiaohongshu.com"
            or host.endswith(".xiaohongshu.com")
            or host == "xhslink.com"
        ):
            return "xiaohongshu"
        return "generic"


def _validate_request(request: SocialContentRequest) -> tuple[str, str, list[SocialAttachment]]:
    if not request.authenticated_user.strip():
        raise SocialContentIngestError("authenticated_user is required")
    platform = _normalise_platform(request.source_platform)
    source_url = _validate_url(request.source_url, "source_url")
    detected = _detect_platform(source_url)
    if detected != platform:
        raise SocialContentIngestError("source_url does not belong to source_platform")

    attachments: list[SocialAttachment] = []
    for raw in request.attachments:
        if isinstance(raw, SocialAttachment):
            attachment = raw
        elif isinstance(raw, Mapping):
            attachment = SocialAttachment(
                url=str(raw.get("url") or raw.get("attachment_url") or ""),
                kind=str(raw.get("kind") or raw.get("type") or "").lower(),
                title=str(raw.get("title") or "") or None,
            )
        else:
            raise SocialContentIngestError("attachments must contain objects")
        url = _validate_url(attachment.url, "attachment_url")
        kind = attachment.kind.lower().strip()
        if kind != "image" and kind not in _MEDIA_KINDS:
            raise SocialContentIngestError("attachment kind must be image, video, or audio")
        attachments.append(SocialAttachment(url=url, kind=kind, title=attachment.title))
    return platform, source_url, attachments


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def _fetch_body(source_url: str, platform: str) -> str:
    """Use the existing enhanced web path, including Crawl4AI for XHS."""
    from stratum.services.web_fetch_enhanced import fetch_url_enhanced

    strategy = "crawl4ai" if platform == "xiaohongshu" else "twitter"
    result = await fetch_url_enhanced(source_url, strategy=strategy)
    if not result.success or not result.html:
        raise SocialContentIngestError(result.error or "social body fetch failed")
    return result.html.strip()


def _ingest_body(request: SocialContentRequest, body: str) -> str:
    """Create the canonical substrate and fragments before any attachment."""
    from stratum.services.canonical_fragment_writer import ensure_canonical_fragments
    from stratum.services.canonical_source_writer import CanonicalSourceWriter

    metadata = {
        "parent_substrate_id": None,
        "source_platform": _normalise_platform(request.source_platform),
        "source_url": request.source_url,
    }
    created = CanonicalSourceWriter().create(
        authenticated_user=request.authenticated_user,
        source_type="social",
        title=(request.title or request.source_url).strip(),
        mime="text/markdown",
        original_binary_uri=None,
        file_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        metadata=metadata,
    )
    substrate_id = str(created["id"])
    ensure_canonical_fragments(substrate_id, request.authenticated_user, content=body)
    return substrate_id


def _ingest_image(
    url: str, substrate_id: str, source_url: str, provenance: dict[str, str]
) -> dict[str, Any]:
    """Fetch one image and use the existing ImageAsset persistence boundary."""
    import httpx

    from stratum.services.multimodal_extraction import (
        ImageAsset,
        _describe_image_vlm,
        _get_embedding,
        persist_image_asset,
    )

    del source_url
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    content = response.content
    if not content:
        raise SocialContentIngestError("image response was empty")
    asset_id = hashlib.sha256(f"{substrate_id}:{url}".encode()).hexdigest()[:24]
    description = _describe_image_vlm(content)
    asset = ImageAsset(
        asset_id=asset_id,
        substrate_id=substrate_id,
        page_num=0,
        bbox=(0.0, 0.0, 0.0, 0.0),
        width=0,
        height=0,
        format="jpeg" if response.headers.get("content-type", "").endswith("jpeg") else "png",
        vlm_description=description,
        thumbnail_b64=base64.b64encode(content).decode("ascii"),
        embedding=_get_embedding(description) if description else None,
    )
    persist_image_asset(asset)
    return {"asset_id": asset_id, "attachment_url": url, **provenance}


async def ingest_social_content_async(
    request: SocialContentRequest,
    *,
    body_fetcher: BodyFetcher | None = None,
    body_ingester: BodyIngester | None = None,
    image_ingester: ImageIngester | None = None,
    media_dispatcher: MediaDispatcher | None = None,
) -> dict[str, Any]:
    """Ingest body first, then best-effort attachments with structured errors."""
    platform, source_url, attachments = _validate_request(request)
    body = request.body.strip() if isinstance(request.body, str) else ""
    if not body:
        try:
            body = str(
                await _maybe_await((body_fetcher or _fetch_body)(source_url, platform))
            ).strip()
        except Exception as exc:
            return {
                "status": "failed",
                "substrate_id": None,
                "attachments": [],
                "errors": [{"stage": "body", "error": str(exc)}],
            }
    if not body:
        return {
            "status": "failed",
            "substrate_id": None,
            "attachments": [],
            "errors": [{"stage": "body", "error": "body is empty"}],
        }

    try:
        substrate_id = str(await _maybe_await((body_ingester or _ingest_body)(request, body)))
    except Exception as exc:
        log.exception("social body ingest failed url=%s", source_url)
        return {
            "status": "failed",
            "substrate_id": None,
            "attachments": [],
            "errors": [{"stage": "body", "error": str(exc)}],
        }
    if not substrate_id.strip():
        return {
            "status": "failed",
            "substrate_id": None,
            "attachments": [],
            "errors": [
                {
                    "stage": "body",
                    "error": "body ingester returned no substrate_id",
                }
            ],
        }

    provenance = {
        "parent_substrate_id": substrate_id,
        "source_platform": platform,
        "source_url": source_url,
    }
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for attachment in attachments:
        try:
            if attachment.kind == "image":
                value = (image_ingester or _ingest_image)(
                    attachment.url,
                    substrate_id,
                    source_url,
                    {**provenance, "attachment_url": attachment.url},
                )
            else:
                if media_dispatcher is None:
                    from stratum.services.media_runtime import (
                        MediaRuntimeJob,
                        dispatch_media_job_async,
                    )

                    job = MediaRuntimeJob(
                        url=attachment.url,
                        user_id_hash=request.authenticated_user,
                        kind=attachment.kind,
                        source_metadata={**provenance, "attachment_url": attachment.url},
                    )
                    value = dispatch_media_job_async(job)
                else:
                    from types import SimpleNamespace

                    job = SimpleNamespace(
                        url=attachment.url,
                        user_id_hash=request.authenticated_user,
                        kind=attachment.kind,
                        source_metadata={**provenance, "attachment_url": attachment.url},
                    )
                    value = media_dispatcher(job)
            result = dict(await _maybe_await(value))
            result.setdefault("status", "completed")
            results.append(
                {
                    "kind": attachment.kind,
                    "attachment_url": attachment.url,
                    **result,
                    **provenance,
                }
            )
            if result.get("status") not in {"completed", "success"}:
                errors.append(
                    {
                        "stage": "attachment",
                        "kind": attachment.kind,
                        "attachment_url": attachment.url,
                        "error": result.get("error", "attachment failed"),
                    }
                )
        except Exception as exc:
            errors.append(
                {
                    "stage": "attachment",
                    "kind": attachment.kind,
                    "attachment_url": attachment.url,
                    "error": str(exc),
                }
            )

    return {
        "status": "partial" if errors else "completed",
        "substrate_id": substrate_id,
        "attachments": results,
        "errors": errors,
        **provenance,
    }


def ingest_social_content(request: SocialContentRequest, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for callers outside an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ingest_social_content_async(request, **kwargs))
    raise SocialContentIngestError("active event loop: use ingest_social_content_async")
