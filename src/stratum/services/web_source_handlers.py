"""stratum.services.web_source_handlers — WeChat / Twitter 源抓取.

为 source_watcher 提供 wechat/twitter 源的搜索/抓取能力.

WeChat: 直接 URL 列表 → enhanced fetcher (jina.ai 代理)
Twitter: 用户名/关键词 → r.jina.ai 级联抓取

★ 注意: 微信文章通常无 RSS, 需手动提供 URL 列表或通过第三方 API 发现.
Twitter 同样受反爬限制, jina.ai 是主要获取路径.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from oprim._media_types import SourceResult

log = logging.getLogger(__name__)


async def wechat_fetch_articles(
    urls: list[str] | None = None,
    keyword: str | None = None,
    max_results: int = 10,
    **_kw: Any,
) -> list[SourceResult]:
    """通过 URL 列表抓取微信公众号文章 (jina.ai 代理).

    WeChat 无公开搜索 API, 需用户提供 URL 列表.
    返回的 SourceResult.download_url 指向原文, external_id 为 URL hash.
    """
    if not urls:
        log.warning("wechat_fetch: no urls provided")
        return []

    from stratum.services.web_fetch_enhanced import fetch_url_enhanced

    results: list[SourceResult] = []
    for url in urls[:max_results]:
        try:
            result = await fetch_url_enhanced(url, strategy="wechat")
            if result.success and result.html:
                ext_id = f"wechat_{abs(hash(url)) % 10**12}"
                results.append(SourceResult(
                    external_id=ext_id,
                    title=result.title or f"WeChat Article {ext_id[-8:]}",
                    download_url=url,  # 原文链接
                    file_type="html",
                    metadata={
                        "source_type": "wechat",
                        "url": url,
                        "strategy": result.strategy_used,
                        "content_preview": result.html[:500] if result.html else "",
                    },
                ))
                log.info("wechat_fetch: OK %s title=%s len=%d", ext_id, result.title, len(result.html))
            else:
                log.warning("wechat_fetch: FAIL %s error=%s", url[:60], result.error)
        except Exception as e:
            log.warning("wechat_fetch: ERROR %s %s", url[:60], e)

    return results


async def twitter_fetch_threads(
    usernames: list[str] | None = None,
    keyword: str | None = None,
    max_results: int = 10,
    **_kw: Any,
) -> list[SourceResult]:
    """抓取 X/Twitter 线程 (r.jina.ai 代理).

    ★ 限制: jina.ai 对 twitter 抓取不稳定, 结果可能不完整.
    最佳实践: 用户提供具体推文 URL 列表 (通过 usernames 构建 URL).
    """
    from stratum.services.web_fetch_enhanced import fetch_url_enhanced

    # 构建推文 URL 列表
    tweet_urls: list[str] = []
    if usernames:
        for user in usernames[:5]:
            tweet_urls.append(f"https://twitter.com/{user}/status/")  # 用户最新推文
    if keyword:
        # Twitter 搜索 URL (jina.ai 可能无法完整解析)
        import urllib.parse
        tweet_urls.append(f"https://twitter.com/search?q={urllib.parse.quote(keyword)}")

    # 允许直接提供 URL
    direct_urls = _kw.get("urls", [])
    tweet_urls.extend(direct_urls)

    results: list[SourceResult] = []
    for url in tweet_urls[:max_results]:
        try:
            result = await fetch_url_enhanced(url, strategy="twitter")
            if result.success and result.html:
                ext_id = f"tweet_{abs(hash(url)) % 10**12}"
                results.append(SourceResult(
                    external_id=ext_id,
                    title=result.title or f"Twitter Thread {ext_id[-8:]}",
                    download_url=url,
                    file_type="html",
                    metadata={
                        "source_type": "twitter",
                        "url": url,
                        "strategy": result.strategy_used,
                        "content_preview": result.html[:500] if result.html else "",
                    },
                ))
                log.info("twitter_fetch: OK %s len=%d", ext_id, len(result.html))
            else:
                log.warning("twitter_fetch: FAIL %s error=%s", url[:60], result.error)
        except Exception as e:
            log.warning("twitter_fetch: ERROR %s %s", url[:60], e)

    return results
