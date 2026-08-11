#!/usr/bin/env python3
"""★2026-08-10 arXiv 数学论文 → math 飞轮供料。

math(0-LLM 程序化) 吃「编号定理/定义/证明」— arXiv 数学论文定理密集, 完美匹配。
拉取: arXiv API(math 各分类最新) → 下载 PDF → /home/soffy/books/数学
      → math_convert 自动转 → books/MD/英文数学 → math 飞轮 discover。

去重: watchdog/arxiv_math_state.json(已拉 arxiv_id)。
用法: .venv/bin/python scripts/arxiv_math_fetch.py [--max N] [--per-cat K]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = Path("/home/soffy/books/论文")  # ★2026-08-10 论文精髓通道: PDF 源 → convert → books/MD/论文 → paper 飞轮 BU+skill
STATE = ROOT / "watchdog" / "arxiv_math_state.json"
ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf/"

# 数学分类(每类拉最新)
CATS = ["math.AG", "math.NT", "math.AP", "math.CO", "math.PR", "math.ST",
        "math.DS", "math.FA", "math.AC", "math.GR", "math.GT", "math.RT",
        "math.OA", "math.SG", "math.AT", "math.SP"]


def _opener():
    # 走 7890 代理(arXiv 国内可达性不稳); 本地/内网不在此列
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": "http://127.0.0.1:7890",
                                     "https": "http://127.0.0.1:7890"}))


def _load_state() -> set[str]:
    try:
        return set(json.loads(STATE.read_text()).get("ids", []))
    except Exception:
        return set()


def _save_state(ids: set[str]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"ids": sorted(ids)}, indent=2))


def _query(cat: str, per_cat: int, op: urllib.request.OpenerDirector) -> list[tuple[str, str]]:
    """arXiv API 返回 [(arxiv_id, title)]。"""
    url = f"{ARXIV_API}?search_query=cat:{cat}&sortBy=submittedDate&sortOrder=descending&max_results={per_cat}"
    try:
        with op.open(url, timeout=30) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  ⚠ {cat} API 失败: {str(e)[:60]}")
        return []
    out = []
    for m in re.finditer(r"<entry>.*?</entry>", xml, re.S):
        e = m.group(0)
        aid = re.search(r"<id>http://arxiv.org/abs/([^<]+)</id>", e)
        title = re.search(r"<title>([^<]+)</title>", e)
        if aid:
            out.append((aid.group(1).strip(),
                        (title.group(1).strip() if title else "")[:200]))
    return out


def _download(arxiv_id: str, op: urllib.request.OpenerDirector) -> Path | None:
    """下载 PDF 到 books/数学。返回路径或 None。"""
    url = f"{ARXIV_PDF}{arxiv_id}"
    out = DEST / f"arxiv_{arxiv_id}.pdf"
    if out.exists():
        return out
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) arxiv-math-fetch/1.0"})
        with op.open(req, timeout=120) as r, open(out, "wb") as fh:
            total = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
                if total > 30 * 1048576:  # 30MB 上限(超大论文跳过)
                    fh.close()
                    out.unlink()
                    return None
        return out
    except Exception as e:
        print(f"  ⚠ 下载 {arxiv_id} 失败: {str(e)[:60]}")
        try:
            out.unlink()
        except OSError:
            pass
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=20, help="本轮最多下载 PDF 数")
    ap.add_argument("--per-cat", type=int, default=5)
    args = ap.parse_args()

    op = _opener()
    done = _load_state()
    DEST.mkdir(parents=True, exist_ok=True)

    new = 0
    for cat in CATS:
        if new >= args.max:
            break
        papers = _query(cat, args.per_cat, op)
        for aid, title in papers:
            if new >= args.max:
                break
            if aid in done:
                continue
            if re.search(r"erratum|comment|correction", title, re.I):
                done.add(aid)
                continue
            p = _download(aid, op)
            if p:
                done.add(aid)
                new += 1
                print(f"  📥 [{cat}] arxiv_{aid} {title[:45]}")
            else:
                done.add(aid)  # 下载失败也标记, 防反复
            time.sleep(2)  # arXiv API 礼貌间隔

    _save_state(done)
    print(f"\n完成: 新增 {new} 篇 → /home/soffy/books/数学 (math_convert → math 飞轮)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
