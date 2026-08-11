"""stratum.services.web_fetch_enhanced — 增强版 URL 抓取: 付费墙绕过 + 多源适配 + JS 渲染.

集成 oprim.fetch_url_with_bypass + Crawl4AI 到 stratum web-clip / source_watcher 管线.

支持:
  - 微信公众号 (mp.weixin.qq.com) → jina.ai 代理
  - X/Twitter 线程 (x.com/twitter.com) → jina.ai / agent-fetch 级联
  - 付费墙站点 (nytimes/wsj/ft/economist/bloomberg/medium...) → Bot UA + AMP + archive 级联
  - JS 渲染/SPA (React/Vue/Angular) → Crawl4AI (Playwright 异步抓取)
  - 普通网页 → SSRF-safe 直取 + oprim 标准流程

用法:
  from stratum.services.web_fetch_enhanced import fetch_url_enhanced
  result = await fetch_url_enhanced(url)
  result.html  # HTML/Markdown 内容
  result.strategy_used  # 实际使用的策略
  result.content_type  # "generic" | "wechat_article" | "twitter_thread" | "js_rendered"
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

# 已知 JS 渲染/SPA 域名 (触发 Crawl4AI)
_JS_HEAVY_DOMAINS = frozenset((
    "notion.so", "airtable.com", "medium.com", "substack.com",
    "threads.net", "instagram.com", "tiktok.com", "reddit.com",
    "github.com", "gitlab.com", "bitbucket.org",
))


@dataclass
class FetchResult:
    """增强抓取结果."""
    html: str                    # HTML/Markdown 内容
    title: str                   # 提取的标题
    strategy_used: str           # 实际使用的策略
    content_type: str            # "generic" | "wechat_article" | "twitter_thread" | "js_rendered"
    source_url: str              # 原始 URL
    success: bool                # 是否成功
    error: str | None            # 失败原因


def _detect_paywall_domain(url: str) -> str | None:
    """快速检测 URL 是否属于已知付费墙/JS 渲染域名."""
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    # 付费墙 (Bot UA 策略)
    if any(host == d or host.endswith("." + d) for d in (
        "nytimes.com", "wsj.com", "ft.com", "economist.com", "bloomberg.com",
        "washingtonpost.com", "newyorker.com", "wired.com", "theatlantic.com",
        "medium.com", "businessinsider.com", "technologyreview.com", "scmp.com",
        "forbes.com", "foreignaffairs.com", "theinformation.com",
    )):
        return "paywall"
    # 微信
    if host in ("mp.weixin.qq.com",):
        return "wechat"
    # X/Twitter
    if host in ("x.com", "twitter.com", "t.co"):
        return "twitter"
    # JS 渲染/SPA
    if any(host == d or host.endswith("." + d) for d in _JS_HEAVY_DOMAINS):
        return "js_heavy"
    return None


async def fetch_url_enhanced(
    url: str,
    *,
    timeout: int = 30,
    max_bytes: int = 5 * 1024 * 1024,
    strategy: str = "auto",
) -> FetchResult:
    """增强 URL 抓取: 付费墙绕过 + 多源适配 + JS 渲染 + SSRF 安全.

    策略:
      1. 检测域名类型 (wechat/twitter/paywall/js_heavy/普通)
      2. wechat/twitter → 专用 fetcher (jina.ai 代理)
      3. paywall → oprim.fetch_url_with_bypass(strategy=auto) 级联绕过
      4. js_heavy → Crawl4AI (Playwright 异步抓取, LLM-ready Markdown)
      5. 普通 → oprim.url_fetch_ssrf_safe (DNS-pinned)
      6. 所有策略失败 → 回退普通抓取
    """
    domain_type = _detect_paywall_domain(url)
    log.info("fetch_url_enhanced url=%s domain_type=%s strategy=%s",
             url[:80], domain_type, strategy)

    # 源专用抓取
    if domain_type in ("wechat", "twitter"):
        return await _fetch_with_bypass(url, domain_type, timeout, max_bytes)

    # 付费墙 → 级联绕过 (包含 stealth 策略)
    if domain_type == "paywall" or strategy == "paywall":
        return await _fetch_with_bypass(url, "stealth", timeout, max_bytes)

    # JS 渲染/SPA → Crawl4AI
    if domain_type == "js_heavy" or strategy == "crawl4ai":
        result = await _fetch_with_crawl4ai(url, timeout, max_bytes)
        if result.success:
            return result
        # 降级: 尝试级联绕过或直取
        if domain_type == "paywall":
            return await _fetch_with_bypass(url, "paywall", timeout, max_bytes)

    # 普通网页 → SSRF-safe 直取
    return await _fetch_direct(url, timeout, max_bytes)


async def _fetch_with_crawl4ai(
    url: str, timeout: int, max_bytes: int,
) -> FetchResult:
    """通过 Crawl4AI (Playwright) 抓取 JS 渲染页面."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        log.warning("crawl4ai not installed, skipping JS render fetch")
        return FetchResult(
            html="", title="", strategy_used="crawl4ai_unavailable",
            content_type="js_rendered", source_url=url, success=False,
            error="crawl4ai not installed (pip install crawl4ai)",
        )

    try:
        browser_cfg = BrowserConfig(
            headless=True,
            viewport_width=1280,
            viewport_height=720,
            text_mode=True,  # 优化文本提取
            enable_stealth=True,  # 启用隐身模式 (绕过反爬)
        )
        run_cfg = CrawlerRunConfig(
            page_timeout=timeout * 1000,  # ms
            stream=False,
        )

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)

        # Crawl4AI 0.9+ returns CrawlerRunResult with markdown attribute
        md = getattr(result, "markdown", "") or ""
        if isinstance(md, dict):
            md = md.get("raw_markdown", "") or md.get("markdown", "") or ""
        if not isinstance(md, str):
            md = ""

        if result.success and md:
            content = md[:max_bytes]
            title = ""
            try:
                title = getattr(result, "title", "") or ""
            except Exception:
                pass
            return FetchResult(
                html=content,
                title=title,
                strategy_used="crawl4ai",
                content_type="js_rendered",
                source_url=url,
                success=True,
                error=None,
            )

        log.warning("crawl4ai_failed url=%s success=%s md_len=%d",
                    url[:80], result.success, len(md))
        return FetchResult(
            html="", title="", strategy_used="crawl4ai_error",
            content_type="js_rendered", source_url=url, success=False,
            error="Crawl4AI returned empty content",
        )
    except Exception as e:
        log.warning("crawl4ai_exception url=%s error=%s", url[:80], e)
        return FetchResult(
            html="", title="", strategy_used="crawl4ai_exception",
            content_type="js_rendered", source_url=url, success=False,
            error=str(e),
        )


async def _fetch_with_bypass(
    url: str, strategy: str, timeout: int, max_bytes: int,
) -> FetchResult:
    """通过 oprim.fetch_url_with_bypass 抓取."""
    try:
        from oprim import fetch_url_with_bypass
    except ImportError:
        log.warning("oprim.fetch_url_with_bypass not available, falling back to direct")
        return await _fetch_direct(url, timeout, max_bytes)

    try:
        result = await asyncio.to_thread(
            fetch_url_with_bypass, url, strategy=strategy if strategy not in ("auto", "paywall") else "stealth",
        )
    except Exception as e:
        log.warning("bypass_fetch_error url=%s strategy=%s error=%s", url[:80], strategy, e)
        return await _fetch_direct(url, timeout, max_bytes)

    if result.get("success"):
        content = result.get("content", "")
        if len(content) > max_bytes:
            content = content[:max_bytes]
        return FetchResult(
            html=content,
            title=result.get("title", ""),
            strategy_used=result.get("strategy", "unknown"),
            content_type=result.get("content_type", "generic"),
            source_url=url,
            success=True,
            error=None,
        )

    log.warning("bypass_failed url=%s strategy=%s error=%s", url[:80],
                result.get("strategy"), result.get("error"))
    # 降级: 尝试 SSRF-safe 直取
    return await _fetch_direct(url, timeout, max_bytes)


async def _fetch_direct(
    url: str, timeout: int, max_bytes: int,
) -> FetchResult:
    """SSRF-safe 直取 (标准 oprim 流程)."""
    try:
        from stratum.services.web_fetch import fetch_url_ssrf_safe
    except ImportError:
        try:
            from oprim import url_fetch_ssrf_safe as fetch_url_ssrf_safe
        except ImportError:
            log.warning("SSRF-safe fetch not available")
            return FetchResult(
                html="", title="", strategy_used="unavailable",
                content_type="generic", source_url=url, success=False,
                error="URL fetch unavailable",
            )

    try:
        result = await asyncio.to_thread(
            fetch_url_ssrf_safe, url=url, timeout=timeout, max_bytes=max_bytes,
        )
    except Exception as e:
        log.warning("direct_fetch_error url=%s error=%s", url[:80], e)
        return FetchResult(
            html="", title="", strategy_used="direct_failed",
            content_type="generic", source_url=url, success=False,
            error=str(e),
        )

    err = result.get("error")
    if err:
        log.warning("direct_fetch_error url=%s error=%s", url[:80], err)
        return FetchResult(
            html="", title="", strategy_used="direct_error",
            content_type="generic", source_url=url, success=False,
            error=err,
        )

    status = result.get("status_code")
    if status and status >= 400:
        return FetchResult(
            html="", title="", strategy_used=f"http_{status}",
            content_type="generic", source_url=url, success=False,
            error=f"HTTP {status}",
        )

    html = result.get("body_text", "")
    if not html:
        return FetchResult(
            html="", title="", strategy_used="empty_response",
            content_type="generic", source_url=url, success=False,
            error="Empty response",
        )

    # 提取标题
    title_m = re.search(r"<title[^>]*>([^<]{1,300})</title>", html, re.I | re.S)
    title = title_m.group(1).strip() if title_m else url

    return FetchResult(
        html=html,
        title=title,
        strategy_used="direct",
        content_type="generic",
        source_url=url,
        success=True,
        error=None,
    )
