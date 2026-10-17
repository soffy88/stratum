"""stratum.services.web_fetch_enhanced — 增强版 URL 抓取: 付费墙绕过 + 多源适配 + JS 渲染.

集成 Crawl4AI 到 stratum web-clip / source_watcher 管线.

支持:
  - JS 渲染/SPA (React/Vue/Angular) → Crawl4AI (Playwright 异步抓取)
  - 普通网页 → SSRF-safe 直取 + oprim 标准流程

★ 降级说明 (2026-10-17, 审计 🟡15): 原设计中微信公众号 / X(Twitter) / 付费墙站点走
  ``oprim.fetch_url_with_bypass``, 但已发布的 oprim 中不存在该函数 (仅在未合并的分支里),
  该分支一直静默回退直取. 现删除死分支, 这三类请求 **明确降级** 为 SSRF-safe 直取:
  每次降级记 WARNING 日志 ``fetch_strategy_degraded`` 并计入 ``get_fetch_metrics()``,
  成功结果的 ``strategy_used`` 为 ``direct_degraded_<kind>``. oprim 正式提供绕过能力后再接回.

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
import threading
from collections import Counter
from dataclasses import dataclass

log = logging.getLogger(__name__)

# 需要专用绕过能力、但当前没有可用实现的策略 → 明确降级为直取.
_DEGRADED_KINDS = frozenset(("wechat", "twitter", "paywall"))

# 进程内抓取策略计数 (key 集合有限: <outcome>:<strategy>, 不会无界增长).
_FETCH_METRICS: Counter[str] = Counter()
_FETCH_METRICS_LOCK = threading.Lock()


def _record_metric(key: str) -> None:
    with _FETCH_METRICS_LOCK:
        _FETCH_METRICS[key] += 1


def get_fetch_metrics() -> dict[str, int]:
    """返回抓取策略计数快照, 如 {"degraded:wechat": 3, "ok:direct": 10}."""
    with _FETCH_METRICS_LOCK:
        return dict(_FETCH_METRICS)

# 已知 JS 渲染/SPA 域名 (触发 Crawl4AI)
_JS_HEAVY_DOMAINS = frozenset(
    (
        "notion.so",
        "airtable.com",
        "medium.com",
        "substack.com",
        "threads.net",
        "instagram.com",
        "tiktok.com",
        "reddit.com",
        "github.com",
        "gitlab.com",
        "bitbucket.org",
    )
)


@dataclass
class FetchResult:
    """增强抓取结果."""

    html: str  # HTML/Markdown 内容
    title: str  # 提取的标题
    strategy_used: str  # 实际使用的策略
    content_type: str  # "generic" | "wechat_article" | "twitter_thread" | "js_rendered"
    source_url: str  # 原始 URL
    success: bool  # 是否成功
    error: str | None  # 失败原因


def _detect_paywall_domain(url: str) -> str | None:
    """快速检测 URL 是否属于已知付费墙/JS 渲染域名."""
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    # 付费墙 (Bot UA 策略)
    if any(
        host == d or host.endswith("." + d)
        for d in (
            "nytimes.com",
            "wsj.com",
            "ft.com",
            "economist.com",
            "bloomberg.com",
            "washingtonpost.com",
            "newyorker.com",
            "wired.com",
            "theatlantic.com",
            "medium.com",
            "businessinsider.com",
            "technologyreview.com",
            "scmp.com",
            "forbes.com",
            "foreignaffairs.com",
            "theinformation.com",
        )
    ):
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
    """增强 URL 抓取: 多源适配 + JS 渲染 + SSRF 安全.

    策略:
      1. 检测域名类型 (wechat/twitter/paywall/js_heavy/普通); 显式 ``strategy`` 参数
         为 wechat/twitter/paywall/crawl4ai 时优先于域名检测
      2. wechat/twitter/paywall → 当前无可用绕过实现, 明确降级为 SSRF-safe 直取
         (WARNING 日志 + metrics ``degraded:<kind>``)
      3. js_heavy → Crawl4AI (Playwright 异步抓取, LLM-ready Markdown), 失败回退直取
      4. 普通 → SSRF-safe 直取 (DNS-pinned)
    """
    domain_type = _detect_paywall_domain(url)
    log.info(
        "fetch_url_enhanced url=%s domain_type=%s strategy=%s", url[:80], domain_type, strategy
    )

    degraded_kind = strategy if strategy in _DEGRADED_KINDS else None
    if degraded_kind is None and domain_type in _DEGRADED_KINDS:
        degraded_kind = domain_type
    if degraded_kind is not None:
        return await _fetch_degraded(url, degraded_kind, timeout, max_bytes)

    # JS 渲染/SPA → Crawl4AI
    if domain_type == "js_heavy" or strategy == "crawl4ai":
        result = await _fetch_with_crawl4ai(url, timeout, max_bytes)
        if result.success:
            _record_metric("ok:crawl4ai")
            return result
        _record_metric("fallback:crawl4ai")

    # 普通网页 → SSRF-safe 直取
    result = await _fetch_direct(url, timeout, max_bytes)
    _record_metric(("ok:" if result.success else "fail:") + "direct")
    return result


async def _fetch_degraded(url: str, kind: str, timeout: int, max_bytes: int) -> FetchResult:
    """wechat/twitter/paywall: 无专用绕过实现, 明确降级为直取并记录."""
    _record_metric(f"degraded:{kind}")
    log.warning(
        "fetch_strategy_degraded url=%s requested=%s fallback=direct "
        "reason=no_bypass_fetcher_available",
        url[:80],
        kind,
    )
    result = await _fetch_direct(url, timeout, max_bytes)
    _record_metric(("ok:" if result.success else "fail:") + f"direct_degraded_{kind}")
    if result.success:
        result.strategy_used = f"direct_degraded_{kind}"
    return result


async def _fetch_with_crawl4ai(
    url: str,
    timeout: int,
    max_bytes: int,
) -> FetchResult:
    """通过 Crawl4AI (Playwright) 抓取 JS 渲染页面."""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        log.warning("crawl4ai not installed, skipping JS render fetch")
        return FetchResult(
            html="",
            title="",
            strategy_used="crawl4ai_unavailable",
            content_type="js_rendered",
            source_url=url,
            success=False,
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

        log.warning(
            "crawl4ai_failed url=%s success=%s md_len=%d", url[:80], result.success, len(md)
        )
        return FetchResult(
            html="",
            title="",
            strategy_used="crawl4ai_error",
            content_type="js_rendered",
            source_url=url,
            success=False,
            error="Crawl4AI returned empty content",
        )
    except Exception as e:
        log.warning("crawl4ai_exception url=%s error=%s", url[:80], e)
        return FetchResult(
            html="",
            title="",
            strategy_used="crawl4ai_exception",
            content_type="js_rendered",
            source_url=url,
            success=False,
            error=str(e),
        )


async def _fetch_direct(
    url: str,
    timeout: int,
    max_bytes: int,
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
                html="",
                title="",
                strategy_used="unavailable",
                content_type="generic",
                source_url=url,
                success=False,
                error="URL fetch unavailable",
            )

    try:
        result = await asyncio.to_thread(
            fetch_url_ssrf_safe,
            url=url,
            timeout=timeout,
            max_bytes=max_bytes,
        )
    except Exception as e:
        log.warning("direct_fetch_error url=%s error=%s", url[:80], e)
        return FetchResult(
            html="",
            title="",
            strategy_used="direct_failed",
            content_type="generic",
            source_url=url,
            success=False,
            error=str(e),
        )

    err = result.get("error")
    if err:
        log.warning("direct_fetch_error url=%s error=%s", url[:80], err)
        return FetchResult(
            html="",
            title="",
            strategy_used="direct_error",
            content_type="generic",
            source_url=url,
            success=False,
            error=err,
        )

    status = result.get("status_code")
    if status and status >= 400:
        return FetchResult(
            html="",
            title="",
            strategy_used=f"http_{status}",
            content_type="generic",
            source_url=url,
            success=False,
            error=f"HTTP {status}",
        )

    html = result.get("body_text", "")
    if not html:
        return FetchResult(
            html="",
            title="",
            strategy_used="empty_response",
            content_type="generic",
            source_url=url,
            success=False,
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
