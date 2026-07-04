"""PDF → 干净文本, 走 Unlimited-OCR(vLLM+FP8, docker容器 ocr-vllm:8011).

供 math_convert.py 对"需OCR"的书自主调用(烂文本层/无文字层). 输出契约与
math_convert.convert() 一致(逐页清洗文本, 章节行提升为 "# 标题"), 使下游
math_textbook() 分类与写文件逻辑无需改动.

实测(见 aii-ocr-vllm-pipeline 记忆): FP8量化破10G卡KV饿死, 并发~8路,
767页书约42分钟. 容器按需启停(不需要OCR时不占卡), 每本转换只在有需要时启动.
"""

from __future__ import annotations

import base64
import hashlib
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import requests

CONTAINER = "ocr-vllm"
IMAGE = "vllm/vllm-openai:unlimited-ocr"
PORT = 8011
URL = f"http://127.0.0.1:{PORT}/v1/chat/completions"
CONCURRENCY = 8
CACHE_ROOT = Path(__file__).resolve().parents[1] / "math_pipeline" / "ocr_cache"

_DROP_DET = {"page_number", "header", "image"}
_CHAPTER_RE = re.compile(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+\s*章|CHAPTER\s+\d+)\b")


def _run(*args, timeout=30):
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)


def ensure_container(timeout_s: int = 180) -> bool:
    """确保 ocr-vllm 容器就绪(启动已存在的, 或全新创建). 返回是否就绪."""
    status = _run("docker", "inspect", "-f", "{{.State.Running}}", CONTAINER).stdout.strip()
    if status != "true":
        exists = _run("docker", "inspect", CONTAINER).returncode == 0
        if exists:
            _run("docker", "start", CONTAINER)
        else:
            _run(
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER,
                "--gpus",
                "all",
                "--network",
                "host",
                "--ipc",
                "host",
                "-v",
                "/home/soffy/.cache/huggingface:/root/.cache/huggingface",
                "-e",
                "HF_HUB_OFFLINE=1",
                "-e",
                "TRANSFORMERS_OFFLINE=1",
                IMAGE,
                "baidu/Unlimited-OCR",
                "--served-model-name",
                "Unlimited-OCR",
                "--trust-remote-code",
                "--logits_processors",
                "vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor",
                "--no-enable-prefix-caching",
                "--mm-processor-cache-gb",
                "0",
                "--quantization",
                "fp8",
                # ★留给共享嵌入服务(aii-embed)可能常驻的 ~2.5G headroom, 不抢满全卡
                "--gpu-memory-utilization",
                "0.75",
                "--max-model-len",
                "8192",
                "--max-num-seqs",
                "12",
                "--max-num-batched-tokens",
                "8192",
                "--enforce-eager",
                "--limit-mm-per-prompt",
                '{"image":1}',
                "--host",
                "0.0.0.0",
                "--port",
                str(PORT),
                timeout=30,
            )
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if requests.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=3).status_code == 200:
                return True
        except Exception:
            pass
        if (
            _run("docker", "inspect", "-f", "{{.State.Running}}", CONTAINER).stdout.strip()
            != "true"
        ):
            return False  # 容器启动后自己退出了(如显存不够) → 放弃
        time.sleep(3)
    return False


def release_container() -> None:
    """转换结束释放 GPU, 让共享嵌入服务等其它消费方能上卡."""
    _run("docker", "stop", CONTAINER, timeout=30)


def _strip_det(raw: str) -> str:
    out = []
    for part in re.split(r"<\|det\|>", raw):
        m = re.match(r"(\w+)\s*\[[\d,\s]*\]<\|/det\|>(.*)", part, re.DOTALL)
        if not m:
            continue
        typ, content = m.group(1), m.group(2).replace("<PAGE>", "").strip()
        if typ in _DROP_DET or not content:
            continue
        out.append(content)
    return "\n\n".join(out)


def _ocr_one_page(sess: requests.Session, png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode()
    body = {
        "model": "Unlimited-OCR",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "<image>document parsing."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": 7000,
        "temperature": 0.0,
        "skip_special_tokens": False,
        "vllm_xargs": {"ngram_size": 35, "window_size": 128},
    }
    for attempt in range(3):
        try:
            r = sess.post(URL, json=body, timeout=300)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)


def ocr_pdf_to_text(pdf_path: str, progress_cb=None) -> str:
    """PDF → 清洗文本(逐页 OCR, 与 math_convert.convert() 同契约: 章节行提升为 '# 标题').
    按 PDF 内容 hash 缓存每页原始输出(断点续跑, 与飞轮 substrate 命名无关的临时缓存)."""
    doc = fitz.open(pdf_path)
    n = doc.page_count
    cache_dir = CACHE_ROOT / hashlib.md5(pdf_path.encode("utf-8")).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)

    sess = requests.Session()
    sess.trust_env = False

    def work(i):
        fp = cache_dir / f"page_{i:04d}.txt"
        if fp.exists() and fp.stat().st_size > 0:
            return
        png = doc[i].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72)).tobytes("png")
        txt = _ocr_one_page(sess, png)
        fp.write_text(txt, encoding="utf-8")
        if progress_cb:
            progress_cb(i, n)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        list(ex.map(work, range(n)))
    doc.close()

    lines = []
    for i in range(n):
        fp = cache_dir / f"page_{i:04d}.txt"
        if not fp.exists():
            continue
        page_text = _strip_det(fp.read_text(encoding="utf-8"))
        for l in page_text.splitlines():
            s = l.strip()
            if not s or re.fullmatch(r"\d{1,4}", s):
                continue
            if _CHAPTER_RE.match(s):
                lines.append(f"\n# {s}\n")
            else:
                lines.append(s)
    return "\n".join(lines)


if __name__ == "__main__":
    import signal
    import sys

    def _on_signal(signum, frame):
        print(f"\n⚠ 收到信号 {signum}, 释放 OCR 容器后退出")
        release_container()
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    path = sys.argv[1]
    print("確保 OCR 容器就绪…")
    if not ensure_container():
        print("✗ 容器未就绪, 退出")
        sys.exit(1)
    try:
        t0 = time.time()
        text = ocr_pdf_to_text(
            path, progress_cb=lambda i, n: print(f"  {i + 1}/{n}", end="\r", flush=True)
        )
        print(f"\n✓ 完成 {time.time() - t0:.0f}s, {len(text)} 字")
    finally:
        release_container()
