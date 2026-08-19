#!/usr/bin/env python3
"""URL 增强抓取 CLI — 测试/手动抓取网页、微信文章、Twitter 线程.

集成 oprim.fetch_url_with_bypass + Crawl4AI + stratum enhanced fetcher.

用法:
    .venv/bin/python scripts/fetch_url.py <url> [--strategy auto|direct|wechat|twitter|crawl4ai|paywall|stealth]
    .venv/bin/python scripts/fetch_url.py --list  # 测试已知的付费墙/微信/Twitter URL

输出: Markdown 到 stdout, 或 --out 指定文件.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add stratum src to path (must be before any stratum imports)
# Script is at aii/scripts/fetch_url.py, stratum src is at ../src
_stratum_src = Path(__file__).resolve().parents[2] / "src"
if str(_stratum_src) not in sys.path:
    sys.path.insert(0, str(_stratum_src))

from stratum.services.web_fetch_enhanced import fetch_url_enhanced


async def fetch(url: str, strategy: str, out: str | None = None) -> None:
    print(f"🌐 抓取: {url}", file=sys.stderr)
    print(f"   策略: {strategy}", file=sys.stderr)

    result = await fetch_url_enhanced(url, strategy=strategy)

    if result.success:
        print(f"✅ 策略: {result.strategy_used}", file=sys.stderr)
        print(f"📄 标题: {result.title}", file=sys.stderr)
        print(f"📏 长度: {len(result.html)} 字符", file=sys.stderr)
        print(f"📦 类型: {result.content_type}", file=sys.stderr)

        if out:
            Path(out).write_text(result.html, encoding="utf-8")
            print(f"💾 已写入: {out}", file=sys.stderr)
        else:
            print("\n" + "=" * 60)
            print(result.html)
    else:
        print(f"❌ 失败: {result.error}", file=sys.stderr)
        sys.exit(1)


async def main() -> None:
    ap = argparse.ArgumentParser(description="增强 URL 抓取 (付费墙绕过 + JS渲染 + 多源适配)")
    ap.add_argument("url", nargs="?", help="URL to fetch")
    ap.add_argument("--strategy", default="auto",
                    help="抓取策略: auto | direct | wechat | twitter | crawl4ai | paywall | stealth")
    ap.add_argument("--out", help="输出文件路径 (默认 stdout)")
    ap.add_argument("--test", action="store_true", help="运行测试 URL 列表")
    args = ap.parse_args()

    if args.test:
        # 测试 URL 列表
        tests = [
            ("https://en.wikipedia.org/wiki/Opportunity_cost", "auto", "普通网页"),
            ("https://www.notion.so/product", "crawl4ai", "Notion (SPA)"),
            ("https://github.com/unclecode/crawl4ai", "crawl4ai", "GitHub (JS)"),
            ("https://mp.weixin.qq.com/s/example", "wechat", "微信公众号 (示例)"),
            ("https://x.com/elonmusk/status/123", "twitter", "Twitter (示例)"),
        ]
        for url, strat, desc in tests:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"🧪 {desc}: {url}", file=sys.stderr)
            try:
                await fetch(url, strat)
            except Exception as e:
                print(f"   ⚠ 跳过: {e}", file=sys.stderr)
        return

    if not args.url:
        ap.print_help()
        sys.exit(1)

    await fetch(args.url, args.strategy, args.out)


if __name__ == "__main__":
    asyncio.run(main())
