#!/usr/bin/env python3
"""主链路 E2E: 注册 → 剪藏 → 入库 → 检索 → 导出 → 真删 → 收敛验证。

全 stdlib (urllib), 无第三方依赖。默认打本机 stratum 栈:

    AUTH_BASE=http://127.0.0.1:9309   (register/login → JWT)
    SL_BASE  =http://127.0.0.1:9304   (web-clip/search/export/inbox)

用法:
    python3 scripts/e2e_mvp_chain.py                          # 剪藏 github.com 页面
    python3 scripts/e2e_mvp_chain.py --url https://...        # 指定 URL
    python3 scripts/e2e_mvp_chain.py --email x@y.com --username xy --password ...

每一步打印 PASS / FAIL / WARN; 任一 FAIL 则 exit 1。
WARN 项 (如 /api/v1/retrieve 旧 pgvector 路径 0 命中) 不阻塞 MVP 判定。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AUTH_BASE = os.environ.get("AUTH_BASE", "http://127.0.0.1:9309")
SL_BASE = os.environ.get("SL_BASE", "http://127.0.0.1:9304")
POLL_ATTEMPTS = 15
POLL_INTERVAL = 4.0

_CJK_WORDS = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_WORDS = re.compile(r"[a-zA-Z]{3,}")
_STOPWORDS = {"the", "and", "for", "with", "https", "http", "www", "com"}


def _request(method: str, url: str, body: bytes | None = None,
             headers: dict[str, str] | None = None,
             timeout: float = 60.0) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return exc.code, {"detail": raw.decode(errors="replace")[:500]}


def _multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----e2e" + hex(int(time.time() * 1e6))[2:]
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
    parts.append(f"--{boundary}--\r\n")
    return "".join(parts).encode(), boundary


def _pick_query(title: str) -> str:
    for pat in (_CJK_WORDS, _ASCII_WORDS):
        toks = [t for t in pat.findall(title) if t.lower() not in _STOPWORDS]
        if toks:
            return max(toks, key=len)
    return ""


def _json_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default=None)
    ap.add_argument("--username", default=None)
    ap.add_argument("--password", default=None)
    ap.add_argument("--url", default="https://github.com/anomalyco/opencode")
    args = ap.parse_args()

    stamp = str(int(time.time()))[-6:]
    email = args.email or f"e2e_{stamp}@example.com"
    username = args.username or f"e2e_{stamp}"
    password = args.password or "E2eChainPass1!"

    results: list[tuple[str, str, str]] = []  # (step, status, detail)

    def step(name: str, status: str, detail: str = "") -> None:
        results.append((name, status, detail))
        print(f"[{status:4}] {name} — {detail}")

    # 1. 注册
    code, body = _request(
        "POST", f"{AUTH_BASE}/api/auth/register",
        json.dumps({"email": email, "username": username, "password": password}).encode(),
        {"Content-Type": "application/json"},
    )
    if code == 200 or (code in (400, 409) and "exists" in json.dumps(body)):
        step("注册", "PASS" if code == 200 else "WARN", f"{email} ({code})")
    else:
        step("注册", "FAIL", f"{code} {body}")
        return _finish(results)

    # 2. 登录
    code, body = _request(
        "POST", f"{AUTH_BASE}/api/auth/login",
        json.dumps({"email_or_username": email, "password": password}).encode(),
        {"Content-Type": "application/json"},
    )
    token = body.get("access_token", "")
    if code == 200 and token:
        step("登录", "PASS", "got JWT")
    else:
        step("登录", "FAIL", f"{code} {body}")
        return _finish(results)

    h = _json_headers(token)

    # 3. 剪藏
    payload, boundary = _multipart({"url": args.url, "fetch_mode": "full"})
    code, body = _request(
        "POST", f"{SL_BASE}/api/v1/inbox/web-clip", payload,
        {"Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=180.0,
    )
    sid = body.get("substrate_id") or ""
    title = body.get("title") or ""
    if code == 200 and sid:
        step("剪藏", "PASS", f"id={sid} title={title!r} words={body.get('word_count')}")
    else:
        step("剪藏", "FAIL", f"{code} {body}")
        return _finish(results)

    # 4. 入库确认 (收件箱出现)
    found = False
    for _ in range(POLL_ATTEMPTS):
        code, body = _request("GET", f"{SL_BASE}/api/v1/inbox?limit=50", headers=h)
        items = body.get("items", [])
        if any(i.get("id") == sid for i in items):
            found = True
            break
        time.sleep(POLL_INTERVAL)
    step("入库可见", "PASS" if found else "FAIL", f"polled {POLL_ATTEMPTS}x{POLL_INTERVAL}s")

    # 5. 语义检索命中
    query = _pick_query(title) or "document"
    hits = 0
    seen_in_search = False
    for _ in range(POLL_ATTEMPTS):
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/search",
            json.dumps({"query": query, "top_k": 20}).encode(), h,
        )
        results_list = body.get("results", [])
        hits = len(results_list)
        seen_in_search = any(
            r.get("substrate_id") == sid or r.get("id") == sid for r in results_list
        )
        if seen_in_search:
            break
        time.sleep(POLL_INTERVAL)
    step("检索命中", "PASS" if seen_in_search else "FAIL",
         f"query={query!r} hits={hits} (需包含刚入库文档)")

    # 6. 整库导出
    code, body = _request("GET", f"{SL_BASE}/api/v1/export/markdown", headers=h)
    items = body.get("items", [])
    exported = any(i.get("substrate_id") == sid for i in items)
    step("导出", "PASS" if exported else "FAIL", f"count={body.get('count')}")

    # 7. 旧 pgvector 检索路径 (WARN 级, 已知未接 BGE-M3)
    try:
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/retrieve",
            json.dumps({"query": query}).encode(), h,
        )
        rc = body.get("result_count", "?")
        step("retrieve(旧路径)", "WARN",
             f"result_count={rc} (Ollama/pgvector 旧栈, 不阻塞 MVP)")
    except Exception as exc:  # noqa: BLE001
        step("retrieve(旧路径)", "WARN", str(exc)[:120])

    # 8. 真删
    code, body = _request("DELETE", f"{SL_BASE}/api/v1/inbox/{sid}", headers=h)
    if code == 200 and body.get("status") == "deleted":
        step("真删", "PASS", f"mode={body.get('mode')}")
    else:
        step("真删", "FAIL", f"{code} {body}")
        return _finish(results)

    # 9. 收敛验证: 收件箱与检索都不再出现
    code, body = _request("GET", f"{SL_BASE}/api/v1/inbox?limit=50", headers=h)
    gone_from_inbox = not any(i.get("id") == sid for i in body.get("items", []))
    gone_from_search = True
    for _ in range(5):
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/search",
            json.dumps({"query": query, "top_k": 20}).encode(), h,
        )
        gone_from_search = not any(
            r.get("substrate_id") == sid or r.get("id") == sid for r in body.get("results", [])
        )
        if gone_from_search:
            break
        time.sleep(POLL_INTERVAL)
    if gone_from_inbox and gone_from_search:
        step("删除收敛", "PASS", "inbox/search 均不可见")
    else:
        step("删除收敛", "FAIL", f"inbox_gone={gone_from_inbox} search_gone={gone_from_search}")

    return _finish(results)


def _finish(results: list[tuple[str, str, str]]) -> int:
    fails = [r for r in results if r[1] == "FAIL"]
    print("\n" + "=" * 60)
    for name, status, _ in results:
        print(f"  {status:4}  {name}")
    print("=" * 60)
    if fails:
        print(f"E2E 结果: FAIL ({len(fails)} 项失败)")
        return 1
    print("E2E 结果: PASS (WARN 项不影响 MVP 判定)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
