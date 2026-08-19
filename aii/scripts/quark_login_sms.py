#!/usr/bin/env python3
"""夸克网盘手机号+短信验证码登录 — 无需夸克 APP / 无需 Cookie 手动提供。

用法:
    cd aii && .venv/bin/python scripts/quark_login_sms.py

交互(通过文件, 便于远程配合):
    quark_pipeline/phone.txt       ← 你的夸克网盘绑定手机号(我帮你写入)
    quark_pipeline/sms_code.txt    ← 短信验证码(你收到后告诉我, 我写入; 脚本轮询读取)
    quark_pipeline/storage_state.json ← 登录成功后的会话(供 quark_fetch.py 使用)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
PIPE.mkdir(exist_ok=True)
PHONE_FILE = PIPE / "phone.txt"
CODE_FILE = PIPE / "sms_code.txt"
STATE = PIPE / "storage_state.json"
PUUS_TXT = PIPE / "__puus.txt"


def wait_file(path: Path, timeout_s: int, what: str) -> str:
    print(f"⏳ 等待 {what} (写入 {path.name})...", flush=True)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists():
            v = path.read_text().strip()
            if v:
                return v
        time.sleep(1.5)
    raise TimeoutError(f"等待 {what} 超时")


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--no-proxy-server", "--disable-blink-features=AutomationControlled"],
        )
        ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()

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
        pg.wait_for_timeout(3000)

        # 切到手机登录 tab
        for sel in ["text=手机登录", "text=手机号登录"]:
            el = pg.query_selector(sel)
            if el:
                try:
                    el.click()
                    print(f"✅ 已切换: {sel}", flush=True)
                    break
                except Exception as e:
                    print(f"  点击 {sel} 失败: {e}", flush=True)
        pg.wait_for_timeout(2000)

        # 登录表单在 uop.quark.cn 统一认证 iframe 内(该站网络间歇抖动, 多重试)
        fr = None
        for attempt in range(6):
            for _ in range(10):
                iframe_el = pg.query_selector("iframe.mobile-container")
                if iframe_el:
                    fr = iframe_el.content_frame()
                    if fr and fr.query_selector("input[name=login_name]"):
                        break
                pg.wait_for_timeout(1000)
            if fr and fr.query_selector("input[name=login_name]"):
                break
            print(f"  iframe 未就绪(尝试 {attempt+1}/6), 刷新页面重试...", flush=True)
            try:
                pg.reload(wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
            pg.wait_for_timeout(3000)
            el = pg.query_selector("text=手机登录")
            if el:
                try:
                    el.click()
                except Exception:
                    pass
            pg.wait_for_timeout(3000)
        if fr is None or not fr.query_selector("input[name=login_name]"):
            print("❌ 找不到登录 iframe(uop.quark.cn), 页面结构可能变化")
            pg.screenshot(path=str(PIPE / "login_debug.png"))
            return 2
        print("✅ 已进入统一认证 iframe", flush=True)

        # 1. 手机号
        phone = wait_file(PHONE_FILE, 600, "手机号")
        phone_input = fr.query_selector("input[name=login_name]")
        if not phone_input:
            print("❌ 找不到手机号输入框")
            return 2
        phone_input.fill(phone)
        print(f"✅ 已填手机号: {phone[:3]}****{phone[-4:]}", flush=True)

        # 2. 获取验证码
        got = False
        for sel in ["text=获取短信验证码", "input[type=button]", "button:has-text('验证码')"]:
            el = fr.query_selector(sel)
            if el:
                try:
                    el.click()
                    got = True
                    print("✅ 已点击获取短信验证码, 短信即将发送", flush=True)
                    break
                except Exception as e:
                    print(f"  点验证码按钮失败: {e}", flush=True)
        if not got:
            pg.screenshot(path=str(PIPE / "login_debug2.png"))
            print("⚠ 没找到获取验证码按钮, 继续等待输入框")

        # 3. 等待验证码(用户告诉我 → 我写入 sms_code.txt)
        code = wait_file(CODE_FILE, 300, "短信验证码")
        code_box = fr.query_selector("input[name=sms_code]")
        if not code_box:
            print("❌ 找不到验证码输入框")
            return 3
        code_box.fill(code)
        print("✅ 验证码已填入", flush=True)

        # 4. 提交并等待登录(优先点登录按钮, 兜底 Enter)
        submitted = False
        for sel in ["button:has-text('登录')", "input[type=submit]", "text=登录"]:
            el = fr.query_selector(sel)
            if el:
                try:
                    el.click()
                    submitted = True
                    print("✅ 已提交登录", flush=True)
                    break
                except Exception:
                    pass
        if not submitted:
            code_box.press("Enter")
            print("✅ 已回车提交登录", flush=True)
        deadline = time.monotonic() + 60
        logged = False
        while time.monotonic() < deadline:
            for c in ctx.cookies():
                if c["name"] == "__puus" and c["value"]:
                    logged = True
                    break
            if logged:
                break
            pg.wait_for_timeout(1500)
        if not logged:
            print("❌ 登录未确认(验证码错误/过期?), 可重跑脚本再试")
            return 4

        ctx.storage_state(path=str(STATE))
        puus = next((c["value"] for c in ctx.cookies() if c["name"] == "__puus"), "")
        PUUS_TXT.write_text(puus)
        print("✅✅ 登录成功! 会话已保存:")
        print(f"   storage_state: {STATE}")
        print(f"   __puus: {puus[:12]}...")
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
