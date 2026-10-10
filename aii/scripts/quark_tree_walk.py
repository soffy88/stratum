#!/usr/bin/env python3
"""递归遍历夸克网盘目录树。

关键：file/sort 只接受 GET + URL query 参数（POST 返回 405），
且必须显式带 pdir_fid，之前用 POST body 传会被忽略而返回根目录。
"""
from __future__ import annotations
import json, ssl, sys, time, urllib.parse, urllib.request
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1] / "quark_pipeline"
COOKIE = (PIPE / "quark_cookies_full.txt").read_text(encoding="utf-8").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 "
      "Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch")
BASE = "https://drive.quark.cn/1/clouddrive/file/sort"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=CTX))

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def list_dir(pdir: str) -> list[dict]:
    """GET + query 参数（POST body 会被忽略并返回根目录）。分页直到返回不足一页。"""
    out: list[dict] = []
    page, token = 1, None
    while page <= 50:
        q = {"pr": "ucpro", "fr": "pc", "uc_param_str": "",
             "pdir_fid": pdir, "_page": page, "_size": 200}
        if token:
            q["_token"] = token
        url = f"{BASE}?{urllib.parse.urlencode(q)}"
        req = urllib.request.Request(url, headers={
            "Cookie": COOKIE, "Referer": "https://pan.quark.cn/",
            "User-Agent": UA}, method="GET")
        with OP.open(req, timeout=30) as r:
            d = json.loads(r.read().decode()) or {}
        # 注意：list 嵌在 data 里，不是顶层
        lst = (d.get("data") or {}).get("list") or d.get("list") or []
        out.extend(lst)
        if len(lst) < 200:
            break
        token = (d.get("metadata") or {}).get("token")
        if not token:
            break
        page += 1
    return out

FILES: list[dict] = []
DIRS: list[dict] = []

def walk(pdir: str, path: str, depth: int = 0):
    if depth > 6: return
    try: items = list_dir(pdir)
    except Exception as e:
        log(f"  ! {path or '/'}: {str(e)[:60]}"); return
    for it in items:
        cur = f"{path}/{it['file_name']}" if path else it["file_name"]
        if str(it.get("file_type")) == "0":
            DIRS.append({"fid": it["fid"], "name": it["file_name"], "path": cur})
            walk(it["fid"], cur, depth + 1)
        else:
            FILES.append({"fid": it["fid"], "name": it["file_name"],
                          "size": it.get("size", 0), "path": cur})

if __name__ == "__main__":
    import hashlib
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    roots = json.loads(Path(arg).read_text(encoding="utf-8")) if arg else []
    for r in roots:
        walk(r["fid"], r.get("name", ""))
    tot = sum(f["size"] for f in FILES)
    log(f"目录 {len(DIRS)} · 文件 {len(FILES)} · {tot/1024**3:.2f} GB")
    for f in sorted(FILES, key=lambda x: -x["size"]):
        log(f"  {f['size']/1024**2:>9.1f}MB  {f['path']}")
    tag = hashlib.md5(str([r["fid"] for r in roots]).encode()).hexdigest()[:8]
    out = PIPE / f"quark_tree_{tag}.json"
    out.write_text(json.dumps({"dirs": DIRS, "files": FILES}, ensure_ascii=False),
                   encoding="utf-8")
    log(f"已写入 {out}")
