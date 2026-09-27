from __future__ import annotations

import asyncio

import pytest

from stratum.services.media_runtime import (
    MediaRuntimeError,
    MediaRuntimeJob,
    dispatch_media_job,
    dispatch_media_job_async,
)


class FakeConfig:
    def __init__(self, **kwargs):
        self.values = kwargs


class FakeInput:
    pass


@pytest.mark.asyncio
async def test_media_runtime_builds_platform_config_and_projects_metadata(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("STRATUM_MEDIA_COOKIE_BILIBILI", "/tmp/bili-cookie.txt")

    async def processor(*, config, input_data, output_dir):
        captured["config"] = config.values
        assert isinstance(input_data, FakeInput)
        assert output_dir.exists()
        return {
            "status": "completed",
            "substrate_id": "sid-1",
            "title": "Episode",
            "has_subtitle": True,
        }

    def projector(*, result, job, platform):
        captured["projected_result"] = result
        captured["job"] = job
        captured["platform"] = platform

    job = MediaRuntimeJob(
        url="https://www.bilibili.com/video/BV1xx",
        user_id_hash="user-hash",
        kind="video",
        source_metadata={"parent_substrate_id": "parent-1"},
    )
    result = await dispatch_media_job_async(
        job,
        config_factory=FakeConfig,
        input_factory=FakeInput,
        processor=processor,
        projector=projector,
    )

    assert result["status"] == "completed"
    assert result["platform"] == "bilibili"
    assert captured["config"]["video_url"] == job.url
    assert captured["config"]["user_id_hash"] == "user-hash"
    assert captured["config"]["transcribe_if_no_subtitle"] is True
    assert captured["config"]["cookies_path"] == "/tmp/bili-cookie.txt"
    assert captured["job"].source_metadata == {"parent_substrate_id": "parent-1"}
    assert captured["platform"] == "bilibili"


@pytest.mark.asyncio
async def test_media_runtime_processor_failure_is_reported() -> None:
    async def processor(**_):
        raise RuntimeError("provider down")

    result = await dispatch_media_job_async(
        MediaRuntimeJob("https://x.com/u/status/1", "u"),
        config_factory=FakeConfig,
        input_factory=FakeInput,
        processor=processor,
    )
    assert result["status"] == "failed"
    assert result["platform"] == "x"
    assert result["error"] == "provider down"


@pytest.mark.asyncio
async def test_media_runtime_projection_failure_fails_closed() -> None:
    async def processor(**_):
        return {"status": "completed", "substrate_id": "sid-1"}

    def projector(**_):
        raise RuntimeError("db projection failed")

    result = await dispatch_media_job_async(
        MediaRuntimeJob("https://example.com/a.mp3", "u", kind="audio"),
        config_factory=FakeConfig,
        input_factory=FakeInput,
        processor=processor,
        projector=projector,
    )
    assert result["status"] == "failed"
    assert result["error"] == "projection_failed: db projection failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job,error",
    [
        (MediaRuntimeJob("", "u"), "media url is required"),
        (MediaRuntimeJob("https://example.com/v", ""), "user_id_hash is required"),
        (MediaRuntimeJob("https://example.com/v", "u", kind="image"), "kind must be video or audio"),
    ],
)
async def test_media_runtime_rejects_invalid_jobs(job, error) -> None:
    with pytest.raises(MediaRuntimeError, match=error):
        await dispatch_media_job_async(
            job,
            config_factory=FakeConfig,
            input_factory=FakeInput,
            processor=lambda **_: {},
        )


def test_sync_media_runtime_wrapper() -> None:
    def processor(**_):
        return {"status": "failed", "error": "fixture"}

    result = dispatch_media_job(
        MediaRuntimeJob("https://example.com/a.mp3", "u", kind="audio"),
        config_factory=FakeConfig,
        input_factory=FakeInput,
        processor=processor,
    )
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_sync_wrapper_refuses_running_event_loop() -> None:
    with pytest.raises(MediaRuntimeError, match="active event loop"):
        dispatch_media_job(MediaRuntimeJob("https://example.com/a.mp3", "u", kind="audio"))
    await asyncio.sleep(0)
