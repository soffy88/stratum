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
# ★2026-08-27 提速: 容器慢/挂时立即 fallback(原 900s 等太久了, 串行 convert 卡死飞轮).
# 默认 10s: 正常 PDF 容器 <5s 处理完, 10s 给 2x 缓冲; 慢就立刻退本地 pdf_inspector/markitdown.
# (单本容器慢飞轮会整体卡死; 本地 pdf_inspector 1-3s/本, 比容器慢 1-3 倍但稳.)
TIMEOUT = int(os.getenv("DOCS_TIMEOUT", "10"))


def _multipart(path: str, extra: dict | None = None) -> tuple[bytes, str]:
    boundary = "----docs" + uuid.uuid4().hex
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    fname = Path(path).name
    body = []
    if extra:
        for k, v in extra.items():
            body.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            )
    body.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode()
    )
    with open(path, "rb") as f:
        body.append(f.read())
    body.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(body), f"multipart/form-data; boundary={boundary}"


def _post(route: str, path: str, extra: dict | None = None) -> bytes:
    data, ctype = _multipart(path, extra)
    req = urllib.request.Request(
        f"{DOCS_URL}{route}", data=data, method="POST", headers={"Content-Type": ctype}
    )
    # ★2026-08-27 加速: 容器 healthy 但排队时整 POST 60s 后才超时, 一轮几百本 = 几小时.
    # 用 socket.setdefaulttimeout 短超时 + urlopen(timeout=) 兜底. 容器无响应/慢就立刻
    # 抛 socket.timeout, 调用方 fallback 走本地 pdf_inspector/markitdown.
    import socket as _socket

    _socket.setdefaulttimeout(TIMEOUT)
    try:
        with urllib.request.urlopen(req) as r:
            return r.read()
    finally:
        _socket.setdefaulttimeout(None)


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
