#!/usr/bin/env python3
"""夸克网盘微信扫码登录 — 无头浏览器 + 微信授权码 → ASCII 二维码 → 手机微信扫。

流程:
  1. headless chromium 打开 pan.quark.cn/#/login → 点「微信登录」
  2. 捕获 open.weixin.qq.com/connect/qrcode/<uuid> 二维码图片 URL
  3. 下载 → PIL 二值化 → ASCII 二维码写入 quark_pipeline/wx_qr.txt
     (你用自己的终端 cat 该文件, 手机微信扫一扫即可; 二维码 5 分钟有效)
  4. 轮询 __puus cookie → 登录成功 → 保存 storage_state.json

用法:
    cd aii && .venv/bin/python scripts/quark_login_wx.py
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
PIPE.mkdir(exist_ok=True)
QR_TXT = PIPE / "wx_qr.txt"
STATE = PIPE / "storage_state.json"
PUUS_TXT = PIPE / "__puus.txt"

BLOCK = "\u2588"  # █


def qr_to_ascii(img_bytes: bytes, modules: int = 29) -> str:
    """二维码 PNG → 精确模块矩阵 → 纯 ASCII(##/空格, 每模块 2 列字符补偿终端宽高比)。

    步骤: 灰度 → 黑像素 bbox 裁剪(去掉 quiet zone) → 按 modules×modules 网格
    采样每模块中心像素 → 渲染 58 列 x 29 行, 四周留白模拟 quiet zone。
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    bbox = img.point(lambda v: 0 if v < 128 else 255).getbbox()
    if not bbox:
        raise ValueError("二维码图片无黑色像素")
    x0, y0, x1, y1 = bbox
    # 采样每模块中心(bbox 略含误差, 用中心点抗边缘)
    sw, sh = (x1 - x0) / modules, (y1 - y0) / modules
    mat = []
    for r in range(modules):
        row = []
        for c in range(modules):
            px = img.getpixel((int(x0 + (c + 0.5) * sw), int(y0 + (r + 0.5) * sh)))
            row.append(px < 128)
        mat.append(row)
    # 渲染: 每模块 2 字符宽; 上下各留 2 行空白
    lines = [""] * 2
    for row in mat:
        lines.append("".join("##" if v else "  " for v in row))
    lines += [""] * 2
    return "\n".join(lines)


def main() -> int:
    qr_url: list[str] = []

    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--no-proxy-server", "--disable-blink-features=AutomationControlled"],
        )
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()

        def on_resp(resp):
            u = resp.url
            if "/connect/qrcode/" in u and resp.ok:
                qr_url.append(u)
            if "open.weixin.qq.com/connect/qrconnect" in u:
                qrconnect_url.append(u)

        qrconnect_url: list[str] = []
        pg.on("response", on_resp)

        ok = False
        for i in range(5):
            try:
                pg.goto("https://pan.quark.cn/#/login", timeout=45000, wait_until="domcontentloaded")
                ok = True
                break
            except Exception as e:
                print(f"  打开页面失败({i+1}/5): {str(e)[:60]}", flush=True)
                pg.wait_for_timeout(3000)
        if not ok:
            print("❌ 无法打开登录页")
            return 1

        # 等登录弹窗(偶发不自动出现) → 没有则点页面「登录」按钮强制打开
        for _ in range(15):
            if pg.query_selector("text=微信登录"):
                break
            pg.wait_for_timeout(2000)
        el = pg.query_selector("text=微信登录")
        if not el:
            print("  弹窗未自动出现, 点页面「登录」按钮...", flush=True)
            btn = pg.query_selector("text=登录")
            if btn:
                try:
                    btn.click()
                except Exception:
                    pass
            for _ in range(10):
                if pg.query_selector("text=微信登录"):
                    break
                pg.wait_for_timeout(2000)
            el = pg.query_selector("text=微信登录")
        if not el:
            print("❌ 登录弹窗未出现(页面可能加载异常)")
            pg.screenshot(path=str(PIPE / "wx_debug.png"))
            return 2
        el.click()
        print("✅ 已点击微信登录", flush=True)

        # 等微信二维码 URL(网络间歇抖动, 整体重试)
        u = None
        for attempt in range(3):
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and not qr_url:
                pg.wait_for_timeout(1000)
            if qr_url:
                u = qr_url[-1]
                break
            print(f"  二维码未出现(尝试 {attempt+1}/3), 刷新重试...", flush=True)
            try:
                pg.reload(wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
            pg.wait_for_timeout(3000)
            el = pg.query_selector("text=微信登录")
            if el:
                try:
                    el.click()
                except Exception:
                    pass
        if u is None:
            print("❌ 未捕获到微信二维码 URL")
            pg.screenshot(path=str(PIPE / "wx_debug.png"))
            return 3
        print(f"✅ 微信授权码已捕获: ...{u[-24:]}", flush=True)

        # 微信官方 qrconnect 页面 URL(用户可自行在浏览器打开 → 页面显示标准二维码)
        if qrconnect_url:
            (PIPE / "wx_qrconnect_url.txt").write_text(qrconnect_url[-1])
            print(f"🔗 备用链接(浏览器打开即显示微信官方二维码):", flush=True)
            print(f"   {qrconnect_url[-1][:200]}", flush=True)

        # 下载二维码 PNG(原始图, jsQR 验证过可解码) → 存文件供 scp 下载直扫
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            png_bytes = resp.read()
        PNG_FILE = PIPE / "wx_qr.png"
        PNG_FILE.write_bytes(png_bytes)
        print(f"📱 二维码图片已保存: {PNG_FILE} ({len(png_bytes)//1024}KB)", flush=True)
        print(f"   下载方式(本机终端): scp soffy@<host>:{PNG_FILE} .  → 微信扫一扫(相册选图)", flush=True)

        # 顺带生成 ASCII 版(尽力而为, 矩阵提取依赖图片布局; 失败不影响 PNG 方案)
        try:
            ascii_qr = qr_to_ascii(png_bytes)
            QR_TXT.write_text(ascii_qr)
            print(f"📱 ASCII 版(备用): cat {QR_TXT}", flush=True)
        except Exception as e:
            print(f"  (ASCII 生成跳过: {e})", flush=True)

        # 轮询登录成功
        deadline = time.monotonic() + 300
        logged = False
        while time.monotonic() < deadline:
            for c in ctx.cookies():
                if c["name"] == "__puus" and c["value"]:
                    logged = True
                    break
            if logged:
                break
            pg.wait_for_timeout(2000)
        if not logged:
            print("❌ 5 分钟内未扫码/登录未完成, 重跑脚本再来")
            return 4

        ctx.storage_state(path=str(STATE))
        puus = next((c["value"] for c in ctx.cookies() if c["name"] == "__puus"), "")
        PUUS_TXT.write_text(puus)
        print("✅✅ 登录成功! 会话已保存:")
        print(f"   storage_state: {STATE}")
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
