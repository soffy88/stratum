#!/usr/bin/env python3
"""夸克网盘扫码登录 — 无头浏览器生成二维码 → 手机夸克 APP 扫码 → 会话落盘。

用法:
    cd aii && .venv/bin/python scripts/quark_login.py

流程:
  1. headless chromium 打开 pan.quark.cn(带重试, 该站网络偶发 ERR_NETWORK_CHANGED)
  2. 点"登录"→ 确保"扫码登录"tab → 截图二维码
  3. 起临时 HTTP 服务(0.0.0.0:8899, tailscale 可达) → 打印二维码图片地址
  4. 轮询 cookie 出现 __puus(登录凭证) → 保存 storage_state 到 quark_pipeline/
  5. 完成后自动退出; 不想要二维码服务可 Ctrl-C

登录后:
  - quark_pipeline/storage_state.json 供 quark_fetch.py 调 API 按需拉取
  - quark_pipeline/__puus.txt 明文凭证(备用)
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
PIPE.mkdir(exist_ok=True)

QR_PNG = PIPE / "qr.png"
STATE = PIPE / "storage_state.json"
PUUS_TXT = PIPE / "__puus.txt"
PORT = int(os.getenv("QUARK_QR_PORT", "8899"))
TAILSCALE_IP = os.getenv(
    "QUARK_QR_HOST", "100.86.95.70"
)  # 本机 tailscale IP, 用户手机同网可访问


def _start_qr_server() -> None:
    """把二维码图片暴露为 http://<tailscale-ip>:8899/ (带自动刷新的简单页)。"""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(PIPE), **kw)

        def log_message(self, *a):  # 静默
            pass

    os.chdir(PIPE)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.serve_forever()


def _wait_login(pg, ctx, timeout_s: int = 300) -> bool:
    """轮询 cookie 直到出现 __puus(夸克登录凭证)。"""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for c in ctx.cookies():
            if c["name"] == "__puus" and c["value"]:
                return True
        # 页面跳转到网盘列表页也算成功
        if "/#/" in pg.url and "login" not in pg.url.lower():
            for c in ctx.cookies():
                if c["name"] in ("__puus", "USID"):
                    return True
        pg.wait_for_timeout(2000)
    return False


def main() -> int:
    t = threading.Thread(target=_start_qr_server, daemon=True)
    t.start()
    print(f"二维码服务已起: http://{TAILSCALE_IP}:{PORT}/  (手机夸克 APP 扫一扫此页面的二维码)")

    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--no-proxy-server",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()

        ok = False
        for i in range(5):
            try:
                pg.goto("https://pan.quark.cn", timeout=45000, wait_until="domcontentloaded")
                ok = True
                break
            except Exception as e:
                print(f"  打开页面失败({i+1}/5): {str(e)[:70]}", flush=True)
                pg.wait_for_timeout(3000)
        if not ok:
            print("❌ 无法打开 pan.quark.cn, 检查网络")
            return 1

        pg.wait_for_timeout(4000)
        # 已有登录态则直接保存
        if _wait_login(pg, ctx, timeout_s=5):
            print("✅ 检测到已有登录态, 直接保存会话")
        else:
            # 点登录 → 切扫码 tab
            for sel in ["text=登录", "button:has-text('登录')", ".login-entry"]:
                el = pg.query_selector(sel)
                if el:
                    try:
                        el.click()
                        print(f"  已点击登录入口: {sel}")
                        break
                    except Exception:
                        pass
            pg.wait_for_timeout(2500)
            for sel in ["text=扫码登录", "text=二维码登录"]:
                el = pg.query_selector(sel)
                if el:
                    try:
                        el.click()
                        print(f"  已切换到: {sel}")
                        break
                    except Exception:
                        pass
            pg.wait_for_timeout(2000)
            pg.screenshot(path=str(QR_PNG))
            print(f"📱 二维码已生成: {QR_PNG}")
            print(f"📱 请用手机夸克 APP『扫一扫』访问: http://{TAILSCALE_IP}:{PORT}/  (5 分钟内有效)")
            print("   (若页面没显示二维码, 手机浏览器打开该地址会看到截图)")

            if not _wait_login(pg, ctx, timeout_s=300):
                print("❌ 等待登录超时(5 分钟), 重跑脚本再来一次")
                return 2

        ctx.storage_state(path=str(STATE))
        puus = next((c["value"] for c in ctx.cookies() if c["name"] == "__puus"), "")
        PUUS_TXT.write_text(puus)
        print(f"✅ 登录成功! 会话已保存:")
        print(f"   storage_state: {STATE}")
        print(f"   __puus: {puus[:12]}... (已存 {PUUS_TXT.name})")
        b.close()
    print("  现在可运行 scripts/quark_fetch.py 按需拉取(搜索/下载)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
