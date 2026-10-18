"""stratum.services.web_fetch_cascade — multi-layer URL fetch (paywall cascade → clean Markdown).

Ported from the six-layer strategy in joeseesun/qiaomu-anything-to-notebooklm's
``scripts/fetch_url.sh`` (MIT License, Copyright (c) 2024 joeseesun), rewritten in
Python on httpx + lxml so it runs with the backend's existing dependencies and can
be unit-tested without a browser.

Layer order (first success wins):

  1. r.jina.ai proxy (wide coverage, often bypasses paywalls)
  2. defuddle.md proxy (clean Markdown + YAML frontmatter)
  3. Site-specific Googlebot UA  (SEO whitelist, ~50 sites)
  4. Site-specific Bingbot UA
  5. Generic paywall bypass: Googlebot UA + X-Forwarded-For, Bingbot UA,
     Facebook/Twitter referer, AMP page, EU X-Forwarded-For
  6. archive.today  →  Google cache (last resorts)

The JSON-LD ``articleBody`` extractor is shared: any HTML-returning layer first
tries to pull the full article body out of ``<script type="application/ld+json">``
before falling back to a plain HTML→Markdown conversion.

Network is configurable: set ``STRATUM_WEB_FETCH_PROXY`` to route every request
through an HTTP(S) proxy (e.g. the local relay), and ``STRATUM_WEB_FETCH_TIMEOUT``
to change the per-request timeout. Both the direct path and the proxy path are
supported; the caller decides which by setting the env var.

Public entry points:
  * ``fetch_web_markdown(url, ...) -> WebFetchResult``
  * ``extract_jsonld_article(html) -> dict`` (standalone, unit-tested)
  * ``html_to_markdown(html, base_url="") -> str``
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from lxml import html as lxml_html

log = logging.getLogger(__name__)

# ── Paywall domain lists (from Bypass Paywalls Clean, via fetch_url.sh) ──────────

# Sites where a Googlebot UA gets full content (SEO whitelist).
GOOGLEBOT_DOMAINS = (
    "wsj.com|barrons.com|ft.com|economist.com|theaustralian.com.au|thetimes.co.uk|"
    "telegraph.co.uk|zeit.de|handelsblatt.com|leparisien.fr|nzz.ch|usatoday.com|"
    "quora.com|lefigaro.fr|lemonde.fr|spiegel.de|sueddeutsche.de|"
    "frankfurter-allgemeine.de|wires.com|brisbanetimes.com.au|smh.com.au|theage.com.au"
)

# Sites where a Bingbot UA works.
BINGBOT_DOMAINS = "haaretz.com|nzherald.co.nz|stratfor.com|themarker.com"

# Sites that allow social referral traffic.
FACEBOOK_REF_DOMAINS = "law.com|ftm.nl|law360.com|sloanreview.mit.edu"

# Sites with usable AMP versions.
AMP_DOMAINS = (
    "wsj.com|bostonglobe.com|latimes.com|chicagotribune.com|seattletimes.com|"
    "theatlantic.com|wired.com|newyorker.com|washingtonpost.com|smh.com.au|"
    "theage.com.au|brisbanetimes.com.au"
)

# All known paywall domains (for the generic bypass attempts).
PAYWALL_DOMAINS = (
    "nytimes.com|wsj.com|ft.com|economist.com|bloomberg.com|washingtonpost.com|"
    "newyorker.com|wired.com|theatlantic.com|medium.com|businessinsider.com|"
    "technologyreview.com|scmp.com|seattletimes.com|bostonglobe.com|latimes.com|"
    "chicagotribune.com|theglobeandmail.com|afr.com|thetimes.co.uk|telegraph.co.uk|"
    "spiegel.de|zeit.de|sueddeutsche.de|barrons.com|forbes.com|foreignaffairs.com|"
    "foreignpolicy.com|harvard.edu|newscientist.com|scientificamerican.com|"
    "theinformation.com|statista.com|handelsblatt.com|nzz.ch|leparisien.fr|"
    "lefigaro.fr|lemonde.fr|haaretz.com|nzherald.co.nz|theaustralian.com.au|"
    "smh.com.au|theage.com.au|quora.com|usatoday.com"
)

_GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
_BINGBOT_UA = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_PAYWALL_RE = re.compile(
    r"(subscribe to (continue|read|access|unlock)|paywall|premium[._]content|"
    r"metered[._]paywall|article[._]limit|sign[._]in[._]to[._](continue|read)|"
    r"create[._]a[._]free[._]account[._]to[._]unlock|membership[._]to[._]continue|"
    r"subscribe now for full access|to continue reading|remaining free articles|"
    r"has been removed|subscribe or|already a subscriber|"
    # Registration / login walls that proxy services and referral-referer fetches serve
    # in place of the article (verified: FT returns "To read this article for free /
    # Once registered, you can:" to a twitter-referer fetch; these carry no article text).
    r"to read this article for free|once registered, you can|unlock this article|"
    r"subscribe to unlock|this article is (for|available to) (subscribers|members)|"
    r"register to (continue|read|unlock)|become a (subscriber|member) to)",
    re.I,
)
_CAPTCHA_RE = re.compile(
    r"(security check|captcha|recaptcha|hcaptcha|please complete|"
    r"cloudflare.*challenge|verify you are human)",
    re.I,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{1,300})</title>", re.I | re.S)
_NON_PUBLIC_TLDS = (".local", ".internal", ".lan", ".home.arpa", ".localdomain")

_ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "report", "webpage"}

# ── Prose-quality gate ──────────────────────────────────────────────────────────
# ``has_content`` (line/char count) is too weak on its own: a proxy service or a
# referral-referer fetch can return a full-size *paywall shell* — navigation, a
# "subscribe / register to read" block and a footer — that clears the line and char
# floors while containing none of the article. We therefore measure the *prose*:
# long, non-boilerplate, non-link text lines. Verified separation on real fetches —
# genuine articles (FT, Wikipedia) yield 54-70 prose lines / 22k-28k prose chars,
# while paywall/registration shells yield ≤4 lines / ≤420 chars. Boilerplate is
# matched on the *link-stripped* line, so navigation lists drop out.
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_URL_RE = re.compile(r"https?://\S+")
_BOILERPLATE_RE = re.compile(
    r"(cookie|consent|gdpr|privacy policy|terms of (service|use)|subscrib|sign ?in|"
    r"sign ?up|log ?in|register|newsletter|advertis|all rights reserved|follow us|"
    r"share this|related (articles|stories)|most read|recommended|you might (also )?like|"
    r"manage (your )?(preferences|cookies)|accept all|reject all|enable javascript|"
    r"digital access|gift articles|expert opinion|global news|save (now|over)|"
    r"per (month|year)|your first year|editor.s digest|alphaville|follow topics|"
    r"complete digital|essential digital|cancel anytime|on any device|print edition|"
    r"©|all rights)",
    re.I,
)
# A genuine article must clear all three (chars, lines, prose ratio). Thresholds sit
# well above every observed wall (≤420 chars, ≤4 lines) and well below every observed
# article (≥22k chars); the ratio rejects link/nav-dominated pages of any size.
_MIN_PROSE_CHARS = 1200
_MIN_PROSE_LINES = 3
_MIN_PROSE_RATIO = 0.10


# ── Result type ─────────────────────────────────────────────────────────────────


@dataclass
class WebFetchResult:
    """One URL fetch outcome, with the strategy that produced it and the attempt log."""

    success: bool
    url: str
    markdown: str = ""
    title: str = ""
    author: str = ""
    published: str = ""
    strategy: str = ""
    error: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.markdown)


# ── Config ──────────────────────────────────────────────────────────────────────


def _proxy_url() -> str | None:
    return (os.environ.get("STRATUM_WEB_FETCH_PROXY") or "").strip() or None


def _default_timeout() -> float:
    try:
        return float(os.environ.get("STRATUM_WEB_FETCH_TIMEOUT", "25"))
    except ValueError:
        return 25.0


class SSRFBlockedError(Exception):
    """Request (or redirect hop) targets a non-public destination."""


def _ssrf_request_hook(request: httpx.Request) -> None:
    """httpx calls request hooks for the first request AND every redirect hop,
    so each hop is re-resolved and refused if it is not public (安全审计 🟡9)."""
    from stratum.services.web_fetch import is_public_destination

    url = str(request.url)
    if not is_public_destination(url):
        raise SSRFBlockedError(f"ssrf_blocked: non-public destination {url!r}")


def make_client(timeout: float | None = None) -> httpx.Client:
    """Build an httpx client honouring ``STRATUM_WEB_FETCH_PROXY`` when set."""
    kwargs: dict[str, Any] = {
        "timeout": timeout or _default_timeout(),
        "follow_redirects": True,
        "event_hooks": {"request": [_ssrf_request_hook]},
        "headers": {"User-Agent": _DEFAULT_UA, "Accept-Language": "en,zh;q=0.8"},
    }
    proxy = _proxy_url()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


# ── URL guards ──────────────────────────────────────────────────────────────────


def is_fetchable_url(url: str) -> bool:
    """Reject non-http(s) schemes and obviously non-public hosts (SSRF guard)."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname or hostname == "localhost":
        return False
    try:
        ipaddress.ip_address(hostname)
        return False  # IP literal
    except ValueError:
        pass
    return not hostname.endswith(_NON_PUBLIC_TLDS)


def _domain_matches(url: str, domains: str) -> bool:
    return re.search(domains, url, re.I) is not None


def host_of(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


# ── Content heuristics ──────────────────────────────────────────────────────────


def prose_stats(text: str) -> tuple[int, int]:
    """Return ``(prose_lines, prose_chars)`` for a Markdown blob.

    A *prose line* is a long (≥80-char) line of running text: markdown links are
    reduced to their anchor text and bare URLs dropped first, then lines matching
    the boilerplate/navigation vocabulary are discarded. This is what separates a
    real article body from a full-size paywall/registration shell.
    """
    if not text:
        return 0, 0
    stripped = _MD_LINK_RE.sub(r"\1", text)
    stripped = _MD_URL_RE.sub("", stripped)
    lines: list[str] = []
    for raw in stripped.splitlines():
        line = raw.strip(" \t*#>-")
        if len(line) >= 80 and not _BOILERPLATE_RE.search(line):
            lines.append(line)
    return len(lines), sum(len(line) for line in lines)


def has_article_body(text: str) -> bool:
    """True when ``text`` carries enough *prose* to be a real article (not a wall).

    Requires all of: ≥ ``_MIN_PROSE_CHARS`` prose characters, ≥ ``_MIN_PROSE_LINES``
    prose lines, and a prose-to-total ratio ≥ ``_MIN_PROSE_RATIO``. Calibrated so that
    genuine articles pass and every observed paywall/registration shell fails.
    """
    if not text or len(text) < 500:
        return False
    lines, chars = prose_stats(text)
    if chars < _MIN_PROSE_CHARS or lines < _MIN_PROSE_LINES:
        return False
    return chars / len(text) >= _MIN_PROSE_RATIO


def has_content(text: str) -> bool:
    """True when ``text`` looks like a real article, not a nav/error/login page.

    Combines the cheap line/char floor with the prose-quality gate, so a large but
    content-free paywall shell is rejected rather than silently accepted.
    """
    if not text or len(text) < 500:
        return False
    if text.count("\n") < 8:
        return False
    low = text.lower()
    for marker in (
        "don't miss what's happening",
        "access denied",
        "404 not found",
        "403 forbidden",
    ):
        if marker in low:
            return False
    return has_article_body(text)


def is_paywall_content(text: str) -> bool:
    return _PAYWALL_RE.search(text) is not None


def is_captcha_page(text: str) -> bool:
    return _CAPTCHA_RE.search(text) is not None


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _strip_html(text: str) -> str:
    """Remove tags and unescape entities from a fragment (e.g. JSON-LD articleBody)."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    import html as _html

    return _html.unescape(text).strip()


# ── JSON-LD extraction (shared by every HTML-returning layer) ────────────────────


def _iter_jsonld(data: Any):
    """Yield every JSON-LD object in a document (handles lists and @graph)."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_jsonld(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _iter_jsonld(data["@graph"])
        yield data


def _ld_author(author: Any) -> str:
    if isinstance(author, str):
        return author.strip()
    if isinstance(author, dict):
        return _norm_ws(str(author.get("name") or ""))
    if isinstance(author, list):
        names = [_ld_author(a) for a in author]
        return ", ".join(n for n in names if n)
    return ""


def _ld_types(obj: dict) -> set[str]:
    t = obj.get("@type")
    values = t if isinstance(t, list) else [t]
    return {str(v).lower() for v in values if v}


def extract_jsonld_article(html_text: str) -> dict[str, str]:
    """Pull ``{body, title, author, published}`` from schema.org Article JSON-LD.

    Scans every ``<script type="application/ld+json">`` block (including ``@graph``
    and arrays). The first object that carries an ``articleBody`` wins for the body;
    title/author/datePublished are harvested from any Article-typed object. Returns
    empty strings when nothing usable is found.
    """
    out = {"body": "", "title": "", "author": "", "published": ""}
    if not html_text:
        return out
    try:
        doc = lxml_html.fromstring(html_text)
    except Exception:
        return out

    for script in doc.xpath('//script[@type="application/ld+json"]'):
        raw = script.text or script.text_content() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        for obj in _iter_jsonld(data):
            if not isinstance(obj, dict):
                continue
            types = _ld_types(obj)
            is_article = bool(types & _ARTICLE_TYPES) or bool(obj.get("articleBody"))
            if not is_article:
                continue
            if not out["body"] and obj.get("articleBody"):
                out["body"] = _strip_html(str(obj["articleBody"]))
            if not out["title"]:
                out["title"] = _norm_ws(str(obj.get("headline") or obj.get("name") or ""))
            if not out["author"]:
                out["author"] = _ld_author(obj.get("author"))
            if not out["published"]:
                out["published"] = _norm_ws(
                    str(obj.get("datePublished") or obj.get("dateModified") or "")
                )
    return out


# ── HTML → Markdown ─────────────────────────────────────────────────────────────

_HANDLED_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}
_DROP_XPATH = "//script|//style|//noscript|//nav|//header|//footer|//aside|//form|//iframe|//svg"


def _main_content_node(doc):
    """Pick the container with the most paragraph text (rough readability)."""
    best, best_score = None, 0
    for el in doc.iter():
        if not isinstance(el.tag, str) or el.tag not in (
            "article",
            "main",
            "div",
            "section",
            "body",
        ):
            continue
        ps = el.findall(".//p")
        if not ps:
            continue
        score = sum(len(_norm_ws(p.text_content())) for p in ps)
        if score > best_score:
            best, best_score = el, score
    return best if best is not None else doc


def html_to_markdown(html_text: str, base_url: str = "") -> str:
    """Convert an HTML document to Markdown: strip chrome, keep headings/lists/quotes."""
    if not html_text:
        return ""
    try:
        doc = lxml_html.fromstring(html_text)
    except Exception:
        return _strip_html(html_text)

    for bad in doc.xpath(_DROP_XPATH):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    root = _main_content_node(doc)
    lines: list[str] = []
    for el in root.iter():
        if not isinstance(el.tag, str) or el.tag not in _HANDLED_TAGS:
            continue
        # Only emit the top-most handled block; nested blocks fold into its text.
        if any(isinstance(a.tag, str) and a.tag in _HANDLED_TAGS for a in el.iterancestors()):
            continue
        text = _norm_ws(el.text_content())
        if not text:
            continue
        if el.tag == "pre":
            code = el.text_content().strip("\n")
            lines.append(f"```\n{code}\n```")
        elif el.tag == "blockquote":
            lines.append(f"> {text}")
        elif el.tag == "li":
            lines.append(f"- {text}")
        elif el.tag.startswith("h") and len(el.tag) == 2 and el.tag[1].isdigit():
            lines.append(f"{'#' * int(el.tag[1])} {text}")
        else:
            lines.append(text)

    md = "\n\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _extract_title(html_text: str) -> str:
    m = _TITLE_RE.search(html_text)
    if not m:
        return ""
    import html as _html

    return _norm_ws(_html.unescape(m.group(1)))


# ── Proxy-layer output parsers ──────────────────────────────────────────────────


def _proxy_error(text: str) -> str | None:
    """Detect a proxy-service JSON error envelope (r.jina.ai returns HTTP 200 + JSON).

    e.g. ``{"data":null,"code":403,"name":"AbuseAlleviationError","message":"..."}``.
    Returns a short reason string, or None when ``text`` is normal Markdown.
    """
    head = text.lstrip()[:400]
    if not head.startswith("{"):
        return None
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    if obj.get("data") is None and (obj.get("code") or obj.get("status")):
        name = obj.get("name") or "error"
        return f"proxy {obj.get('code') or obj.get('status')} {name}"
    return None


def parse_jina_output(text: str) -> dict[str, str]:
    """Parse r.jina.ai's ``Title:/URL Source:/.../Markdown Content:`` envelope."""
    title = published = ""
    body = text
    marker = "\nMarkdown Content:\n"
    if marker in text:
        head, body = text.split(marker, 1)
        for line in head.splitlines():
            if line.startswith("Title:"):
                title = line[len("Title:") :].strip()
            elif line.startswith("Published Time:"):
                published = line[len("Published Time:") :].strip()
    else:
        body = text
    return {"title": title, "published": published, "body": body.strip()}


def parse_defuddle_output(text: str) -> dict[str, str]:
    """Parse defuddle.md's leading ``---`` YAML frontmatter + Markdown body."""
    out = {"title": "", "author": "", "published": "", "body": text}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml

                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                out["title"] = str(meta.get("title") or "")
                out["author"] = str(meta.get("author") or "")
                out["published"] = str(meta.get("published") or meta.get("date") or "")
            out["body"] = parts[2].strip()
    return out


# ── Strategy plumbing ───────────────────────────────────────────────────────────


def _ok(strategy: str, url: str, markdown: str, **meta: str) -> WebFetchResult:
    return WebFetchResult(success=True, url=url, markdown=markdown, strategy=strategy, **meta)


def _fail(strategy: str, url: str, error: str) -> WebFetchResult:
    return WebFetchResult(success=False, url=url, strategy=strategy, error=error)


def _get(client: httpx.Client, url: str, headers: dict | None, timeout: float) -> httpx.Response:
    return client.get(url, headers=headers or {}, timeout=timeout)


def _ua_fetch(
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    timeout: float,
    max_bytes: int,
    strategy: str,
) -> WebFetchResult:
    """Fetch with a given header set: JSON-LD articleBody first, else HTML→Markdown."""
    try:
        resp = _get(client, url, headers, timeout)
    except Exception as e:  # noqa: BLE001 — any transport error is just a failed layer
        return _fail(strategy, url, f"request error: {type(e).__name__}: {e}")
    if resp.status_code >= 400:
        return _fail(strategy, url, f"HTTP {resp.status_code}")

    body = resp.text[:max_bytes]
    ld = extract_jsonld_article(body)
    if ld["body"] and len(ld["body"]) > 200:
        md = ld["body"]
        if ld["title"]:
            md = f"# {ld['title']}\n\n{md}"
        return _ok(
            strategy,
            url,
            md,
            title=ld["title"] or _extract_title(body),
            author=ld["author"],
            published=ld["published"],
        )

    md = html_to_markdown(body, url)
    if not has_content(md) or is_paywall_content(md):
        return _fail(strategy, url, "paywalled or too thin")
    return _ok(strategy, url, md, title=_extract_title(body))


# ── Layer 1: proxy services ─────────────────────────────────────────────────────


def _strategy_jina(client, url, timeout, max_bytes) -> WebFetchResult:
    try:
        resp = _get(client, f"https://r.jina.ai/{url}", None, timeout)
    except Exception as e:  # noqa: BLE001
        return _fail("jina", url, f"request error: {type(e).__name__}: {e}")
    if resp.status_code >= 400:
        return _fail("jina", url, f"HTTP {resp.status_code}")
    text = resp.text[:max_bytes]
    perr = _proxy_error(text)
    if perr:
        return _fail("jina", url, perr)
    parsed = parse_jina_output(text)
    if not has_content(parsed["body"]) or is_paywall_content(parsed["body"]):
        return _fail("jina", url, "paywalled or too thin")
    return _ok("jina", url, parsed["body"], title=parsed["title"], published=parsed["published"])


def _strategy_defuddle(client, url, timeout, max_bytes) -> WebFetchResult:
    try:
        resp = _get(client, f"https://defuddle.md/{url}", None, timeout)
    except Exception as e:  # noqa: BLE001
        return _fail("defuddle", url, f"request error: {type(e).__name__}: {e}")
    if resp.status_code >= 400:
        return _fail("defuddle", url, f"HTTP {resp.status_code}")
    text = resp.text[:max_bytes]
    perr = _proxy_error(text)
    if perr:
        return _fail("defuddle", url, perr)
    parsed = parse_defuddle_output(text)
    if not has_content(parsed["body"]) or is_paywall_content(parsed["body"]):
        return _fail("defuddle", url, "paywalled or too thin")
    return _ok(
        "defuddle",
        url,
        parsed["body"],
        title=parsed["title"],
        author=parsed["author"],
        published=parsed["published"],
    )


# ── Layer 2: site-specific bot UAs ──────────────────────────────────────────────


def _strategy_googlebot(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, GOOGLEBOT_DOMAINS):
        return None
    headers = {
        "User-Agent": _GOOGLEBOT_UA,
        "X-Forwarded-For": "66.249.66.1",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml",
        "Cookie": "",
    }
    return _ua_fetch(client, url, headers, timeout, max_bytes, "googlebot_ua")


def _strategy_bingbot(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, BINGBOT_DOMAINS):
        return None
    headers = {
        "User-Agent": _BINGBOT_UA,
        "Referer": "https://www.bing.com/",
        "Accept": "text/html,application/xhtml+xml",
        "Cookie": "",
    }
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bingbot_ua")


# ── Layer 3: generic paywall bypass ─────────────────────────────────────────────


def _strategy_bypass_googlebot(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, PAYWALL_DOMAINS):
        return None
    headers = {
        "User-Agent": _GOOGLEBOT_UA,
        "X-Forwarded-For": "66.249.66.1",
        "Referer": "https://www.google.com/",
        "Accept": "text/html,application/xhtml+xml",
        "Cookie": "",
    }
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bypass_googlebot")


def _strategy_bypass_bingbot(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, PAYWALL_DOMAINS):
        return None
    headers = {
        "User-Agent": _BINGBOT_UA,
        "Referer": "https://www.bing.com/",
        "Accept": "text/html,application/xhtml+xml",
        "Cookie": "",
    }
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bypass_bingbot")


def _strategy_bypass_facebook(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, FACEBOOK_REF_DOMAINS):
        return None
    headers = {"User-Agent": _BROWSER_UA, "Referer": "https://www.facebook.com/", "Cookie": ""}
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bypass_facebook_ref")


def _strategy_bypass_twitter(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, PAYWALL_DOMAINS):
        return None
    headers = {"User-Agent": _BROWSER_UA, "Referer": "https://t.co/", "Cookie": ""}
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bypass_twitter_ref")


def _strategy_bypass_amp(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, AMP_DOMAINS):
        return None
    candidates = [f"{url}{s}" for s in ("/amp", "?outputType=amp", ".amp.html", "?amp")]
    # WSJ-style: path.html → path.amp.html
    if url.endswith(".html"):
        candidates.insert(0, url[: -len(".html")] + ".amp.html")
    elif url.endswith("/"):
        candidates.insert(0, url + "amp")
    last = _fail("bypass_amp", url, "no amp variant")
    for amp_url in candidates:
        if amp_url == url:
            continue
        try:
            resp = _get(client, amp_url, {"User-Agent": _DEFAULT_UA}, timeout)
        except Exception:
            continue
        if resp.status_code >= 400:
            continue
        ld = extract_jsonld_article(resp.text[:max_bytes])
        if ld["body"] and len(ld["body"]) > 200:
            md = f"# {ld['title']}\n\n{ld['body']}" if ld["title"] else ld["body"]
            return _ok("bypass_amp", url, md, title=ld["title"], author=ld["author"])
        md = html_to_markdown(resp.text[:max_bytes], amp_url)
        if has_content(md) and not is_paywall_content(md):
            return _ok("bypass_amp", url, md, title=_extract_title(resp.text[:max_bytes]))
        last = _fail("bypass_amp", url, "amp page paywalled or thin")
    return last


def _strategy_bypass_eu_xff(client, url, timeout, max_bytes) -> WebFetchResult | None:
    if not _domain_matches(url, PAYWALL_DOMAINS):
        return None
    headers = {
        "User-Agent": _BROWSER_UA,
        "X-Forwarded-For": "185.100.87.3",  # EU IP (deterministic; original used RANDOM)
        "Referer": "https://www.google.com/",
        "Cookie": "",
    }
    return _ua_fetch(client, url, headers, timeout, max_bytes, "bypass_eu_xff")


# ── Layer 4: archive.today + Google cache ───────────────────────────────────────


def _strategy_archive_today(client, url, timeout, max_bytes) -> WebFetchResult:
    archive_url = f"https://archive.today/newest/{url}"
    try:
        resp = _get(client, archive_url, {"User-Agent": _BROWSER_UA}, timeout)
    except Exception as e:  # noqa: BLE001
        return _fail("archive_today", url, f"request error: {type(e).__name__}: {e}")
    if resp.status_code >= 400:
        return _fail("archive_today", url, f"HTTP {resp.status_code}")
    html_text = resp.text[:max_bytes]
    if is_captcha_page(html_text):
        return _fail("archive_today", url, f"captcha: {archive_url}")
    ld = extract_jsonld_article(html_text)
    if ld["body"] and len(ld["body"]) > 200:
        md = f"# {ld['title']}\n\n{ld['body']}" if ld["title"] else ld["body"]
        return _ok("archive_today", url, md, title=ld["title"], author=ld["author"])
    md = html_to_markdown(html_text, archive_url)
    if not has_content(md):
        return _fail("archive_today", url, "no archived content")
    return _ok("archive_today", url, md, title=_extract_title(html_text))


def _strategy_google_cache(client, url, timeout, max_bytes) -> WebFetchResult:
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
    try:
        resp = _get(client, cache_url, {"User-Agent": _BROWSER_UA}, timeout)
    except Exception as e:  # noqa: BLE001
        return _fail("google_cache", url, f"request error: {type(e).__name__}: {e}")
    if resp.status_code >= 400:
        return _fail("google_cache", url, f"HTTP {resp.status_code}")
    md = html_to_markdown(resp.text[:max_bytes], cache_url)
    if not has_content(md):
        return _fail("google_cache", url, "no cached content")
    return _ok("google_cache", url, md, title=_extract_title(resp.text[:max_bytes]))


# ── Orchestrator ────────────────────────────────────────────────────────────────

_Strategy = Callable[..., "WebFetchResult | None"]


def _strategy_chain(url: str, allow_archive: bool) -> list[tuple[str, _Strategy]]:
    """The ordered cascade. Domain-gated layers self-skip (return None)."""
    chain: list[tuple[str, _Strategy]] = [
        ("jina", _strategy_jina),
        ("defuddle", _strategy_defuddle),
        ("googlebot_ua", _strategy_googlebot),
        ("bingbot_ua", _strategy_bingbot),
        ("bypass_googlebot", _strategy_bypass_googlebot),
        ("bypass_bingbot", _strategy_bypass_bingbot),
        ("bypass_facebook_ref", _strategy_bypass_facebook),
        ("bypass_twitter_ref", _strategy_bypass_twitter),
        ("bypass_amp", _strategy_bypass_amp),
        ("bypass_eu_xff", _strategy_bypass_eu_xff),
    ]
    if allow_archive:
        chain.append(("archive_today", _strategy_archive_today))
        chain.append(("google_cache", _strategy_google_cache))
    return chain


def fetch_web_markdown(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    allow_archive: bool = True,
) -> WebFetchResult:
    """Fetch ``url`` as clean Markdown, trying the six-layer cascade in order.

    ``client`` (an httpx client, e.g. backed by a MockTransport) is used as-is and
    not closed — the caller owns it. When omitted, a client honouring
    ``STRATUM_WEB_FETCH_PROXY`` is created and closed here.
    """
    url = (url or "").strip()
    if not is_fetchable_url(url):
        return WebFetchResult(
            success=False, url=url, strategy="guard", error="unsupported or non-public url"
        )

    timeout = timeout or _default_timeout()
    owns_client = client is None
    if client is None:
        client = make_client(timeout)

    attempts: list[dict[str, Any]] = []
    try:
        for name, fn in _strategy_chain(url, allow_archive):
            try:
                res = fn(client, url, timeout, max_bytes)
            except Exception as e:  # noqa: BLE001 — a layer must never abort the cascade
                log.warning("web_fetch_cascade layer=%s raised %s", name, e)
                res = _fail(name, url, f"layer error: {type(e).__name__}: {e}")
            if res is None:
                continue  # not applicable for this domain
            attempts.append(
                {
                    "strategy": res.strategy,
                    "ok": res.success,
                    "chars": res.char_count,
                    "error": res.error,
                }
            )
            if res.success:
                res.attempts = attempts
                log.info(
                    "web_fetch_cascade ok url=%s strategy=%s chars=%d",
                    url[:80],
                    res.strategy,
                    res.char_count,
                )
                return res
        return WebFetchResult(
            success=False,
            url=url,
            strategy="exhausted",
            error="all fetch strategies failed",
            attempts=attempts,
        )
    finally:
        if owns_client:
            client.close()
