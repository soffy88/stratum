"""Unit tests for the web-fetch cascade, WeChat parser, and URL ingest channel.

All network is mocked: an ``httpx.MockTransport`` handler routes by URL host so the
cascade's layer order, JSON-LD extraction, and WeChat parsing are exercised without
touching the internet.
"""

from __future__ import annotations

import httpx
import pytest

from stratum.services import web_fetch_cascade as wfc
from stratum.services import wechat_fetch as wx
from stratum.services import web_ingest as wi

# ── fixtures ────────────────────────────────────────────────────────────────────

# A long, multi-paragraph body (so has_content's >8-lines gate is satisfied).
_MD_BODY = "\n\n".join(f"Paragraph {i}: " + ("focus is the new iq. " * 12) for i in range(12))

_ARTICLE_HTML = (
    "<html><head><title>Deep Work — Notes</title></head><body><article><h1>Deep Work</h1>"
    + "".join(f"<p>{'focus is the new iq. ' * 12}</p>" for _ in range(12))
    + "</article></body></html>"
)

_JSONLD_HTML = """
<html><head><title>ignored</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"NewsArticle",
 "headline":"The Paywalled Truth",
 "author":{"@type":"Person","name":"Ada Lovelace"},
 "datePublished":"2026-01-02T03:04:05Z",
 "articleBody":"%s"}
</script></head><body><p>teaser</p></body></html>
""" % ("This is the full body pulled from JSON-LD. " * 30)

_PAYWALL_HTML = "<html><body><h1>Subscribe to continue reading</h1><p>%s</p></body></html>" % (
    "Subscribe now for full access to this premium article. " * 40
)

_WECHAT_HTML = """
<html><head>
<meta property="og:title" content="如何学习数学" />
<meta property="og:image" content="https://mmbiz.qpic.cn/cover.jpg" />
<meta property="og:article:published_time" content="2026-03-04T05:06:07Z" />
</head><body>
<h1 id="activity-name">如何学习数学</h1>
<div id="js_content">
  <p>%s</p><p>%s</p>
</div>
<script>var nickname = "数学之美"; var author = "张三"; var ct = "1700000000";</script>
</body></html>
""" % ("先理解定义再看证明。 " * 30, "反复做习题才能内化。 " * 30)


def _client(routes: dict[str, tuple[int, str]]) -> httpx.Client:
    """Build a client whose transport replies from ``routes`` keyed by URL prefix."""

    def handler(request: httpx.Request) -> httpx.Response:
        for prefix, (status, body) in routes.items():
            if str(request.url).startswith(prefix):
                return httpx.Response(status, text=body)
        return httpx.Response(404, text="not found")

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


# ── pure helpers ────────────────────────────────────────────────────────────────


def test_domain_matches():
    assert wfc._domain_matches("https://www.nytimes.com/x", wfc.PAYWALL_DOMAINS)
    assert not wfc._domain_matches("https://example.com/x", wfc.PAYWALL_DOMAINS)


def test_is_fetchable_url_guards():
    assert wfc.is_fetchable_url("https://example.com/a")
    assert not wfc.is_fetchable_url("ftp://example.com/a")
    assert not wfc.is_fetchable_url("https://127.0.0.1/a")
    assert not wfc.is_fetchable_url("http://localhost/a")
    assert not wfc.is_fetchable_url("https://router.local/a")


def test_has_content_and_paywall_heuristics():
    assert wfc.has_content(_MD_BODY)
    assert not wfc.has_content("short")
    assert wfc.is_paywall_content("Please subscribe to continue reading this article")
    assert not wfc.is_paywall_content("Just a normal paragraph of text")


def test_has_content_rejects_paywall_shell():
    """A large, line-rich paywall/registration shell must NOT count as content.

    Regression: the twitter-referer layer accepted FT's "To read this article for
    free / Once registered, you can:" wall as an article because it cleared the
    line/char floor.
    """
    shell = "# Some Headline\n\n" + "\n\n".join(
        [
            "## Explore more offers.",
            "*   Global news & analysis",
            "*   Expert opinion",
            "*   [Read more here](https://example.com/a)",
            "*   Follow topics and set up personalised alerts",
        ]
        * 8
    )
    assert len(shell) > 500  # clears the raw-size floor...
    assert not wfc.is_paywall_content(shell)  # ...and the paywall regex misses it...
    assert not wfc.has_content(shell)  # ...but the prose gate still rejects it


def test_prose_stats_separates_article_from_navigation():
    nav = "\n".join(f"*   [Headline number {i} goes here](https://x.com/a/{i})" for i in range(40))
    lines, chars = wfc.prose_stats(nav)
    assert (lines, chars) == (0, 0)  # pure link list is not prose
    p_lines, p_chars = wfc.prose_stats(_MD_BODY)
    assert p_lines >= 3 and p_chars >= wfc._MIN_PROSE_CHARS


def test_has_article_body_thresholds():
    assert wfc.has_article_body(_MD_BODY)
    assert not wfc.has_article_body("")
    # long enough to clear the size floor but almost all navigation
    assert not wfc.has_article_body(("*   [nav item](https://x.com/p) " * 40) + "\n" + ("x" * 5000))


def test_html_to_markdown_keeps_structure():
    md = wfc.html_to_markdown(_ARTICLE_HTML)
    assert "# Deep Work" in md
    assert "focus is the new iq" in md


# ── JSON-LD extraction ──────────────────────────────────────────────────────────


def test_extract_jsonld_article():
    ld = wfc.extract_jsonld_article(_JSONLD_HTML)
    assert ld["title"] == "The Paywalled Truth"
    assert ld["author"] == "Ada Lovelace"
    assert ld["published"].startswith("2026-01-02")
    assert "full body pulled from JSON-LD" in ld["body"]


def test_extract_jsonld_handles_graph_and_list():
    html = (
        '<html><head><script type="application/ld+json">'
        '[{"@type":"WebSite","name":"x"},'
        '{"@graph":[{"@type":"Article","headline":"H","articleBody":"%s"}]}]'
        "</script></head></html>"
    ) % ("body text here " * 40)
    ld = wfc.extract_jsonld_article(html)
    assert ld["title"] == "H"
    assert "body text here" in ld["body"]


def test_extract_jsonld_empty_on_garbage():
    assert wfc.extract_jsonld_article("<html><body>no ld here</body></html>")["body"] == ""
    assert wfc.extract_jsonld_article("")["body"] == ""


# ── cascade order ───────────────────────────────────────────────────────────────


def test_cascade_order_lists_archive_last():
    names = [n for n, _ in wfc._strategy_chain("https://x.com/a", allow_archive=True)]
    assert names[0] == "jina"
    assert names[1] == "defuddle"
    assert names[-1] == "google_cache"
    assert "archive_today" in names


def test_cascade_order_without_archive():
    names = [n for n, _ in wfc._strategy_chain("https://x.com/a", allow_archive=False)]
    assert "archive_today" not in names
    assert "google_cache" not in names


def test_cascade_first_layer_jina_wins():
    """When jina succeeds, no later layer should be attempted."""
    routes = {
        "https://r.jina.ai/": (
            200,
            "Title: Jina Title\nURL Source: https://example.com\n\nMarkdown Content:\n" + _MD_BODY,
        ),
        "https://defuddle.md/": (200, "---\ntitle: d\n---\n" + _MD_BODY),
    }
    res = wfc.fetch_web_markdown("https://example.com/a", client=_client(routes))
    assert res.success
    assert res.strategy == "jina"
    assert res.title == "Jina Title"
    # only the jina attempt recorded
    assert [a["strategy"] for a in res.attempts] == ["jina"]


def test_cascade_falls_through_to_defuddle():
    routes = {
        "https://r.jina.ai/": (500, "boom"),
        "https://defuddle.md/": (200, "---\ntitle: Defuddle Title\nauthor: Bob\n---\n" + _MD_BODY),
    }
    res = wfc.fetch_web_markdown("https://example.com/a", client=_client(routes))
    assert res.success
    assert res.strategy == "defuddle"
    assert res.title == "Defuddle Title"
    assert res.author == "Bob"
    assert [a["strategy"] for a in res.attempts] == ["jina", "defuddle"]


def test_cascade_jsonld_via_bot_layer_for_paywall_domain():
    """A paywalled domain: jina/defuddle fail, googlebot UA returns JSON-LD articleBody."""
    routes = {
        "https://r.jina.ai/": (403, "blocked"),
        "https://defuddle.md/": (403, "blocked"),
        "https://www.nytimes.com/": (200, _JSONLD_HTML),
    }
    res = wfc.fetch_web_markdown("https://www.nytimes.com/2026/x.html", client=_client(routes))
    assert res.success
    assert res.strategy in ("googlebot_ua", "bypass_googlebot")
    assert "full body pulled from JSON-LD" in res.markdown


def test_cascade_domain_gated_layers_skipped_for_plain_domain():
    """A non-paywall domain must not attempt googlebot/bingbot/amp layers."""
    routes = {
        "https://r.jina.ai/": (500, "boom"),
        "https://defuddle.md/": (500, "boom"),
        "https://example.org/": (200, _ARTICLE_HTML),
    }
    res = wfc.fetch_web_markdown(
        "https://example.org/a", client=_client(routes), allow_archive=False
    )
    # example.org matches no gated domain list → cascade exhausts
    assert not res.success
    assert res.strategy == "exhausted"
    attempted = [a["strategy"] for a in res.attempts]
    assert "googlebot_ua" not in attempted
    assert "bypass_amp" not in attempted


def test_cascade_paywall_text_rejected_then_archive():
    """Direct page returns paywall text → layer fails → archive.today provides content."""
    routes = {
        "https://r.jina.ai/": (500, "boom"),
        "https://defuddle.md/": (500, "boom"),
        "https://www.nytimes.com/": (200, _PAYWALL_HTML),
        "https://archive.today/newest/": (200, _ARTICLE_HTML),
    }
    res = wfc.fetch_web_markdown("https://www.nytimes.com/2026/x.html", client=_client(routes))
    assert res.success
    assert res.strategy == "archive_today"


def test_cascade_guard_rejects_non_public():
    res = wfc.fetch_web_markdown("http://localhost/x")
    assert not res.success
    assert res.strategy == "guard"


# ── WeChat parsing ──────────────────────────────────────────────────────────────


def test_parse_wechat_html_extracts_fields():
    art = wx.parse_wechat_html(_WECHAT_HTML, "https://mp.weixin.qq.com/s/abc")
    assert art.success
    assert art.title == "如何学习数学"
    assert art.author == "张三"
    assert art.account == "数学之美"
    assert art.cover_url.endswith("cover.jpg")
    assert art.published.startswith("2026-03-04")
    assert "先理解定义" in art.markdown


def test_parse_wechat_html_js_ct_fallback():
    html = _WECHAT_HTML.replace(
        '<meta property="og:article:published_time" content="2026-03-04T05:06:07Z" />', ""
    )
    art = wx.parse_wechat_html(html, "https://mp.weixin.qq.com/s/abc")
    # falls back to var ct = 1700000000 → 2023-11-14 UTC
    assert art.published.startswith("2023-11-14")


def test_parse_wechat_html_empty():
    art = wx.parse_wechat_html("", "https://mp.weixin.qq.com/s/abc")
    assert not art.success


def test_fetch_wechat_article_via_mock():
    routes = {"https://mp.weixin.qq.com/": (200, _WECHAT_HTML)}
    art = wx.fetch_wechat_article("https://mp.weixin.qq.com/s/abc", client=_client(routes))
    assert art.success
    assert art.strategy == "wechat_http"
    assert art.char_count > 200


def test_is_wechat_url():
    assert wx.is_wechat_url("https://mp.weixin.qq.com/s/abc")
    assert not wx.is_wechat_url("https://example.com/a")


# ── ingest channel ──────────────────────────────────────────────────────────────


def test_build_frontmatter_has_routing_key():
    fm = wi.build_frontmatter(
        title="A: B",
        url="https://example.com/x",
        author="Ada",
        published="2026-01-01",
        source_type="web",
        strategy="jina",
        domain="economics",
    )
    assert "doc_type: paper" in fm  # routing key
    assert "doc_kind: article" in fm
    assert 'title: "A: B"' in fm  # colon-safe quoting
    assert 'domain: "economics"' in fm


def test_ingest_url_writes_file(tmp_path):
    routes = {"https://r.jina.ai/": (200, "Title: T\n\nMarkdown Content:\n" + _MD_BODY)}
    res = wi.ingest_url(
        "https://example.com/a", sink=tmp_path, client=_client(routes), domain="econ"
    )
    assert res.success
    assert res.source_type == "web"
    out = tmp_path / res.path.split("/")[-1]
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "doc_type: paper" in text
    assert "source_url:" in text
    assert "# T" in text


def test_ingest_url_idempotent(tmp_path):
    routes = {"https://r.jina.ai/": (200, "Title: T\n\nMarkdown Content:\n" + _MD_BODY)}
    c = _client(routes)
    first = wi.ingest_url("https://example.com/a", sink=tmp_path, client=c)
    second = wi.ingest_url("https://example.com/a", sink=tmp_path, client=c)
    assert first.success and second.success
    assert not first.skipped
    assert second.skipped  # same URL → same path → skipped
    assert first.path == second.path


def test_ingest_url_dry_run_writes_nothing(tmp_path):
    routes = {"https://r.jina.ai/": (200, "Title: T\n\nMarkdown Content:\n" + _MD_BODY)}
    res = wi.ingest_url(
        "https://example.com/a", sink=tmp_path, client=_client(routes), dry_run=True
    )
    assert res.success
    # dry-run must not write the output document (tmp_path may hold fixture files)
    assert not list(tmp_path.glob("*.md"))


def test_ingest_url_wechat_dispatch(tmp_path):
    routes = {"https://mp.weixin.qq.com/": (200, _WECHAT_HTML)}
    res = wi.ingest_url("https://mp.weixin.qq.com/s/abc", sink=tmp_path, client=_client(routes))
    assert res.success
    assert res.source_type == "wechat"
    assert "source_type: wechat" in (tmp_path / res.path.split("/")[-1]).read_text(encoding="utf-8")


def test_ingest_url_fetch_failure(tmp_path):
    routes = {"https://r.jina.ai/": (500, "boom")}
    res = wi.ingest_url("https://example.com/a", sink=tmp_path, client=_client(routes))
    assert not res.success
    assert res.error


def test_cli_ingest_url_json(tmp_path, capsys, monkeypatch):
    routes = {"https://r.jina.ai/": (200, "Title: T\n\nMarkdown Content:\n" + _MD_BODY)}
    real_ingest = wi.ingest_url

    def fake_ingest(url, **kw):
        kw.pop("timeout", None)
        kw.pop("sink", None)
        kw.pop("client", None)
        return real_ingest(url, sink=tmp_path, client=_client(routes), **kw)

    monkeypatch.setattr(wi, "ingest_url", fake_ingest)
    rc = wi.main(["ingest-url", "https://example.com/a", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"success": true' in out
    assert '"strategy": "jina"' in out


@pytest.mark.parametrize("bad", ["not a url", "ftp://x/y", "http://localhost/z"])
def test_ingest_url_rejects_bad(bad):
    res = wi.ingest_url(bad)
    assert not res.success
