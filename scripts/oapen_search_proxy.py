#!/usr/bin/env python3
"""OAPEN 搜索代理 — host 常驻小服务(:8766), 补上 oapen_direct_search 缺失的上游。

背景: stratum-sl 容器里的 `oapen_direct_search.py` 写死调
`http://172.19.0.1:8766/oapen-search`, 但这个代理服务从未被建出来("oapen 网络待修"),
导致 oapen 书源一直是死的。OAPEN(library.oapen.org)是开放获取学术专著库, 是
飞轮"拉现代教材/专著"最对口的源。

必须走 host 侧代理的原因: 容器内 urllib 只给了 30s 超时且不带重试, OAPEN 在
GFW 环境直连不稳; host 上统一走 sing-box 出网代理(HTTP(S)_PROXY env, 由 systemd
unit 注入), 容器只打本机端口。

契约(消费方 oapen_direct_search.py 期望):
  GET /oapen-search?query=<q>&max_results=<n>[&language=<lang>]
  → {"results": [{"external_id", "title", "download_url", "metadata": {...}}]}
  GET /health → {"ok": true}

上游: DSpace REST `https://library.oapen.org/rest/search?query=..&limit=..&expand=bitstreams,metadata`
  download_url 取 bundleName=ORIGINAL 且 mimeType=application/pdf 的 retrieveLink。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8766
OAPEN_BASE = "https://library.oapen.org"
UPSTREAM_TIMEOUT = 25  # 消费方 urlopen timeout=30, 上游必须先于它超时

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("oapen-proxy")


def _search(query: str, max_results: int, language: str | None) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            # 统一 3 倍超采: 不少条目没有 ORIGINAL pdf(章节级/仅ONIX), language 过滤也在
            # 本地做(DSpace query 不支持字段过滤)——不超采的话前 N 条恰好无 PDF 就交白卷
            "query": query,
            "limit": str(min(max_results * 3, 60)),
            "expand": "bitstreams,metadata",
        }
    )
    url = f"{OAPEN_BASE}/rest/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "stratum-oapen-proxy/1.0"})
    items = json.loads(urllib.request.urlopen(req, timeout=UPSTREAM_TIMEOUT).read())

    results: list[dict] = []
    for it in items:
        pdf_link = next(
            (
                b.get("retrieveLink")
                for b in (it.get("bitstreams") or [])
                if b.get("bundleName") == "ORIGINAL" and b.get("mimeType") == "application/pdf"
            ),
            None,
        )
        if not pdf_link:
            continue
        meta = {m["key"]: m["value"] for m in (it.get("metadata") or []) if m.get("key")}
        if language and language.lower() not in (meta.get("dc.language") or "").lower():
            continue
        results.append(
            {
                "external_id": f"oapen:{it.get('handle') or it.get('uuid')}",
                "title": it.get("name") or meta.get("dc.title") or "untitled",
                "download_url": f"{OAPEN_BASE}{pdf_link}",
                "metadata": {
                    "source_type": "oapen",
                    "oapen_handle": it.get("handle"),
                    "language": meta.get("dc.language"),
                    "year": meta.get("dc.date.issued"),
                    "publisher": meta.get("publisher.name") or meta.get("dc.publisher"),
                },
            }
        )
        if len(results) >= max_results:
            break
    return results


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"ok": True})
            return
        if parsed.path != "/oapen-search":
            self._json(404, {"error": "not found"})
            return
        q = urllib.parse.parse_qs(parsed.query)
        query = (q.get("query") or [""])[0].strip()
        if not query:
            self._json(400, {"error": "query required"})
            return
        try:
            max_results = min(int((q.get("max_results") or ["10"])[0]), 50)
        except ValueError:
            max_results = 10
        language = (q.get("language") or [None])[0]
        try:
            results = _search(query, max_results, language)
            log.info("query=%r lang=%r → %d results", query, language, len(results))
            self._json(200, {"results": results})
        except Exception as exc:
            log.warning("query=%r failed: %s", query, exc)
            self._json(502, {"error": str(exc), "results": []})

    def log_message(self, *args) -> None:  # 静默默认 access log, 上面自己记
        pass


if __name__ == "__main__":
    log.info("listening on 0.0.0.0:%d, upstream %s", PORT, OAPEN_BASE)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
