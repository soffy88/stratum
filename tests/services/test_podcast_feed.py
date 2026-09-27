from __future__ import annotations

import pytest

from stratum.services.podcast_feed import (
    PodcastFeedError,
    PodcastFeedRequest,
    dispatch_podcast_feed_async,
    podcast_media_ingest_jobs,
    resolve_podcast_feed,
)


def _fetch(**kwargs):
    assert kwargs["url"] == "https://example.com/feed.xml"
    assert kwargs["max_bytes"] == 8 * 1024 * 1024
    return {"body_text": "<rss />", "error": None}


def _parse(**kwargs):
    assert kwargs["xml"] == "<rss />"
    assert kwargs["max_episodes"] == 10
    return {
        "podcast_title": "Example Podcast",
        "podcast_author": "Author",
        "podcast_description": "Description",
        "error": None,
        "episodes": [
            {
                "title": "Episode 1",
                "link": "https://example.com/ep1",
                "pub_date": "today",
                "duration": "12:34",
                "enclosure_url": "https://cdn.example.com/ep1.mp3",
                "enclosure_type": "audio/mpeg",
                "enclosure_length": 123,
                "guid": "ep1",
            },
            {
                "title": "No enclosure",
                "enclosure_url": None,
                "enclosure_type": None,
            },
            {
                "title": "Video enclosure",
                "enclosure_url": "https://cdn.example.com/ep.mp4",
                "enclosure_type": "video/mp4",
            },
        ],
    }


def test_resolve_podcast_feed_uses_3o_contract_shape() -> None:
    result = resolve_podcast_feed(
        PodcastFeedRequest("https://example.com/feed.xml", max_episodes=10),
        fetch_fn=_fetch,
        parse_fn=_parse,
    )
    assert result["authority"] == "oprim"
    assert result["podcast_title"] == "Example Podcast"
    assert result["episode_count"] == 1
    assert result["episodes"][0]["media_url"] == "https://cdn.example.com/ep1.mp3"
    assert result["episodes"][0]["platform"] == "podcast"


def test_podcast_jobs_reuse_media_ingest_contract() -> None:
    feed = resolve_podcast_feed(
        PodcastFeedRequest("https://example.com/feed.xml", max_episodes=10),
        fetch_fn=_fetch,
        parse_fn=_parse,
    )
    jobs = podcast_media_ingest_jobs(feed)
    assert jobs == [
        {
            "url": "https://cdn.example.com/ep1.mp3",
            "kind": "audio",
            "provider": "local",
            "transcribe": True,
            "source_platform": "podcast",
            "source_feed_url": "https://example.com/feed.xml",
            "source_episode_url": "https://example.com/ep1",
            "source_guid": "ep1",
            "title": "Episode 1",
        }
    ]


@pytest.mark.parametrize(
    "case",
    [
        PodcastFeedRequest(""),
        PodcastFeedRequest("https://example.com/feed.xml", max_episodes=0),
        PodcastFeedRequest("https://example.com/feed.xml", max_episodes=101),
    ],
)
def test_podcast_request_validation(case) -> None:
    with pytest.raises(PodcastFeedError):
        resolve_podcast_feed(case, fetch_fn=_fetch, parse_fn=_parse)


def test_podcast_fetch_failure_is_fail_closed() -> None:
    with pytest.raises(PodcastFeedError, match="feed fetch failed"):
        resolve_podcast_feed(
            PodcastFeedRequest("https://example.com/feed.xml"),
            fetch_fn=lambda **_: {"error": "ssrf_blocked"},
            parse_fn=_parse,
        )


def test_podcast_parse_failure_is_fail_closed() -> None:
    with pytest.raises(PodcastFeedError, match="feed parse failed"):
        resolve_podcast_feed(
            PodcastFeedRequest("https://example.com/feed.xml"),
            fetch_fn=_fetch,
            parse_fn=lambda **_: {"error": "xml_parse_error"},
        )

@pytest.mark.asyncio
async def test_dispatch_podcast_feed_uses_media_runtime_and_preserves_provenance() -> None:
    captured = []

    def resolve(_req):
        return {
            "feed_url": "https://example.com/feed.xml",
            "podcast_title": "Example Podcast",
            "episode_count": 1,
            "episodes": [
                {
                    "title": "Episode 1",
                    "episode_url": "https://example.com/ep1",
                    "media_url": "https://cdn.example.com/ep1.mp3",
                    "guid": "ep1",
                }
            ],
        }

    async def dispatch(job):
        captured.append(job)
        return {"status": "completed", "substrate_id": "sid-media-1"}

    result = await dispatch_podcast_feed_async(
        PodcastFeedRequest("https://example.com/feed.xml"),
        "user-hash",
        resolve_fn=resolve,
        dispatch_fn=dispatch,
    )
    assert result["status"] == "completed"
    assert result["completed_count"] == 1
    assert result["authority"] == "media_runtime"
    assert len(captured) == 1
    job = captured[0]
    assert job.url == "https://cdn.example.com/ep1.mp3"
    assert job.kind == "audio"
    assert job.user_id_hash == "user-hash"
    assert job.source_metadata == {
        "source_platform": "podcast",
        "source_feed_url": "https://example.com/feed.xml",
        "source_episode_url": "https://example.com/ep1",
        "source_guid": "ep1",
        "source_title": "Episode 1",
    }


@pytest.mark.asyncio
async def test_dispatch_podcast_feed_partial_status() -> None:
    def resolve(_req):
        return {
            "feed_url": "https://example.com/feed.xml",
            "episode_count": 2,
            "episodes": [
                {"title": "A", "media_url": "https://cdn.example.com/a.mp3"},
                {"title": "B", "media_url": "https://cdn.example.com/b.mp3"},
            ],
        }

    calls = 0

    async def dispatch(_job):
        nonlocal calls
        calls += 1
        return {"status": "completed" if calls == 1 else "failed"}

    result = await dispatch_podcast_feed_async(
        PodcastFeedRequest("https://example.com/feed.xml"),
        "user-hash",
        resolve_fn=resolve,
        dispatch_fn=dispatch,
    )
    assert result["status"] == "partial"
    assert result["completed_count"] == 1
    assert result["failed_count"] == 1


@pytest.mark.asyncio
async def test_dispatch_podcast_feed_requires_user_hash() -> None:
    with pytest.raises(PodcastFeedError, match="user_id_hash is required"):
        await dispatch_podcast_feed_async(
            PodcastFeedRequest("https://example.com/feed.xml"),
            "",
            resolve_fn=lambda _: {},
        )

