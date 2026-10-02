"""Podcast feed assembly over canonical 3O primitives.

Fetching and RSS parsing remain owned by oprim. Stratum only validates the
result and projects podcast episodes into its existing media-ingest contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any, Callable

FetchFn = Callable[..., dict[str, Any]]
ParseFn = Callable[..., dict[str, Any]]


class PodcastFeedError(RuntimeError):
    """Raised when canonical podcast discovery cannot produce trusted episodes."""


@dataclass(frozen=True)
class PodcastFeedRequest:
    feed_url: str
    max_episodes: int = 20


def resolve_podcast_feed(
    req: PodcastFeedRequest,
    *,
    fetch_fn: FetchFn | None = None,
    parse_fn: ParseFn | None = None,
) -> dict[str, Any]:
    """Fetch and parse a podcast feed through the existing 3O authorities."""
    if not req.feed_url.strip():
        raise PodcastFeedError("feed_url is required")
    if req.max_episodes < 1 or req.max_episodes > 100:
        raise PodcastFeedError("max_episodes must be between 1 and 100")

    if fetch_fn is None or parse_fn is None:
        try:
            oprim = importlib.import_module("oprim")
            canonical_fetch = getattr(oprim, "url_fetch_ssrf_safe")
            canonical_parse = getattr(oprim, "podcast_episode_parser")
        except (ImportError, AttributeError) as exc:
            raise PodcastFeedError("oprim podcast primitives unavailable") from exc
        fetch_fn = fetch_fn or canonical_fetch
        parse_fn = parse_fn or canonical_parse

    fetched = fetch_fn(
        url=req.feed_url.strip(),
        timeout=20,
        max_bytes=8 * 1024 * 1024,
        headers={"User-Agent": "StratumBot/1.0"},
    )
    if fetched.get("error"):
        raise PodcastFeedError(f"feed fetch failed: {fetched['error']}")
    xml = fetched.get("body_text")
    if not isinstance(xml, str) or not xml.strip():
        raise PodcastFeedError("feed fetch returned no XML text")

    parsed = parse_fn(xml=xml, max_episodes=req.max_episodes)
    if parsed.get("error"):
        raise PodcastFeedError(f"feed parse failed: {parsed['error']}")

    episodes: list[dict[str, Any]] = []
    for episode in parsed.get("episodes") or []:
        enclosure_url = str(episode.get("enclosure_url") or "").strip()
        if not enclosure_url:
            continue
        enclosure_type = str(episode.get("enclosure_type") or "").lower()
        if enclosure_type and not enclosure_type.startswith("audio/"):
            continue
        episodes.append(
            {
                "title": episode.get("title"),
                "episode_url": episode.get("link"),
                "media_url": enclosure_url,
                "guid": episode.get("guid"),
                "pub_date": episode.get("pub_date"),
                "duration": episode.get("duration"),
                "enclosure_type": episode.get("enclosure_type"),
                "enclosure_length": episode.get("enclosure_length"),
                "platform": "podcast",
            }
        )

    return {
        "feed_url": req.feed_url.strip(),
        "podcast_title": parsed.get("podcast_title"),
        "podcast_author": parsed.get("podcast_author"),
        "podcast_description": parsed.get("podcast_description"),
        "episode_count": len(episodes),
        "episodes": episodes,
        "authority": "oprim",
    }


def podcast_media_ingest_jobs(feed: dict[str, Any]) -> list[dict[str, Any]]:
    """Project resolved episodes into the existing Stratum media-ingest input shape."""
    jobs: list[dict[str, Any]] = []
    for episode in feed.get("episodes") or []:
        media_url = str(episode.get("media_url") or "").strip()
        if not media_url:
            continue
        jobs.append(
            {
                "url": media_url,
                "kind": "audio",
                "provider": "local",
                "transcribe": True,
                "source_platform": "podcast",
                "source_feed_url": feed.get("feed_url"),
                "source_episode_url": episode.get("episode_url"),
                "source_guid": episode.get("guid"),
                "title": episode.get("title"),
            }
        )
    return jobs

async def dispatch_podcast_feed_async(
    req: PodcastFeedRequest,
    user_id_hash: str,
    *,
    resolve_fn: Callable[..., dict[str, Any]] = resolve_podcast_feed,
    dispatch_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Resolve a podcast and dispatch every audio enclosure through media_runtime."""
    if not user_id_hash.strip():
        raise PodcastFeedError("user_id_hash is required")

    from stratum.services.media_runtime import MediaRuntimeJob, dispatch_media_job_async

    feed = resolve_fn(req)
    jobs = podcast_media_ingest_jobs(feed)
    dispatch = dispatch_fn or dispatch_media_job_async
    results: list[dict[str, Any]] = []
    for item in jobs:
        source_metadata = {
            "source_platform": "podcast",
            "source_feed_url": item.get("source_feed_url"),
            "source_episode_url": item.get("source_episode_url"),
            "source_guid": item.get("source_guid"),
            "source_title": item.get("title"),
        }
        value = dispatch(
            MediaRuntimeJob(
                url=str(item["url"]),
                user_id_hash=user_id_hash,
                kind="audio",
                asr_backend=str(item.get("provider") or "local"),
                transcribe=bool(item.get("transcribe", True)),
                source_metadata=source_metadata,
            )
        )
        result = await value if hasattr(value, "__await__") else value
        results.append(dict(result))

    completed = sum(1 for result in results if result.get("status") == "completed")
    failed = len(results) - completed
    if not results or failed == 0:
        status = "completed"
    elif completed:
        status = "partial"
    else:
        status = "failed"
    return {
        "status": status,
        "feed_url": feed.get("feed_url"),
        "podcast_title": feed.get("podcast_title"),
        "episode_count": feed.get("episode_count", 0),
        "dispatched_count": len(results),
        "completed_count": completed,
        "failed_count": failed,
        "results": results,
        "authority": "media_runtime",
    }

