#!/usr/bin/env python3
"""夸克 Cookie 健康巡检。

定期验证 quark_cookies_full.txt 是否仍然有效（__pus token 约 24h 过期）。
失效时在日志中留下明确告警，便于在迁移任务空转前就发现问题。

用法:
    python3 quark_cookie_watchdog.py          # 巡检一次
    python3 quark_cookie_watchdog.py --loop   # 常驻，每 CHECK_INTERVAL_HOURS 小时巡检一次
"""

from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
COOKIE_FILE = PIPE / "quark_cookies_full.txt"
LOG_FILE = PIPE / "cookie_watchdog.log"
STATE_FILE = PIPE / "quark_transfer_2_4_state.json"
CATALOG = PIPE / "quark_catalog.json"

API = "https://drive.quark.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160"
)
CHECK_INTERVAL_HOURS = 12


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx)
    )


def _cookie() -> str:
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def _api(opener, url: str, body: dict | None = None, method: str = "POST"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Cookie": _cookie(),
            "Referer": "https://pan.quark.cn/",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
        method=method,
    )
    with opener.open(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pick_live_fid() -> str | None:
    """从目录树实时找一个仍存在的文件（catalog 会随删除而失效）。"""
    opener = _opener()

    def walk(fid: str, depth: int = 0):
        if depth > 3:
            return None
        try:
            res = _api(
                opener,
                f"{API}/1/clouddrive/file/sort?pr=ucpro&fr=pc&uc_param_str=",
                {"pdir_fid": fid, "limit": 200, "sort": "file_type:asc,updated_at:desc"},
                "GET",
            )
        except Exception:
            return None
        for it in res.get("data", {}).get("list", []):
            if it.get("file_type") == 0:
                got = walk(it["fid"], depth + 1)
                if got:
                    return got
            elif it.get("size", 0) > 1024 * 1024:
                return it["fid"]
        return None

    return walk("0")


def check_once() -> bool:
    """返回 True 表示 Cookie 健康。"""
    opener = _opener()

    # 1) 账号接口：最轻量，验证 token 是否被服务端接受
    try:
        out = subprocess.run(
            ["/home/soffy/.local/bin/quark-drive", "get-user-info"],
            capture_output=True, text=True, timeout=25,
        )
        if out.returncode == 0:
            used = json.loads(out.stdout).get("data", {}).get("vipInfo", {}).get("used", 0)
            log(f"  ✓ 账号接口正常，当前占用 {used / 1024**4:.3f} TB")
        else:
            log(f"  ⚠ 账号接口返回码 {out.returncode}（可能 Cookie 已失效）")
    except Exception as e:
        log(f"  ⚠ 账号接口异常: {e}")

    # 2) 下载链路：真正签发链接并取一个分片，这是 412 的真实触发点
    fid = pick_live_fid()
    if not fid:
        log("  ⚠ 未找到可用于测试的存活文件，跳过下载链路校验")
        return False

    try:
        res = _api(
            opener,
            f"{API}/1/clouddrive/file/download?pr=ucpro&fr=pc&uc_param_str=",
            {"fids": [fid]},
        )
    except Exception as e:
        code = getattr(e, "code", None)
        if code == 412:
            log("  ❌ 下载接口返回 412 —— Cookie 已过期，请更新 quark_cookies_full.txt")
            return False
        log(f"  ⚠ 下载接口异常: {e}")
        return False

    items = res.get("data", [])
    if not items or not items[0].get("download_url"):
        log(f"  ⚠ 未签发下载链接 (fid={fid[:8]})，Cookie 可能已失效")
        return False

    url = items[0]["download_url"]
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Referer": "https://pan.quark.cn/",
                "Range": "bytes=0-1048575",
                "Cookie": _cookie(),
            },
        )
        with opener.open(req, timeout=40) as resp:
            data = resp.read()
            if resp.status == 206 and len(data) == 1024 * 1024:
                log(f"  ✓ 下载链路正常，分片 HTTP {resp.status}，取满 1 MiB")
                return True
            log(f"  ⚠ 分片响应异常: HTTP {resp.status}，{len(data)} 字节")
            return False
    except Exception as e:
        code = getattr(e, "code", None)
        if code == 412:
            log("  ❌ CDN 返回 412 —— Cookie 已过期，请更新 quark_cookies_full.txt")
            return False
        log(f"  ⚠ 分片下载异常: {e}")
        return False


def streamer_running() -> bool:
    try:
        out = subprocess.run(
            ["pgrep", "-f", "quark_to_gdrive_streamer.py"],
            capture_output=True, text=True, timeout=10,
        )
        return out.returncode == 0 and out.stdout.strip() != ""
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="夸克 Cookie 健康巡检")
    ap.add_argument("--loop", action="store_true", help="常驻循环巡检")
    args = ap.parse_args()

    log("=" * 52)
    log("夸克 Cookie 巡检开始")
    healthy = check_once()
    if healthy:
        log("结论: Cookie 有效 ✓")
    else:
        state_txt = ""
        if STATE_FILE.exists():
            try:
                s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                state_txt = (f"（已转存 {len(s.get('transferred_fids', []))}，"
                             f"已删除 {len(s.get('deleted_fids', []))}）")
            except Exception:
                pass
        running = "运行中" if streamer_running() else "未运行"
        log(f"结论: Cookie 失效或链路异常 ✗ | 迁移进程: {running} {state_txt}")
        log("请在浏览器重新登录 drive.quark.cn，复制完整 Cookie 覆盖 "
            f"{COOKIE_FILE} 后重启迁移任务。")
    log("=" * 52)

    if not args.loop:
        return 0 if healthy else 1

    while True:
        time.sleep(CHECK_INTERVAL_HOURS * 3600)
        try:
            check_once()
        except Exception as e:  # 循环内异常不能终止守护
            log(f"  ⚠ 巡检异常: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
