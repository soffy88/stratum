"""stratum-docs 微服务 — PDF/EPUB 转换统一入口(FastAPI)。

POST /convert/pdf-to-md      multipart(file) + form(odl_hybrid) → {md, analyze}
POST /convert/epub-to-md     multipart(file) → {md, analyze}
POST /convert/pdf-to-docx    multipart(file) + form(dpi) → docx 文件下载
POST /convert/analyze        multipart(file) → analyze 信号
GET  /health
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse

from .converter import analyze, convert_to_docx, convert_to_md

app = FastAPI(title="stratum-docs", version="0.1.0")


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
        md = convert_to_md(path)
        return {"md": md, "analyze": analyze(path), "filename": file.filename}
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/convert/epub-to-md")
async def epub_to_md(file: UploadFile = File(...)):
    path = _save_upload(file)
    try:
        md = convert_to_md(path)
        return {"md": md, "analyze": analyze(path), "filename": file.filename}
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
        info = convert_to_docx(path, out, dpi=dpi)
        return FileResponse(
            out, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=Path(file.filename).stem + ".docx")
    finally:
        try:
            Path(path).unlink()
            Path(out).unlink()
        except OSError:
            pass


@app.post("/convert/analyze")
async def analyze_file(file: UploadFile = File(...)):
    path = _save_upload(file)
    try:
        return analyze(path)
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass
