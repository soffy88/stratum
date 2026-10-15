#!/usr/bin/env python3
"""Real-network smoke test for the web-ingest fetchers (no mocks).

Fetches one normal webpage, one paywalled article, and WeChat articles, and prints
which cascade layer each used plus the body character count. Exercises the exact
production code path (``stratum.services.web_fetch_cascade`` / ``wechat_fetch``).

The proxy-service layers need the outbound relay; set it before running:

    STRATUM_WEB_FETCH_PROXY=http://127.0.0.1:1090 \
      uv run python scripts/web_ingest_smoke.py [--json out.json]

A paywalled fetch that exhausts every layer is a legitimate *result* here (the
cascade is a best-effort bypass), so the script always exits 0 and reports the
per-layer attempt log; read the output to see which layer (if any) produced the
body. Use ``--json`` to also write the raw result list for a SMOKE report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stratum.services.wechat_fetch import fetch_wechat_article, is_wechat_url  # noqa: E402
from stratum.services.web_fetch_cascade import fetch_web_markdown  # noqa: E402

# Real, verified URLs. The WSJ/NYT/FT slugs are genuine (a fabricated slug 404s
# and does not exercise the cascade).
CASES = [
    ("normal_wikipedia", "https://en.wikipedia.org/wiki/Opportunity_cost"),
    (
        "paywall_ft",
        "https://www.ft.com/content/cf5f1209-da29-4ce1-b425-0e83818bf9ec",
    ),
    (
        "paywall_wsj",
        "https://www.wsj.com/articles/"
        "even-before-openai-arrest-silicon-valley-was-bracing-for-spies-3c066db2",
    ),
    (
        "paywall_nyt",
        "https://www.nytimes.com/2026/08/28/world/europe/iran-regime-war-us.html",
    ),
]

WECHAT_URLS = [
    "https://mp.weixin.qq.com/s/IPieSj5VyahUWTvATceYGw",
    "https://mp.weixin.qq.com/s/OmPUu0HMGrdlbjrDvfn-1g",
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None, help="write the raw result list to this path")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("wechat_urls", nargs="*", default=WECHAT_URLS)
    args = ap.parse_args()

    out: list[dict] = []
    for label, url in CASES:
        res = fetch_web_markdown(url, timeout=args.timeout)
        out.append(
            {
                "label": label,
                "url": url,
                "success": res.success,
                "strategy": res.strategy,
                "chars": res.char_count,
                "title": res.title[:80],
                "error": res.error,
                "attempts": res.attempts,
            }
        )
        print(f"[{label}] {url}")
        print(f"   success={res.success} strategy={res.strategy} chars={res.char_count}")
        print(f"   title={res.title[:70]!r} error={res.error}")
        for a in res.attempts:
            print(f"      - {a['strategy']}: ok={a['ok']} chars={a['chars']} {a['error'] or ''}")

    for wx_url in args.wechat_urls:
        if not is_wechat_url(wx_url):
            print(f"[wechat] skip non-wechat url: {wx_url}")
            continue
        art = fetch_wechat_article(wx_url, timeout=args.timeout)
        out.append(
            {
                "label": "wechat",
                "url": wx_url,
                "success": art.success,
                "strategy": art.strategy,
                "chars": art.char_count,
                "title": art.title[:80],
                "author": art.author,
                "error": art.error,
            }
        )
        print(f"[wechat] {wx_url}")
        print(f"   success={art.success} strategy={art.strategy} chars={art.char_count}")
        print(f"   title={art.title[:70]!r} error={art.error}")

    if args.json:
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
