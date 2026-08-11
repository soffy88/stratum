"""stratum-docs 转换核心 — PDF/EPUB → MD / DOCX。

与 aii/*_convert.py 同引擎(主: oprim parse_pdf; fallback: markitdown; 清洗同款),
迁移后转换结果与主机脚本完全一致。无 docling。
"""
from __future__ import annotations

import os
import re
from collections import Counter

import fitz

_MD_HEADER = re.compile(r"^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+章|CHAPTER\s+\d+)\b")


def chapters(text: str) -> int:
    """章节数(与 aii convert 同口径, 含前导空格/教辅结构/arXiv '1. Introduction')。"""
    return len(re.findall(
        r"(?m)^\s*#\s+Chapter\s+\d|^\s*第[一二三四五六七八九十百千0-9]+(章|单元|讲|课|节|部分|回|篇)"
        r"|^\s*Chapter\s+\d|^\d{1,2}\.\s+[A-Z][A-Za-z]{2,}",
        text))


def analyze(path: str) -> dict:
    """分析: 打不开/无文字层/无章节/可转 + 页数 + 信号。"""
    try:
        d = fitz.open(path)
    except Exception as e:
        return {"category": "打不开", "pages": 0, "detail": str(e)[:80]}
    npg = d.page_count
    try:
        full = "".join(p.get_text() for p in d)
    except Exception:
        return {"category": "打不开", "pages": npg, "detail": "text extract error"}
    samp = "".join(d[p].get_text() for p in range(0, min(npg, 60), 6))
    txt_ratio = len(samp) / max(min(npg, 60) // 6, 1)
    nch = chapters(full)
    if txt_ratio < 200:
        return {"category": "需OCR(无文字层)", "pages": npg, "chapters": nch}
    if nch < 3:
        return {"category": "无章节结构", "pages": npg, "chapters": nch}
    # 乱码信号(复用 math_corruption_gate, 只报告不拦截)
    signals = {}
    try:
        from math_corruption_gate import corruption_signals
        signals = corruption_signals(full)
        from math_corruption_gate import is_corrupted
        signals["corrupted"] = is_corrupted(full)[0]
    except Exception:
        pass
    return {"category": "可转", "pages": npg, "chapters": nch, "signals": signals}


def convert_to_md(path: str) -> str:
    """PDF/EPUB → 清洗后 MD(与 aii convert 同款: pdf_inspector → markitdown fallback → 清洗)。"""
    text = None
    if str(path).lower().endswith(".pdf"):
        try:
            from oprim.parser.parse_pdf import parse_pdf
            if os.getenv("ODL_HYBRID") == "1":
                pc = parse_pdf(path, provider="opendataloader", hint={"hybrid": True})
            else:
                pc = parse_pdf(path, provider="pdf_inspector")
            text = pc.markdown
        except Exception:
            pass
    if text is None:
        from markitdown import MarkItDown
        text = MarkItDown().convert(path).text_content

    npg = fitz.open(path).page_count
    lines = text.split("\n")
    cnt = Counter(l.strip() for l in lines if l.strip())
    thresh = max(3, int(npg * 0.12))
    headers = {l for l, c in cnt.items() if c > thresh and len(l) < 80}
    out = []
    for l in lines:
        s = l.strip()
        if not s or s in headers or re.fullmatch(r"\d{1,4}", s):
            continue
        if _MD_HEADER.match(s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


def convert_to_docx(path: str, out_path: str, dpi: int = 200) -> dict:
    """PDF → DOCX(全页图片版): 每页渲染 JPEG 嵌入, 页码标注原页码。无方框/乱码。"""
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    d = fitz.open(path)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    sec.left_margin = sec.right_margin = Inches(0.5)
    sec.top_margin = sec.bottom_margin = Inches(0.4)

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="docs_")
    for i, page in enumerate(d):
        pix = page.get_pixmap(dpi=dpi)
        img = f"{tmpdir}/p{i+1:03d}.jpg"
        pix.save(img)
        from PIL import Image
        Image.open(img).convert("RGB").save(img, "JPEG", quality=85)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(img, width=Inches(7.3))
        cap = doc.add_paragraph(f"第 {i + 1} 页")
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in cap.runs:
            r.font.size = Pt(9)

    doc.save(out_path)
    return {"pages": d.page_count, "out": out_path}
