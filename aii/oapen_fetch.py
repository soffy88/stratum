#!/usr/bin/env python3
"""OAPEN 开放教材抓取(★主机侧跑 — 容器到不了 library.oapen.org, 但主机直连可达).

链路: OAPEN REST 搜索 → 取自托管 PDF bitstream(application/pdf) → 下载到
      /books/{Economic|数学} → feeder(math/econ_convert) 自动转MD → 四个飞轮.

绕过历史坑:
  - 容器网络不可达 / 8766 主机代理没跑  → 本脚本直接在主机跑, 不走代理.
  - oprim._oapen_search 的 Unpaywall+Springer-only 过滤丢99%书 → 改用 OAPEN
    自己的 bitstream 直链(application/pdf), 不依赖 Unpaywall.

去重: 归一标题 vs 已有MD(/books/MD/**, /books/{Economic,数学}) ∪ 已入库标题.

用法: oapen_fetch.py            # dry-run(只列能下的)
      oapen_fetch.py --do       # 实际下载
      oapen_fetch.py --do --max 5   # 每个主题最多下5本(默认3)
"""
import os, re, sys, json, glob, time, subprocess, urllib.parse, urllib.request
from pathlib import Path

DO = "--do" in sys.argv
MAX = 3
if "--max" in sys.argv:
    try: MAX = int(sys.argv[sys.argv.index("--max") + 1])
    except Exception: pass

# 主题 → 目标目录(只喂 econ/math 四飞轮). query 用英文(OAPEN 以英文书为主).
TOPICS = [
    ("economics microeconomics",        "/home/soffy/books/Economic"),
    ("macroeconomics",                   "/home/soffy/books/Economic"),
    ("econometrics",                     "/home/soffy/books/Economic"),
    ("calculus analysis",                "/home/soffy/books/数学"),
    ("linear algebra",                   "/home/soffy/books/数学"),
    ("probability statistics",           "/home/soffy/books/数学"),
]

_UA = {"Accept": "application/json", "User-Agent": "oprim/1.0"}
_BASE = "https://library.oapen.org"


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or _UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def norm(s):
    s = re.sub(r'\(z-lib[^)]*\)|\(z-library[^)]*\)', '', s, flags=re.I)
    s = re.sub(r'\.(pdf|epub|md)$', '', s, flags=re.I)
    s = re.sub(r'[\s_\-（）()【】\[\]·,，.。、:：;；/]+', '', s)
    return s.lower()


def done_norms():
    done = set()
    for p in glob.glob("/home/soffy/books/MD/**/*.md", recursive=True):
        done.add(norm(Path(p).stem))
    for d in ("/home/soffy/books/Economic", "/home/soffy/books/数学"):
        for p in glob.glob(f"{d}/*.pdf") + glob.glob(f"{d}/*.epub"):
            done.add(norm(Path(p).stem))
    try:
        out = subprocess.run(
            ["docker", "exec", "aii-postgres", "psql", "-U", "aii", "-d", "aii_kg", "-tAc",
             "SELECT title FROM aii.ingested_substrate WHERE title IS NOT NULL"],
            capture_output=True, text=True, timeout=20).stdout
        for t in out.splitlines():
            if t.strip(): done.add(norm(t))
    except Exception as e:
        print(f"  ⚠ 取已入库清单失败(只按文件去重): {e}", file=sys.stderr)
    return done


def is_done(title, done):
    ns = norm(title)
    if ns in done: return True
    return any(len(e) >= 6 and (e in ns or ns in e) for e in done)


def pdf_bitstream(uuid):
    """返回该 item 的 application/pdf bitstream 直链(优先最大), 没有则 None."""
    try:
        bs = json.loads(_get(f"{_BASE}/rest/items/{uuid}/bitstreams"))
    except Exception:
        return None
    pdfs = [b for b in bs if 'pdf' in (b.get('mimeType') or '').lower()]
    if not pdfs:
        return None
    big = max(pdfs, key=lambda b: b.get('sizeBytes', 0))
    if big.get('sizeBytes', 0) < 200_000:   # <200KB 不像整本书
        return None
    return _BASE + big['retrieveLink'], big.get('sizeBytes', 0)


def safe_name(title):
    n = re.sub(r'[/\\:*?"<>|]+', ' ', title).strip()
    return n[:120]


def main():
    done = done_norms()
    print(f"已完成清单 {len(done)} 条. {'★实下' if DO else 'dry-run(加 --do 实下)'}, 每主题≤{MAX}本\n")
    total_new = 0
    for query, dstdir in TOPICS:
        print(f"=== [{query}] → {dstdir} ===")
        try:
            items = json.loads(_get(f"{_BASE}/rest/search?" +
                urllib.parse.urlencode({"query": query, "limit": "25", "expand": "bitstreams"})))
        except Exception as e:
            print(f"  搜索失败: {e}"); continue
        got = 0
        for it in items:
            if got >= MAX: break
            title = it.get('name') or ''
            uuid = it.get('uuid') or ''
            if not title or not uuid:
                continue
            if is_done(title, done):
                continue
            # 先用 search 自带的 bitstreams(expand)快速判, 没有再查详情
            bs = it.get('bitstreams') or []
            pdf = next((b for b in bs if 'pdf' in (b.get('mimeType') or '').lower()
                        and b.get('sizeBytes', 0) >= 200_000), None)
            link = (_BASE + pdf['retrieveLink'], pdf['sizeBytes']) if pdf else pdf_bitstream(uuid)
            if not link:
                continue
            url, sz = link
            fname = safe_name(title) + ".pdf"
            dst = os.path.join(dstdir, fname)
            print(f"  {'下载' if DO else '可下'}: {title[:50]} ({sz//1024}KB)")
            if DO:
                try:
                    data = _get(url, headers={"User-Agent": "oprim/1.0"}, timeout=120)
                    if data[:4] != b'%PDF':
                        print(f"    ✗ 非PDF, 跳过"); continue
                    with open(dst, 'wb') as f:
                        f.write(data)
                    done.add(norm(title)); total_new += 1
                    print(f"    ✓ 存 {dst}")
                except Exception as e:
                    print(f"    ✗ 下载失败: {e}"); continue
            got += 1
            time.sleep(1.0)   # 限速, 对 OAPEN 友好
    print(f"\n{'✓ 共下载 %d 本 → feeder 会自动转MD喂飞轮' % total_new if DO else '(dry-run, 加 --do 实下)'}")


if __name__ == "__main__":
    main()
