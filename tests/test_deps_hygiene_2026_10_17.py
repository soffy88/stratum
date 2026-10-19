"""Regression tests for chore/deps-hygiene-2026-10-17 (audit 🟡15 / 🟡21)."""

from __future__ import annotations

import asyncio
import time

from stratum.common import DedupCache
from stratum.middleware import rate_limit as rl
from stratum.services import web_fetch_enhanced as wfe


def _ok(url: str) -> wfe.FetchResult:
    return wfe.FetchResult(
        html="<html><title>t</title></html>",
        title="t",
        strategy_used="direct",
        content_type="generic",
        source_url=url,
        success=True,
        error=None,
    )


def test_wechat_twitter_paywall_degrade_explicitly(monkeypatch):
    async def fake_direct(url, timeout, max_bytes):
        return _ok(url)

    monkeypatch.setattr(wfe, "_fetch_direct", fake_direct)
    before = wfe.get_fetch_metrics()

    r1 = asyncio.run(wfe.fetch_url_enhanced("https://mp.weixin.qq.com/s/abc"))
    r2 = asyncio.run(wfe.fetch_url_enhanced("https://example.com/x", strategy="twitter"))
    r3 = asyncio.run(wfe.fetch_url_enhanced("https://www.nytimes.com/a"))

    assert r1.strategy_used == "direct_degraded_wechat"
    assert r2.strategy_used == "direct_degraded_twitter"
    assert r3.strategy_used == "direct_degraded_paywall"
    after = wfe.get_fetch_metrics()
    for kind in ("wechat", "twitter", "paywall"):
        assert after.get(f"degraded:{kind}", 0) == before.get(f"degraded:{kind}", 0) + 1
    assert not hasattr(wfe, "_fetch_with_bypass")


def test_generic_url_uses_direct(monkeypatch):
    async def fake_direct(url, timeout, max_bytes):
        return _ok(url)

    monkeypatch.setattr(wfe, "_fetch_direct", fake_direct)
    r = asyncio.run(wfe.fetch_url_enhanced("https://example.com/"))
    assert r.success and r.strategy_used == "direct"


def test_dedup_cache_is_bounded():
    cache = DedupCache(max_entries=5)

    async def run():
        for i in range(50):
            await cache.set(f"k{i}", i, ttl=60)
        assert len(cache) == 5
        assert await cache.get("k49") == 49
        assert await cache.get("k0") is None

    asyncio.run(run())


def test_dedup_cache_purges_expired_when_full():
    cache = DedupCache(max_entries=3)

    async def run():
        await cache.set("old1", 1, ttl=-1)
        await cache.set("old2", 2, ttl=-1)
        await cache.set("live", 3, ttl=60)
        await cache.set("new", 4, ttl=60)
        assert await cache.get("live") == 3
        assert await cache.get("new") == 4
        assert len(cache) == 2

    asyncio.run(run())


def test_rate_limit_windows_bounded_and_ttl():
    w = rl._BoundedWindows(list, max_keys=3, idle_ttl=3600)
    for i in range(10):
        w[f"ip{i}"].append(1)
    assert len(w) == 3 and "ip9" in w and "ip0" not in w

    w2 = rl._BoundedWindows(list, max_keys=100, idle_ttl=0.01)
    w2["a"]
    time.sleep(0.02)
    w2["b"]
    assert "a" not in w2 and "b" in w2


def test_aii_rate_limit_still_enforces():
    rl.reset_rate_limits()
    key = "testkey-" + "x" * 8
    allowed = [rl._aii_rate_limit(key, "/api/aii/api/chat") for _ in range(25)]
    assert allowed.count(True) == rl._AII_CHAT_LIMIT[1]
    rl.reset_rate_limits()
