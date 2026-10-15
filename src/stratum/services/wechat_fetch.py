"""stratum.services.wechat_fetch — WeChat public-account (mp.weixin.qq.com) article fetch.

Ported from wexin-read-mcp's fetch/parse contract (https://github.com/joeseesun/wexin-read-mcp,
MIT License) but implemented as a self-contained HTTP fetch — no Playwright, no external
``url-md`` binary. Plain HTTP against ``mp.weixin.qq.com`` works for public articles (verified),
so the heavy browser path is deliberately not introduced.

The upstream tool returns ``{success, title, author, publish_time, content, cover_url, error}``
with ``content`` as Markdown; this module keeps that shape and adds ``strategy`` + ``url``.

Extraction:
  * body     — the ``#js_content`` container (WeChat's article body), HTML→Markdown
  * title    — ``og:title`` → ``<title>`` → ``var msg_title``
  * author   — ``var author`` → ``var nickname`` (account name) → ``og:article:author``
  * publish  — ``var ct`` (unix seconds) → ``og:article:published_time``
  * cover    — ``og:image``

Falls back to the generic cascade (``fetch_web_markdown``) when the direct page carries no
``#js_content`` (e.g. a "verify" interstitial), so a WeChat URL still has a second chance.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from lxml import html as lxml_html

from stratum.services.web_fetch_cascade import (
    _norm_ws,
    extract_jsonld_article,
    fetch_web_markdown,
    html_to_markdown,
    is_fetchable_url,
    make_client,
)

log = logging.getLogger(__name__)

_WECHAT_HOSTS = ("mp.weixin.qq.com", "mp.weixin.qq.com.cn")

# JS vars WeChat embeds in the page (used as a metadata fallback).
_JS_STR = {
    "msg_title": r"var\s+msg_title\s*=\s*(['\"])(?P<v>.*?)\1",
    "nickname": r"var\s+nickname\s*=\s*(['\"])(?P<v>.*?)\1",
    "author": r"var\s+author\s*=\s*(['\"])(?P<v>.*?)\1",
    "user_name": r"var\s+user_name\s*=\s*(['\"])(?P<v>.*?)\1",
}
_JS_CT = re.compile(r"var\s+ct\s*=\s*['\"]?(?P<v>\d{9,11})\b")
_META_RE = re.compile(
    r"<meta[^>]+(?:property|name)=[\"'](?P<key>[^\"']+)[\"'][^>]+content=[\"'](?P<val>[^\"']*)[\"']",
    re.I,
)


@dataclass
class WeChatArticle:
    success: bool
    url: str
    markdown: str = ""
    title: str = ""
    author: str = ""
    published: str = ""
    cover_url: str = ""
    account: str = ""
    strategy: str = ""
    error: str | None = None

    @property
    def char_count(self) -> int:
        return len(self.markdown)


def is_wechat_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in _WECHAT_HOSTS


def _meta_map(doc) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _META_RE.finditer(lxml_html.tostring(doc, encoding="unicode")):
        out.setdefault(m.group("key").lower(), _norm_ws(m.group("val")))
    return out


def _js_str(text: str, key: str) -> str:
    m = re.search(_JS_STR[key], text)
    return _norm_ws(m.group("v")) if m else ""


def _ct_to_iso(html_text: str) -> str:
    m = _JS_CT.search(html_text)
    if not m:
        return ""
    try:
        return datetime.fromtimestamp(int(m.group("v")), tz=timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return ""


def parse_wechat_html(html_text: str, url: str = "") -> WeChatArticle:
    """Parse a fetched WeChat article page into title/author/date/cover + Markdown body."""
    if not html_text:
        return WeChatArticle(success=False, url=url, error="empty document")

    try:
        doc = lxml_html.fromstring(html_text)
    except Exception as e:  # noqa: BLE001
        return WeChatArticle(success=False, url=url, error=f"html parse failed: {e}")

    meta = _meta_map(doc)

    # Body: WeChat's #js_content container. If absent, try JSON-LD, else whole-page MD.
    node = doc.xpath('//*[@id="js_content"]')
    body_html = lxml_html.tostring(node[0], encoding="unicode") if node else ""
    if body_html:
        markdown = html_to_markdown(body_html, url)
        strategy = "wechat_http"
    else:
        ld = extract_jsonld_article(html_text)
        if ld["body"]:
            markdown = ld["body"]
            strategy = "wechat_jsonld"
        else:
            markdown = html_to_markdown(html_text, url)
            strategy = "wechat_http_fallback"

    title = (
        meta.get("og:title")
        or (doc.findtext(".//title") or "").strip()
        or _js_str(html_text, "msg_title")
    )
    author = (
        _js_str(html_text, "author")
        or meta.get("og:article:author")
        or _js_str(html_text, "nickname")
    )
    account = _js_str(html_text, "nickname")
    published = meta.get("og:article:published_time") or _ct_to_iso(html_text)
    cover = meta.get("og:image") or ""

    markdown = _norm_ws_body(markdown)
    ok = len(markdown) >= 200
    return WeChatArticle(
        success=ok,
        url=url,
        markdown=markdown,
        title=_norm_ws(title),
        author=_norm_ws(author),
        published=_norm_ws(published),
        cover_url=cover,
        account=_norm_ws(account),
        strategy=strategy,
        error=None if ok else "no article body found",
    )


def _norm_ws_body(md: str) -> str:
    """Collapse 3+ blank lines but keep paragraph breaks."""
    return re.sub(r"\n{3,}", "\n\n", md or "").strip()


def fetch_wechat_article(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float | None = None,
    max_bytes: int = 5 * 1024 * 1024,
) -> WeChatArticle:
    """Fetch a WeChat article over plain HTTP and return Markdown + metadata.

    ``client`` (e.g. a MockTransport-backed client) is used as-is and not closed.
    """
    url = (url or "").strip()
    if not is_fetchable_url(url):
        return WeChatArticle(success=False, url=url, error="unsupported or non-public url")

    owns = client is None
    if client is None:
        client = make_client(timeout)

    try:
        try:
            resp = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
                        "MicroMessenger/8.0"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001
            return WeChatArticle(
                success=False, url=url, error=f"request error: {type(e).__name__}: {e}"
            )
        if resp.status_code >= 400:
            return WeChatArticle(success=False, url=url, error=f"HTTP {resp.status_code}")

        article = parse_wechat_html(resp.text[:max_bytes], url)
        if article.success:
            log.info(
                "wechat_fetch ok url=%s title=%s chars=%d",
                url[:80],
                article.title,
                article.char_count,
            )
            return article

        # Direct page carried no #js_content — usually WeChat's "环境异常/去验证" anti-bot
        # interstitial served to datacenter IPs. Fall back to the proxy layers of the generic
        # cascade (r.jina.ai / defuddle.md), which reach the article from a different egress.
        # Only the proxy layers are useful here; the bot-UA layers hit the same interstitial.
        return _wechat_via_cascade(url, client=client, timeout=timeout, direct_error=article.error)
    finally:
        if owns:
            client.close()


def _wechat_via_cascade(
    url: str,
    *,
    client: httpx.Client,
    timeout: float | None,
    direct_error: str | None,
) -> WeChatArticle:
    """Second chance for a WeChat URL whose direct page was an anti-bot interstitial."""
    res = fetch_web_markdown(url, client=client, timeout=timeout, allow_archive=False)
    if res.success and len(res.markdown) >= 200:
        log.info(
            "wechat_fetch ok via=%s url=%s chars=%d",
            res.strategy,
            url[:80],
            res.char_count,
        )
        return WeChatArticle(
            success=True,
            url=url,
            markdown=_norm_ws_body(res.markdown),
            title=_norm_ws(res.title),
            author=_norm_ws(res.author),
            published=_norm_ws(res.published),
            strategy=f"wechat_via_{res.strategy}",
        )
    return WeChatArticle(
        success=False,
        url=url,
        strategy=res.strategy,
        error=direct_error or res.error or "no article body found",
    )
