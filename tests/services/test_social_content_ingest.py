from __future__ import annotations

import pytest

from stratum.services.social_content_ingest import (
    SocialContentIngestError,
    SocialContentRequest,
    ingest_social_content_async,
)


SOURCE = "https://www.xiaohongshu.com/explore/note-1"


@pytest.mark.asyncio
async def test_body_is_ingested_before_attachments_and_provenance_is_shared() -> None:
    calls: list[tuple[str, object]] = []

    def body_ingester(request, body):
        calls.append(("body", (request.source_url, body)))
        return "substrate-1"

    def image_ingester(url, substrate_id, source_url, provenance):
        calls.append(("image", (url, substrate_id, source_url, provenance)))
        return {"asset_id": "asset-1"}

    async def media_dispatcher(job):
        calls.append(("media", job))
        return {"status": "completed", "substrate_id": "media-1"}

    result = await ingest_social_content_async(
        SocialContentRequest(
            authenticated_user="user-hash",
            source_platform="xiaohongshu",
            source_url=SOURCE,
            body="A post body",
            attachments=[
                {"url": "https://cdn.example/image.jpg", "kind": "image"},
                {"url": "https://cdn.example/video.mp4", "kind": "video"},
            ],
        ),
        body_ingester=body_ingester,
        image_ingester=image_ingester,
        media_dispatcher=media_dispatcher,
    )

    assert result["status"] == "completed"
    assert result["parent_substrate_id"] == "substrate-1"
    assert [kind for kind, _ in calls] == ["body", "image", "media"]
    image_provenance = calls[1][1][3]
    assert image_provenance == {
        "parent_substrate_id": "substrate-1",
        "source_platform": "xiaohongshu",
        "source_url": SOURCE,
        "attachment_url": "https://cdn.example/image.jpg",
    }
    job = calls[2][1]
    assert job.source_metadata["parent_substrate_id"] == "substrate-1"
    assert job.source_metadata["attachment_url"] == "https://cdn.example/video.mp4"


@pytest.mark.asyncio
async def test_body_failure_creates_no_orphan_attachments() -> None:
    attachment_calls = 0

    def body_ingester(_request, _body):
        raise RuntimeError("canonical writer failed")

    def image_ingester(*_args):
        nonlocal attachment_calls
        attachment_calls += 1
        return {"asset_id": "should-not-exist"}

    result = await ingest_social_content_async(
        SocialContentRequest(
            authenticated_user="user-hash",
            source_platform="x",
            source_url="https://x.com/user/status/1",
            body="body",
            attachments=[{"url": "https://cdn.example/image.jpg", "kind": "image"}],
        ),
        body_ingester=body_ingester,
        image_ingester=image_ingester,
    )

    assert result["status"] == "failed"
    assert result["substrate_id"] is None
    assert result["attachments"] == []
    assert attachment_calls == 0
    assert result["errors"][0]["stage"] == "body"


@pytest.mark.asyncio
async def test_attachment_failure_preserves_body_and_returns_structured_error() -> None:
    async def media_dispatcher(_job):
        return {"status": "failed", "error": "runtime unavailable"}

    result = await ingest_social_content_async(
        SocialContentRequest(
            authenticated_user="user-hash",
            source_platform="x",
            source_url="https://x.com/user/status/1",
            body="body",
            attachments=[{"url": "https://cdn.example/audio.mp3", "kind": "audio"}],
        ),
        body_ingester=lambda _request, _body: "substrate-1",
        media_dispatcher=media_dispatcher,
    )

    assert result["status"] == "partial"
    assert result["substrate_id"] == "substrate-1"
    assert result["errors"] == [
        {
            "stage": "attachment",
            "kind": "audio",
            "attachment_url": "https://cdn.example/audio.mp3",
            "error": "runtime unavailable",
        }
    ]


@pytest.mark.parametrize(
    "case",
    [
        SocialContentRequest("u", "youtube", SOURCE),
        SocialContentRequest("u", "x", SOURCE),
        SocialContentRequest("u", "x", "not-a-url"),
        SocialContentRequest(
            "u",
            "x",
            "https://x.com/u/status/1",
            attachments=[{"url": "https://cdn/x", "kind": "pdf"}],
        ),
    ],
)
def test_malformed_or_unsupported_sources_fail_closed(case) -> None:
    with pytest.raises(SocialContentIngestError):
        # Validation runs before the first await and therefore before any I/O.
        import asyncio

        asyncio.run(ingest_social_content_async(case))
