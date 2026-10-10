#!/usr/bin/env python3
"""实时遍历夸克网盘目录树，导出完整清单（含目录路径与大小）。

用于盘点实际存在的文件，而不是依赖可能过期的 catalog 快照。
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
OUT = PIPE / "quark_live_tree.json"

API = "https://drive.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160"
)


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx)
    )


OP = opener()
COOKIE = COOKIE_FILE.read_text(encoding="utf-8").strip()


def api(url: str, body: dict | None = None, method: str = "POST"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Cookie": COOKIE, "Referer": "https://pan.quark.cn/",
                 "User-Agent": UA, "Content-Type": "application/json"},
        method=method,
    )
    with OP.open(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def list_dir(fid: str, token: str | None = None):
    body = {"pdir_fid": fid, "limit": 1000, "sort": "file_type:asc,updated_at:desc"}
    if token:
        body["next_page_token"] = token
    res = api(f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=", body, "GET")
    return res.get("data", {}) or {}


FILES: list[dict] = []
DIRS: list[dict] = []


def walk(fid: str, path: str, depth: int = 0) -> None:
    if depth > 8:
        return
    token = None
    while True:
        try:
            data = list_dir(fid, token)
        except Exception as e:
            log(f"  ! 读取 {path} 失败: {e}")
            return
        for it in data.get("list", []):
            cur = f"{path}/{it['file_name']}" if path else it["file_name"]
            if it.get("file_type") == 0:
                DIRS.append({"fid": it["fid"], "name": it["file_name"], "path": cur})
                walk(it["fid"], cur, depth + 1)
            else:
                FILES.append({
                    "fid": it["fid"], "name": it["file_name"],
                    "size": it.get("size", 0), "path": cur,
                })
        token = data.get("next_page_token")
        if not token:
            break


def main() -> None:
    log("开始遍历夸克网盘目录树 ...")
    walk("0", "")
    total = sum(f["size"] for f in FILES)
    log(f"目录 {len(DIRS)} 个 · 文件 {len(FILES)} 个 · 合计 {total / 1024**4:.2f} TB")
    OUT.write_text(json.dumps({"dirs": DIRS, "files": FILES}, ensure_ascii=False), encoding="utf-8")
    log(f"已写入 {OUT}")


if __name__ == "__main__":
    main()
