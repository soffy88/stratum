#!/usr/bin/env python3
"""夸克网盘按需拉取 CLI — 搜索/列表/下载 PDF/EPUB/视频等。

用法:
    cd aii && .venv/bin/python scripts/quark_fetch.py search 经济学          # 搜索
    cd aii && .venv/bin/python scripts/quark_fetch.py list                  # 根目录列表
    cd aii && .venv/bin/python scripts/quark_fetch.py list <dir_fid>        # 目录列表
    cd aii && .venv/bin/python scripts/quark_fetch.py download <关键词> -o /home/soffy/quark  # 按名下载

凭据: quark_pipeline/quark_cookies_full.txt(浏览器 F12 复制的完整 Cookie 头)。
过期(401 require login)时重新复制最新 Cookie 覆盖该文件即可。

下载链接限时 1 小时; 下载支持断点续传(临时 .part 文件)。
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
COOKIE_FILE = ROOT / "quark_pipeline" / "quark_cookies_full.txt"
API = "https://drive-pc.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _cookie() -> str:
    return COOKIE_FILE.read_text().strip()


def _req(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Cookie": _cookie(),
            "Referer": "https://pan.quark.cn/",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("status") != 200:
        raise RuntimeError(f"API 错误: {payload.get('status')} {payload.get('message')} "
                           f"(cookie 过期? 重新复制浏览器最新 Cookie 覆盖 {COOKIE_FILE.name})")
    return payload


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n}GB"


def cmd_list(fid: str = "0", page: int = 1, size: int = 50) -> None:
    url = f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={fid}&_page={page}&_size={size}&_sort=file_type:asc,file_name:asc"
    d = _req(url)["data"]
    items = d.get("list", [])
    if not items:
        print("(空)")
        return
    for f in items:
        kind = "📁" if f.get("dir") else ("🎬" if f.get("category") == 1 else "📄")
        print(f"{kind} {f['fid'][:12]}  {f['file_name']:<50} {_fmt_size(f.get('size') or 0)}")
    print(f"\n共 {len(items)} 项 (metadata._total={d.get('metadata', {}).get('_total')})")


def cmd_search(keyword: str, size: int = 20) -> None:
    from urllib.parse import quote
    url = f"{API}/1/clouddrive/file/search?pr=ucpro&fr=pc&uc_param_str=&_page=1&_size={size}&keyword={quote(keyword)}"
    items = _req(url)["data"].get("list", [])
    if not items:
        print(f"未搜到「{keyword}」")
        return
    for f in items:
        kind = "📁" if f.get("dir") else ("🎬" if f.get("category") == 1 else "📄")
        print(f"{kind} {f['fid'][:12]}  {f['file_name']:<50} {_fmt_size(f.get('size') or 0)}")


def _resolve_fids(keyword: str, limit: int = 5) -> list[dict]:
    """按文件名关键词找文件(搜索接口), 返回 [item...]"""
    from urllib.parse import quote
    url = f"{API}/1/clouddrive/file/search?pr=ucpro&fr=pc&uc_param_str=&_page=1&_size={limit}&keyword={quote(keyword)}"
    items = _req(url)["data"].get("list", [])
    files = [f for f in items if f.get("file")]
    if not files:
        # 回退: 根目录+常见目录里按名字模糊匹配
        for fid in ("0",):
            lst = _req(f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=&pdir_fid={fid}&_page=1&_size=200&_sort=file_type:asc,file_name:asc")["data"].get("list", [])
            for f in lst:
                if f.get("file") and keyword.lower() in f["file_name"].lower():
                    files.append(f)
    return files


def _download_file(item: dict, out_dir: Path) -> Path:
    url = f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str="
    d = _req(url, "POST", {"fids": [item["fid"]]})["data"][0]
    dl = d.get("download_url")
    if not dl:
        raise RuntimeError(f"{item['file_name']}: 无 download_url")
    name = re.sub(r'[\\/:*?"<>|]', "_", item["file_name"])
    out = out_dir / name
    part = out_dir / (name + ".part")
    tmp = part if part.exists() else out
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
        "Referer": "https://pan.quark.cn/",
        "Cookie": _cookie(),  # ★CDN 防盗链: 下载链接也校验 Cookie
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
    }
    if part.exists():
        headers["Range"] = f"bytes={part.stat().st_size}-"
        print(f"  续传 {name} (已有 {part.stat().st_size} 字节)...", flush=True)
    req = urllib.request.Request(dl, headers=headers)
    mode = "ab" if part.exists() else "wb"
    # ★CDN 偶发 SSL 断连/抖动 → 失败重试 3 次
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp, open(tmp, mode) as fh:
                got = 0
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
            break
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2:
                raise
            print(f"  ⚠ 下载中断({type(e).__name__}), 重试 {attempt+2}/3...", flush=True)
            time.sleep(3)
    if part.exists():
        part.rename(out)
    print(f"  ✅ {name} ({_fmt_size(out.stat().st_size)})", flush=True)
    return out


def cmd_download(keyword: str, out_dir: Path, limit: int = 3) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = _resolve_fids(keyword, limit)
    if not items:
        print(f"未找到与「{keyword}」匹配的文件")
        return
    print(f"找到 {len(items)} 个文件:")
    for i, f in enumerate(items):
        print(f"  [{i}] {f['file_name']} ({_fmt_size(f.get('size') or 0)})")
    idxs = [i for i in range(len(items))]
    for i in idxs:
        print(f"\n下载 [{i}] {items[i]['file_name']} ...")
        _download_file(items[i], out_dir)


def main() -> int:
    ap = argparse.ArgumentParser(description="夸克网盘按需拉取")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="按关键词搜索")
    s.add_argument("keyword")
    sub.add_parser("list", help="列出目录(默认根目录)")
    l2 = sub.add_parser("ls", help="列出目录")
    l2.add_argument("fid", nargs="?", default="0")
    d = sub.add_parser("download", help="按关键词下载文件")
    d.add_argument("keyword")
    d.add_argument("-o", "--out", default=str(ROOT / "quark_downloads"))
    d.add_argument("--limit", type=int, default=3)
    args = ap.parse_args()

    try:
        if args.cmd == "list":
            cmd_list("0")
        elif args.cmd == "ls":
            cmd_list(args.fid)
        elif args.cmd == "search":
            cmd_search(args.keyword)
        elif args.cmd == "download":
            cmd_download(args.keyword, Path(args.out), args.limit)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
