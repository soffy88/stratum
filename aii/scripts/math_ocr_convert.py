"""PDF → 干净文本, 走 Unlimited-OCR(vLLM+FP8, docker容器 ocr-vllm:8011).

供 math_convert.py 对"需OCR"的书自主调用(烂文本层/无文字层). 输出契约与
math_convert.convert() 一致(逐页清洗文本, 章节行提升为 "# 标题"), 使下游
math_textbook() 分类与写文件逻辑无需改动.

实测(见 aii-ocr-vllm-pipeline 记忆): FP8量化破10G卡KV饿死, 并发~8路,
767页书约42分钟. 容器按需启停(不需要OCR时不占卡), 每本转换只在有需要时启动.

事故(2026-07-05): 本机只一块GPU, host原生ollama正在服务时本容器启动触发的NVML初始化
并发撞车, 直接 "Unknown Error" 崩溃(不是容器本身的问题, docker不对GPU设备做互斥). 现经
aegis 的跨进程GPU锁(/api/v1/gpu/lock)在 docker run/start + 健康检查等待这段窗口排队互斥,
与经 aegis Ollama 网关的调用真正串行, 而不是各自直接摸卡. aegis 不可达时 fail-open(仅打
警告日志继续), 不让 OCR 硬依赖 aegis 存活.
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
# ★2026-07-06实测: 8并发在真实书上(复杂图多的页)把KV cache(仅0.75GiB/13168token,
# 为给aii-embed留显存把gpu-memory-utilization压到0.75所致)挤爆, 连续两次CUDA OOM
# 崩溃(docker自动重启兜底没丢数据, 但丢了那本书这一轮的进度)。降到4留够单请求余量。
CONCURRENCY = 4
CACHE_ROOT = Path(__file__).resolve().parents[1] / "math_pipeline" / "ocr_cache"

GPU_LOCK_URL = "http://127.0.0.1:8010/api/v1/gpu/lock"


def _gpu_lock_acquire(
    *, owner: str, lease_sec: float, queue_timeout_sec: float = 120
) -> str | None:
    """经 aegis 跨进程GPU锁排队, 与host原生ollama互斥启动窗口(2026-07-05事故教训).
    aegis 不可达/繁忙 → fail-open, 只告警不阻断(容器启停这条老路自己还能兜底)."""
    try:
        r = requests.post(
            f"{GPU_LOCK_URL}/acquire",
            json={"owner": owner, "lease_sec": lease_sec, "queue_timeout_sec": queue_timeout_sec},
            timeout=queue_timeout_sec + 5,
        )
        if r.status_code == 200:
            return r.json()["token"]
        print(f"  ⚠ aegis GPU锁繁忙({r.status_code}), 不等了直接启动(有与ollama撞车风险)")
    except Exception as e:
        print(f"  ⚠ aegis GPU锁不可达({e}), 不等了直接启动(有与ollama撞车风险)")
    return None


def _gpu_lock_release(token: str | None) -> None:
    if not token:
        return
    try:
        requests.post(f"{GPU_LOCK_URL}/release", json={"token": token}, timeout=10)
    except Exception:
        pass


_DROP_DET = {"page_number", "header", "image"}
_CHAPTER_RE = re.compile(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+\s*章|CHAPTER\s+\d+)\b")


def _run(*args, timeout=30):
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)


AII_EMBED_HEALTH_URL = "http://127.0.0.1:8102/health"

# MinerU VLM(Track B, MINERU-AII-INTEGRATION-SPEC-001 §2.1 R3)——同一张卡装不下
# ocr-vllm(7.23G)和 MinerU VLM(官方文档约8G起)两个都热载。互斥不是免费获得的:
# 见 ensure_container()/ensure_mineru_container() 两边对称加的"起我之前先停对方"。
_MINERU_CONTAINER = "mineru-vlm"
MINERU_PORT = 8012


def _wait_for_embed_idle(max_wait_s: int = 600, poll_s: int = 15) -> None:
    """★2026-07-09 补记: aii-embed 已迁离本机(笔记本远程GPU, 见
    deploy/systemd/README.md), 不再和本机GPU抢显存——这个函数现在几乎总是立刻
    返回(查到 loaded=false 或干脆连不上), 保留是防御性的(万一哪天又有本机常驻
    服务占用), 不是当前真实瓶颈, 后面注释里"75%显存"那句的历史背景仅供参照。

    ★排队, 不是一撞就放弃: ocr-vllm 要75%显存(9.65G卡上约7.23G), aii-embed 的BGE-M3
    只要还占着卡(哪怕仅~2.4G)就可能让 ocr-vllm 启动因显存不足直接 Engine core
    initialization failed(退出码137, 2026-07-06 实测复现). aii-embed 空闲300s会自动卸载
    (AII_EMBED_IDLE_SEC), 等它卸载而不是让 ocr-vllm 直接摸黑撞上去。
    aii-embed 不可达/查询失败 → 不阻塞(fail-open, 由后续 ensure_container 自然决定成败)."""
    import time as _t

    waited = 0
    while waited < max_wait_s:
        try:
            loaded = requests.get(AII_EMBED_HEALTH_URL, timeout=5).json().get("loaded")
        except Exception:
            return  # aii-embed 不可达, 不因为查不到状态而卡住OCR
        if not loaded:
            return
        if waited == 0:
            print("  ⏳ aii-embed 正占着GPU(BGE-M3已加载), 排队等它空闲卸载…", flush=True)
        _t.sleep(poll_s)
        waited += poll_s
    print(f"  ⚠ 等aii-embed空闲超过{max_wait_s}s仍未卸载, 不再等, 直接尝试(可能显存不够会失败)")


def ensure_container(timeout_s: int = 180) -> bool:
    """确保 ocr-vllm 容器就绪(启动已存在的, 或全新创建). 返回是否就绪.

    启动到健康检查通过这段窗口(NVML初始化)经 aegis 跨进程GPU锁与host原生ollama互斥,
    避免2026-07-05那次"容器启动时并发撞车"事故重演。

    ★2026-07-09 加(Track B §2.1 R3): 启动前先停 mineru-vlm——9.65G卡装不下两个都要
    ~7-8G的VLM同时热载, 这是显式互斥, 不是靠运气不撞车。对称逻辑见
    ensure_mineru_container() 开头同样会先停这边。"""
    _run("docker", "stop", _MINERU_CONTAINER, timeout=30)
    _wait_for_embed_idle()
    lock_token = _gpu_lock_acquire(owner=CONTAINER, lease_sec=timeout_s + 30)
    try:
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
    finally:
        _gpu_lock_release(lock_token)


def release_container() -> None:
    """转换结束释放 GPU, 让共享嵌入服务等其它消费方能上卡."""
    _run("docker", "stop", CONTAINER, timeout=30)


# ---------------------------------------------------------------------------
# MinerU VLM(Track B, 并列通道)—— ensure/parse/release 三件套照抄 ocr-vllm
# 那一套的结构, 差异只在: ①启动前对称地先停 ocr-vllm(R3互斥) ②健康检查打
# /v1/models 同款端点但换端口 ③解析走 mineru CLI 的 vlm-http-client 后端, 不是
# 直接拼 chat/completions 请求(mineru 自己处理版面分析/图片切页/结构化落盘,
# 这部分工作量不该在这里重新发明)。
# ---------------------------------------------------------------------------


def ensure_mineru_container(timeout_s: int = 180) -> bool:
    """确保 mineru-vlm 容器就绪. 结构对称于 ensure_container(), 见其 R3 注释。

    ★2026-07-09 写这版时本机GPU硬件故障(Xid 79)未恢复, 这个函数在当前环境下
    大概率启动失败或卡在健康检查超时——这是预期行为不是bug, GPU 恢复后再真正
    验证。"""
    _run("docker", "stop", CONTAINER, timeout=30)
    lock_token = _gpu_lock_acquire(owner=_MINERU_CONTAINER, lease_sec=timeout_s + 30)
    try:
        status = _run(
            "docker", "inspect", "-f", "{{.State.Running}}", _MINERU_CONTAINER
        ).stdout.strip()
        if status != "true":
            exists = _run("docker", "inspect", _MINERU_CONTAINER).returncode == 0
            if exists:
                _run("docker", "start", _MINERU_CONTAINER)
            else:
                _run(
                    "docker",
                    "compose",
                    "-f",
                    str(Path(__file__).resolve().parents[1] / "docker-compose.aii-mineru-vlm.yml"),
                    "up",
                    "-d",
                    timeout=30,
                )
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                if (
                    requests.get(f"http://127.0.0.1:{MINERU_PORT}/v1/models", timeout=3).status_code
                    == 200
                ):
                    return True
            except Exception:
                pass
            if (
                _run(
                    "docker", "inspect", "-f", "{{.State.Running}}", _MINERU_CONTAINER
                ).stdout.strip()
                != "true"
            ):
                return False
            time.sleep(3)
        return False
    finally:
        _gpu_lock_release(lock_token)


def release_mineru_container() -> None:
    """转换结束释放 GPU, 对称于 release_container()."""
    _run("docker", "stop", _MINERU_CONTAINER, timeout=30)


def parse_with_mineru_vlm(pdf_path: str, *, out_dir: str | None = None) -> dict:
    """解析一次, fork-twice(spec §1): 调 mineru CLI 的 vlm-http-client 后端打
    已经在跑的 mineru-vlm 服务, 拿回 middle_json(结构化元素, 供 KU 提取用) +
    渲染好的 MD(人类可读产物, 供 Stratum 阅读器用) —— 两者同源于这一次解析,
    不是"渲染MD再回读解析结构"那种串行有损路径。

    real 字段名核实过(2026-07-09, 本机装 mineru 3.4.3 实测跑通一页真实PDF,
    非查文档假设): middle_json 顶层 {pdf_info, _backend, _version_name},
    每页在 pdf_info[i] 下, 结构化元素类型信息在 para_blocks/discarded_blocks
    里每个 block 的 "type" 字段(如 "title"/"text"/"table"/"interline_equation"),
    不是分开的顶层数组——这点和 spec 原文假设的 schema 形状不同, 以实测为准。

    Args:
        pdf_path: 待解析 PDF 路径.
        out_dir: mineru 输出目录, 默认临时目录(用完不清理, 供人工核对).

    Returns:
        {"middle_json": {...}, "content_list": [...], "md_path": "...", "backend": "vlm-http-client"}

    Raises:
        RuntimeError: mineru CLI 调用失败或找不到预期输出文件.
    """
    import json
    import tempfile

    pdf = Path(pdf_path)
    out = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="mineru_vlm_"))
    out.mkdir(parents=True, exist_ok=True)

    proc = _run(
        "mineru",
        "-p",
        str(pdf),
        "-o",
        str(out),
        "-b",
        "vlm-http-client",
        "-u",
        f"http://127.0.0.1:{MINERU_PORT}",
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"mineru CLI failed (exit {proc.returncode}): {proc.stderr[-2000:]}")

    stem = pdf.stem
    auto_dir = out / stem / "auto"
    middle_path = auto_dir / f"{stem}_middle.json"
    content_list_path = auto_dir / f"{stem}_content_list.json"
    md_path = auto_dir / f"{stem}.md"
    if not middle_path.exists():
        raise RuntimeError(f"mineru ran but expected output not found: {middle_path}")

    return {
        "middle_json": json.loads(middle_path.read_text(encoding="utf-8")),
        "content_list": json.loads(content_list_path.read_text(encoding="utf-8"))
        if content_list_path.exists()
        else [],
        "md_path": str(md_path) if md_path.exists() else None,
        "backend": "vlm-http-client",
    }


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
