from __future__ import annotations

import sys
import types

import pytest

from stratum.services.media_platforms import (
    canonical_media_metadata,
    cookie_path_for_platform,
    detect_media_platform,
)


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.youtube.com/watch?v=x", "youtube"),
        ("https://b23.tv/abc", "bilibili"),
        ("https://www.douyin.com/video/1", "douyin"),
        ("https://www.tiktok.com/@u/video/1", "tiktok"),
        ("https://weibo.com/tv/show/1", "weibo"),
        ("https://www.zhihu.com/zvideo/1", "zhihu"),
        ("https://www.xiaohongshu.com/explore/1", "xiaohongshu"),
        ("https://x.com/user/status/1", "x"),
    ],
)
def test_detect_media_platform(url: str, platform: str) -> None:
    assert detect_media_platform(url) == platform


def test_unknown_media_platform_stays_generic() -> None:
    assert detect_media_platform("https://media.example.org/watch/1") == "generic"


def test_cookie_path_uses_platform_specific_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATUM_MEDIA_COOKIE_BILIBILI", "~/cookies/bili.txt")
    monkeypatch.setenv("STRATUM_MEDIA_COOKIE_YOUTUBE", "~/cookies/youtube.txt")
    assert cookie_path_for_platform("bilibili").endswith("/cookies/bili.txt")
    assert not cookie_path_for_platform("bilibili").endswith("/cookies/youtube.txt")


def test_cookie_path_falls_back_only_when_platform_file_exists(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cookie = tmp_path / ".stratum" / "douyin_cookies.txt"
    cookie.parent.mkdir()
    cookie.write_text("cookie", encoding="utf-8")
    assert cookie_path_for_platform("douyin") == str(cookie)
    assert cookie_path_for_platform("youtube") is None
    assert cookie_path_for_platform("generic") is None


def test_canonical_media_metadata_preserves_source() -> None:
    url = "https://www.bilibili.com/video/BV1xx"
    assert canonical_media_metadata(url, "video") == {
        "platform": "bilibili",
        "source_url": url,
        "medium": "video",
    }


def test_media_ingest_passes_platform_cookie_to_3o(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from stratum.api.routers import media

    captured: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeInput:
        pass

    async def fake_process_media_substrate(*, config, input_data, output_dir):
        assert config is not None
        assert input_data is not None
        assert output_dir.exists()
        return {"status": "failed", "error": "fixture-stop"}

    package = types.ModuleType("omodul")
    module = types.ModuleType("omodul.process_media_substrate")
    module.MediaConfig = FakeConfig
    module.MediaInput = FakeInput
    module.process_media_substrate = fake_process_media_substrate
    monkeypatch.setitem(sys.modules, "omodul", package)
    monkeypatch.setitem(sys.modules, "omodul.process_media_substrate", module)
    cookie = tmp_path / "bili.txt"
    monkeypatch.setenv("STRATUM_MEDIA_COOKIE_BILIBILI", str(cookie))

    url = "https://www.bilibili.com/video/BV1xx"
    media._run_ingest(url, "user-hash", "video", "local", True)

    assert captured["video_url"] == url
    assert captured["cookies_path"] == str(cookie)
    assert captured["transcribe_if_no_subtitle"] is True
