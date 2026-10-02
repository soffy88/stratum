"""Platform metadata and cookie resolution for canonical media ingestion.

The actual extraction/transcription authority remains 3O (oprim/omodul). This
module only maps source URLs to stable Stratum metadata and platform-specific
cookie files so all supported yt-dlp URLs share one ingestion path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class MediaPlatformProfile:
    name: str
    domains: tuple[str, ...]


_PROFILES = (
    MediaPlatformProfile("youtube", ("youtube.com", "youtu.be")),
    MediaPlatformProfile("bilibili", ("bilibili.com", "b23.tv")),
    MediaPlatformProfile("douyin", ("douyin.com", "iesdouyin.com")),
    MediaPlatformProfile("tiktok", ("tiktok.com",)),
    MediaPlatformProfile("weibo", ("weibo.com", "weibo.cn")),
    MediaPlatformProfile("zhihu", ("zhihu.com",)),
    MediaPlatformProfile("xiaohongshu", ("xiaohongshu.com", "xhslink.com")),
    MediaPlatformProfile("x", ("x.com", "twitter.com", "t.co")),
)

_PROFILE_BY_NAME = {profile.name: profile for profile in _PROFILES}


def detect_media_platform(url: str) -> str:
    """Return a stable platform id without restricting generic yt-dlp URLs."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return "generic"
    if host.startswith("www."):
        host = host[4:]
    for profile in _PROFILES:
        if any(host == domain or host.endswith(f".{domain}") for domain in profile.domains):
            return profile.name
    return "generic"


def cookie_path_for_platform(platform: str) -> str | None:
    """Resolve an optional cookie file; absence never blocks public media."""
    if platform not in _PROFILE_BY_NAME:
        return None
    env_key = f"STRATUM_MEDIA_COOKIE_{platform.upper()}"
    configured = str(os.environ.get(env_key) or "").strip()
    if configured:
        return str(Path(configured).expanduser())
    candidate = Path.home() / ".stratum" / f"{platform}_cookies.txt"
    return str(candidate) if candidate.is_file() else None


def canonical_media_metadata(url: str, kind: str) -> dict[str, str]:
    """Metadata projected onto the canonical substrate after successful ingest."""
    return {
        "platform": detect_media_platform(url),
        "source_url": url,
        "medium": kind,
    }
