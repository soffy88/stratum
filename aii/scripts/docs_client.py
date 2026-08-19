#!/usr/bin/env python3
"""stratum-docs 容器薄客户端 — 主机 convert 脚本调用转换微服务(127.0.0.1:8300)。

接口:
  pdf_to_md(path) -> str      # 调容器 /convert/pdf-to-md(同引擎零差异)
  analyze(path) -> dict       # 调容器 /convert/analyze
  pdf_to_docx(path, out)      # 调容器 /convert/pdf-to-docx
  queue_ocr(path) -> dict     # 调容器 /ocr/queue(转发 ocr-vllm)
"""
from __future__ import annotations

import json
import mimetypes
import os
import urllib.request
import uuid
from pathlib import Path

DOCS_URL = os.getenv("DOCS_URL", "http://127.0.0.1:8300")
TIMEOUT = int(os.getenv("DOCS_TIMEOUT", "900"))


def _multipart(path: str, extra: dict | None = None) -> tuple[bytes, str]:
    boundary = "----docs" + uuid.uuid4().hex
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    fname = Path(path).name
    body = []
    if extra:
        for k, v in extra.items():
            body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    body.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
        f"Content-Type: {mime}\r\n\r\n".encode())
    with open(path, "rb") as f:
        body.append(f.read())
    body.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(body), f"multipart/form-data; boundary={boundary}"


def _post(route: str, path: str, extra: dict | None = None) -> bytes:
    data, ctype = _multipart(path, extra)
    req = urllib.request.Request(
        f"{DOCS_URL}{route}", data=data, method="POST",
        headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def pdf_to_md(path: str, odl_hybrid: str = "0") -> str:
    """调容器转换, 返回清洗后 MD(与本地引擎一致)。失败抛异常(调用方 fallback)。"""
    resp = json.loads(_post("/convert/pdf-to-md", path, {"odl_hybrid": odl_hybrid}))
    return resp["md"]


def analyze(path: str) -> dict:
    return json.loads(_post("/convert/analyze", path))


def pdf_to_docx(path: str, out: str, dpi: int = 200) -> dict:
    data = _post("/convert/pdf-to-docx", path, {"dpi": str(dpi)})
    Path(out).write_bytes(data)
    return {"out": out, "bytes": len(data)}


def queue_ocr(path: str) -> dict:
    return json.loads(_post("/ocr/queue", path))
