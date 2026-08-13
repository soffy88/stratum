"""stratum-docs 微服务 — PDF/EPUB 转换统一入口(FastAPI)。

POST /convert/pdf-to-md      multipart(file) + form(odl_hybrid) → {md, analyze}
POST /convert/epub-to-md     multipart(file) → {md, analyze}
POST /convert/pdf-to-docx    multipart(file) + form(dpi) → docx 文件下载
POST /convert/analyze        multipart(file) → analyze 信号
GET  /health

★2026-08-13: 所有 CPU 密集转换一律 asyncio.to_thread + 信号量限流,
  避免长任务阻塞事件循环导致 /health 超时(docker healthcheck 之前因此持续 unhealthy)。
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse

from .converter import analyze, convert_office_to_md, convert_to_docx, convert_to_md

app = FastAPI(title="stratum-docs", version="0.1.0")

# 并发转换上限: 2 路并行, 其余排队; /health 永远不被长任务饿死。
_CONVERT_SEM = asyncio.Semaphore(2)


async def _run_blocking(fn, *args):
    """带信号量限流的线程池执行 — 不阻塞事件循环。"""
    async with _CONVERT_SEM:
        return await asyncio.to_thread(fn, *args)


def _save_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename).suffix.lower() or ".pdf"
    fd = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    fd.write(upload.file.read())
    fd.close()
    return fd.name


@app.get("/health")
def health():
    return {"ok": True, "service": "stratum-docs"}


@app.post("/convert/pdf-to-md")
async def pdf_to_md(file: UploadFile = File(...), odl_hybrid: str = Form("0")):
    import os
    os.environ["ODL_HYBRID"] = odl_hybrid
    path = _save_upload(file)
    try:
        md = await _run_blocking(convert_to_md, path)
        return {"md": md, "analyze": await _run_blocking(analyze, path), "filename": file.filename}
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/convert/epub-to-md")
async def epub_to_md(file: UploadFile = File(...)):
    path = _save_upload(file)
    try:
        md = await _run_blocking(convert_to_md, path)
        return {"md": md, "analyze": await _run_blocking(analyze, path), "filename": file.filename}
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/ocr/queue")
async def ocr_queue(file: UploadFile = File(...)):
    """扫描版 PDF → OCR 队列(转发 ocr-vllm; 当前 GPU 未就绪时返回排队状态)。"""
    path = _save_upload(file)
    try:
        import shutil
        ocr_dir = Path("/mnt/user/books/待OCR")
        if not ocr_dir.exists():
            try:
                ocr_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                ocr_dir = Path("/tmp/ocr_queue")
                ocr_dir.mkdir(parents=True, exist_ok=True)
        dest = ocr_dir / Path(file.filename).name
        shutil.move(path, dest)
        return {"status": "queued", "path": str(dest), "note": "ocr-vllm 按需消费(当前 GPU 未就绪时排队等待)"}
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/convert/office-to-md")
async def office_to_md(file: UploadFile = File(...)):
    """Office 文档(DOCX/PPTX/XLSX/ODT/RTF/CSV)→ MD(anydoc, firecrawl, 毫秒级)。"""
    path = _save_upload(file)
    try:
        md = await _run_blocking(convert_office_to_md, path)
        return {"md": md, "engine": "anydoc", "filename": file.filename}
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/convert/pdf-to-docx")
async def pdf_to_docx(file: UploadFile = File(...), dpi: int = Form(200)):
    path = _save_upload(file)
    out = path + ".docx"
    try:
        info = await _run_blocking(convert_to_docx, path, out, dpi=dpi)
        return FileResponse(
            out, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=Path(file.filename).stem + ".docx")
    finally:
        try:
            Path(path).unlink()  # ★2026-08-11 FileResponse 懒加载, out 不能提前删(留 /tmp 临时文件)
        except OSError:
            pass


@app.post("/convert/analyze")
async def analyze_file(file: UploadFile = File(...)):
    path = _save_upload(file)
    try:
        return await _run_blocking(analyze, path)
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/office/generate")
async def office_generate(doc_type: str = Form("docx"), topic: str = Form(...), prompt: str = Form("")):
    """officecli AI 生成 Office(docx/pptx/xlsx/report) — 返回生成文件流(前端直接下载)。"""
    import subprocess, tempfile, mimetypes

    def _gen():
        outdir = tempfile.mkdtemp(prefix="office_out_")
        cmd = ["officecli", "new", doc_type, topic, "--prompt", prompt or f"Create a {doc_type} about {topic}", "--out", outdir, "--mode", "fast"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            return {"ok": False, "error": proc.stderr[-2000:] or proc.stdout[-2000:]}
        files = [str(p) for p in Path(outdir).rglob("*") if p.is_file()]
        if not files:
            return {"ok": False, "error": "生成失败: 无输出文件"}
        return files[0]

    result = await _run_blocking(_gen)
    if isinstance(result, dict):
        return result
    mime = mimetypes.guess_type(result)[0] or "application/octet-stream"
    return FileResponse(result, media_type=mime, filename=Path(result).name)


@app.post("/extract")
async def extract_grounded(file: UploadFile = File(...), prompt: str = Form(...),
                           examples_json: str = Form("[]"), html: str = Form("0")):
    """LangExtract grounded 提取: 上传文档 + 指令 + few-shot → 结构化 JSON + 源定位。
    examples_json: [{"text": "...", "extractions": [{"extraction_class","extraction_text"}]}]"""
    from .grounded_extract import extract_html, grounded_extract
    import json as _json
    path = _save_upload(file)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        examples = _json.loads(examples_json) if examples_json else []
        r = await _run_blocking(grounded_extract, text, prompt, examples)
        if html == "1":
            r["html"] = await _run_blocking(extract_html, text, r)
        return r
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass
