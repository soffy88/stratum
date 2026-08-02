#!/usr/bin/env python3
"""主链路人工 E2E 自动化版:

    注册 → 剪藏 → 入库 → 翻译 → 问答出处 → 概念追加 → 整库导出
    → vault 同步 → Lint → 日报 → 真删 → 收敛验证

全 stdlib (urllib), 无第三方依赖。默认打本机 stratum 栈:

    AUTH_BASE=http://127.0.0.1:9309   (register/login → JWT)
    SL_BASE  =http://127.0.0.1:9304   (web-clip/search/export/inbox/agents)

用法:
    python3 scripts/e2e_mvp_chain.py                          # 剪藏 github.com 页面
    python3 scripts/e2e_mvp_chain.py --url https://...        # 指定 URL
    python3 scripts/e2e_mvp_chain.py --skip-web --pdf f.pdf    # 走 PDF 上传链
    python3 scripts/e2e_mvp_chain.py --email x@y.com --password ...

每一步打印 PASS / FAIL / WARN; 任一 FAIL 则 exit 1。
WARN 项 (如 /api/v1/retrieve 旧 pgvector 路径 0 命中) 不阻塞 MVP 判定。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

AUTH_BASE = os.environ.get("AUTH_BASE", "http://127.0.0.1:9309")
SL_BASE = os.environ.get("SL_BASE", "http://127.0.0.1:9304")
POLL_ATTEMPTS = 15
POLL_INTERVAL = 4.0

_CJK_WORDS = re.compile(r"[\u4e00-\u9fff]{2,}")
_ASCII_WORDS = re.compile(r"[a-zA-Z]{3,}")
_STOPWORDS = {"the", "and", "for", "with", "https", "http", "www", "com"}


def _request(method: str, url: str, body: bytes | None = None,
             headers: dict[str, str] | None = None,
             timeout: float = 120.0) -> tuple[int, dict]:
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


def _request_raw(method: str, url: str, headers: dict[str, str] | None = None,
                 timeout: float = 120.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes]] | None = None,
               ) -> tuple[bytes, str]:
    boundary = "----e2e" + hex(int(time.time() * 1e6))[2:]
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
    for k, (fname, data) in (files or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; "
            f"filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
        )
        parts.append(data.decode(errors="replace"))
        parts.append("\r\n")
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
    ap.add_argument("--skip-web", action="store_true", help="走 PDF 上传链而非 web-clip")
    ap.add_argument("--pdf", default=None, help="PDF 文件路径 (默认生成一个含英文内容的测试 PDF)")
    args = ap.parse_args()

    stamp = str(int(time.time()))[-6:]
    email = args.email or f"e2e_{stamp}@example.com"
    username = args.username or f"e2e_{stamp}"
    password = args.password or "E2eChainPass1!"

    results: list[tuple[str, str, str]] = []

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

    # 3. 入库: web-clip 或 PDF 上传
    sid, title = "", ""
    if args.skip_web:
        pdf_path = args.pdf
        if not pdf_path:
            pdf_path = f"/tmp/e2e_{stamp}.pdf"
            _make_test_pdf(pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        payload, boundary = _multipart(
            {"medium_hint": "paper", "title_override": f"E2E Paper {stamp}"},
            {"file": (os.path.basename(pdf_path), pdf_data)},
        )
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/inbox/submit", payload,
            {"Authorization": f"Bearer {token}",
             "Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=300.0,
        )
        sid = body.get("substrate_id") or ""
        title = body.get("title") or body.get("upload_id") or ""
        if code == 200 and sid:
            step("PDF 上传", "PASS", f"id={sid} status={body.get('status')}")
        else:
            step("PDF 上传", "FAIL", f"{code} {body}")
            return _finish(results)
    else:
        payload, boundary = _multipart({"url": args.url, "fetch_mode": "full"})
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/inbox/web-clip", payload,
            {"Authorization": f"Bearer {token}",
             "Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=300.0,
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
        if any(i.get("id") == sid for i in body.get("items", [])):
            found = True
            break
        time.sleep(POLL_INTERVAL)
    step("入库可见", "PASS" if found else "FAIL", f"polled {POLL_ATTEMPTS}x{POLL_INTERVAL}s")

    # 5. 翻译 (substrate → zh)
    t_code, t_body = _request(
        "POST", f"{SL_BASE}/api/v1/translate/substrate/{sid}?target_lang=zh", b"", h,
        timeout=300.0,
    )
    t_status = t_body.get("status", "")
    if t_code == 200 and t_status in ("completed", "skipped"):
        step("翻译", "PASS", f"status={t_status}")
    elif t_code == 200 and t_status == "not_implemented":
        step("翻译", "WARN", "translation_worker not_implemented (平台包缺失)")
    else:
        step("翻译", "FAIL", f"{t_code} {t_body}")

    # 6. 问答出处 (reading_companion → sources[])
    qa = {}
    for _ in range(3):
        q_code, q_body = _request(
            "POST", f"{SL_BASE}/api/v1/agents/reading_companion/run",
            json.dumps({"substrate_id": sid, "question": "这篇文章主要讲了什么?"}).encode(), h,
            timeout=300.0,
        )
        qa = q_body
        if q_code == 200 and q_body.get("status") in ("completed", "ok"):
            break
        time.sleep(POLL_INTERVAL)
    sources = qa.get("sources", []) or []
    findings = qa.get("findings") or {}
    if isinstance(findings, dict):
        answer = findings.get("answer") or ""
        if not sources:
            sources = findings.get("sources") or []
    else:
        answer = str(findings)
    llm_failed = "LLM call failed" in str(answer)
    if q_code == 200 and sources and not llm_failed:
        step("问答出处", "PASS", f"sources={len(sources)} answer_len={len(str(answer))}")
    elif q_code == 200 and llm_failed:
        step("问答出处", "WARN", f"LLM 调用失败(凭证/本地LLM): {str(answer)[:80]}")
    elif q_code == 200 and not sources:
        step("问答出处", "WARN", f"answer_len={len(str(answer))} sources=0")
    else:
        step("问答出处", "FAIL", f"{q_code} {str(qa)[:200]}")

    # 7. 概念追加 (create concept + substrate_refs + verify)
    c_code, c_body = _request(
        "POST", f"{SL_BASE}/api/v1/concepts",
        json.dumps({"name": f"E2E概念{stamp}", "type": "concept_idea"}).encode(), h,
    )
    cid = c_body.get("concept_id", "")
    if c_code == 200 and cid:
        u_code, u_body = _request(
            "PUT", f"{SL_BASE}/api/v1/concepts/{cid}",
            json.dumps({"substrate_refs": [sid]}).encode(), h,
        )
        g_code, g_body = _request("GET", f"{SL_BASE}/api/v1/concepts/{cid}", headers=h)
        refs = (g_body.get("related_substrates") or []) if isinstance(g_body, dict) else []
        refs = [r.get("id") if isinstance(r, dict) else r for r in refs]
        if u_code == 200 and sid in refs:
            step("概念追加", "PASS", f"concept={cid} refs={len(refs)}")
        else:
            step("概念追加", "FAIL", f"refs={refs}")
    else:
        step("概念追加", "FAIL", f"{c_code} {c_body}")

    # 8. 语义检索命中
    query = _pick_query(title) or "document"
    hits, seen_in_search = 0, False
    for _ in range(POLL_ATTEMPTS):
        code, body = _request(
            "POST", f"{SL_BASE}/api/v1/search",
            json.dumps({"query": query, "top_k": 20}).encode(), h,
        )
        hits = len(body.get("results", []))
        seen_in_search = any(
            r.get("substrate_id") == sid or r.get("id") == sid for r in body.get("results", [])
        )
        if seen_in_search:
            break
        time.sleep(POLL_INTERVAL)
    step("检索命中", "PASS" if seen_in_search else "FAIL",
         f"query={query!r} hits={hits}")

    # 9. 整库导出 (markdown + vault zip)
    code, body = _request("GET", f"{SL_BASE}/api/v1/export/markdown", headers=h)
    exported = any(i.get("substrate_id") == sid for i in body.get("items", []))
    step("导出", "PASS" if exported else "FAIL", f"markdown count={body.get('count')}")

    z_code, z_data = _request_raw("GET", f"{SL_BASE}/api/v1/export/vault", headers=h)
    try:
        with zipfile.ZipFile(io.BytesIO(z_data)) as zf:
            names = zf.namelist()
        step("导出vault", "PASS" if z_code == 200 and names else "FAIL",
             f"zip={len(z_data)}B files={len(names)}")
    except zipfile.BadZipFile:
        step("导出vault", "FAIL", f"bad zip: {z_data[:120]!r}")

    # 10. vault 同步 (export 到 roots 下)
    r_code, r_body = _request("GET", f"{SL_BASE}/api/v1/sync/vault/roots", headers=h)
    roots = [r for r in r_body.get("roots", []) if r]
    v_code, v_body = _request(
        "POST", f"{SL_BASE}/api/v1/sync/vault",
        json.dumps({"path": f"{roots[0]}/e2e-vault-{stamp}", "mode": "export"}).encode(), h,
    )
    v_status = v_body.get("status", "")
    if roots and v_code == 200 and v_status not in ("error",):
        step("vault同步", "PASS", f"root={roots[0]} status={v_status}")
    elif not roots:
        step("vault同步", "FAIL", "no roots configured")
    else:
        step("vault同步", "FAIL", f"{v_code} {v_body}")

    # 11. Lint (写报告笔记)
    l_code, l_body = _request(
        "POST", f"{SL_BASE}/api/v1/agents/knowledge_lint/run",
        json.dumps({"write_report": True}).encode(), h, timeout=300.0,
    )
    l_status = l_body.get("status", "")
    step("Lint", "PASS" if l_code == 200 and l_status == "ok" else "FAIL",
         f"status={l_status}")

    # 12. 日报
    d_code, d_body = _request(
        "POST", f"{SL_BASE}/api/v1/agents/daily_digest_simple/run",
        json.dumps({"days": 1, "notify": False}).encode(), h, timeout=300.0,
    )
    d_status = d_body.get("status", "")
    step("日报", "PASS" if d_code == 200 and d_status == "ok" else "FAIL",
         f"status={d_status} note_id={d_body.get('note_id')}")

    # 13. 分层检索 (后台生成 L0/L1/L2 是异步任务, 轮询等它就位)
    import time as _time

    retr_count = 0
    for _attempt in range(12):
        try:
            code, body = _request(
                "POST", f"{SL_BASE}/api/v1/retrieve",
                json.dumps({"query": query, "max_depth": 2, "top_k": 5}).encode(), h,
            )
            retr_count = body.get("result_count", 0) or 0
            if code == 200 and retr_count > 0:
                break
        except Exception:  # noqa: BLE001
            pass
        _time.sleep(5)
    step(
        "retrieve分层检索", "PASS" if retr_count > 0 else "WARN",
        f"result_count={retr_count}",
    )

    # 14. 真删 (substrate + concept)
    code, body = _request("DELETE", f"{SL_BASE}/api/v1/inbox/{sid}", headers=h)
    if code == 200 and body.get("status") == "deleted":
        step("真删", "PASS", f"mode={body.get('mode')}")
    else:
        step("真删", "FAIL", f"{code} {body}")
        return _finish(results)
    if cid:
        _request("DELETE", f"{SL_BASE}/api/v1/concepts/{cid}", headers=h)

    # 15. 收敛验证: 收件箱与检索都不再出现
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
    step("删除收敛", "PASS" if gone_from_inbox and gone_from_search else "FAIL",
         f"inbox_gone={gone_from_inbox} search_gone={gone_from_search}")

    return _finish(results)


def _make_test_pdf(path: str) -> None:
    """生成一个最小英文 PDF (含 'attention mechanism' 段落), 无第三方依赖。"""
    import zlib

    lines = [
        "E2E Attention Mechanism Paper",
        "",
        "Abstract. The attention mechanism is a core component of modern",
        "transformer architectures. It allows the model to weight the",
        "importance of different input tokens when producing an output.",
        "This paper summarizes key properties of scaled dot-product attention.",
        "The knowledge distillation process transfers soft labels from a",
        "large teacher model to a compact student model.",
    ]
    content = "\n".join(lines)
    # object 1: catalog; object 2: pages; object 3: page; object 4: contents
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"placeholder",  # 4: contents stream, rebuilt below
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    # (simplified: recompute length)
    stream = f"BT /F1 11 Tf 40 750 Td 18 TL\n".encode()
    for ln in lines:
        stream += f"({ln}) Tj\nT*\n".encode()
    stream += b"ET"
    objs[3] = b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream"

    out = b"%PDF-1.4\n"
    offsets = [0]
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out) + len(f"{i} 0 obj\n".encode()))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1, xref_pos,
    )
    with open(path, "wb") as f:
        f.write(out)


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
