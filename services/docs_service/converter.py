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
    return len(
        re.findall(
            r"(?m)^\s*#\s+Chapter\s+\d|^\s*第[一二三四五六七八九十百千0-9]+(章|单元|讲|课|节|部分|回|篇)"
            r"|^\s*Chapter\s+\d|^\d{1,2}\.\s+[A-Z][A-Za-z]{2,}",
            text,
        )
    )


def analyze(path: str) -> dict:
    """分析: pdf-inspector 分类(Rust, 最强) + 章节/文字层信号。
    pdf_type: text_based/scanned/image_based/mixed; pages_needing_ocr 供 OCR 路由。"""
    out: dict = {}
    # 1. pdf-inspector 分类(优先)
    try:
        import pdf_inspector

        c = pdf_inspector.classify_pdf(path)
        out.update(
            {
                "pdf_type": c.pdf_type,
                "confidence": round(c.confidence, 3),
                "page_count": c.page_count,
                "pages_needing_ocr": list(c.pages_needing_ocr or []),
            }
        )
    except Exception:
        pass
    # 2. 兼容原信号(fitz 文字层/章节/乱码)
    try:
        d = fitz.open(path)
    except Exception as e:
        out.setdefault("category", "打不开")
        out["detail"] = str(e)[:80]
        return out
    npg = d.page_count
    try:
        full = "".join(p.get_text() for p in d)
    except Exception:
        out.setdefault("category", "打不开")
        return out
    samp = "".join(d[p].get_text() for p in range(0, min(npg, 60), 6))
    out["pages"] = npg
    out["chapters"] = chapters(full)
    out["text_ratio"] = round(len(samp) / max(min(npg, 60) // 6, 1), 1)
    # 综合分类(兼容旧调用方)
    pt = out.get("pdf_type")
    if pt in ("scanned", "image_based"):
        out["category"] = "需OCR(无文字层)"
    elif pt == "mixed":
        out["category"] = "可转(混合, 部分页需OCR)"
    elif out.get("text_ratio", 0) < 200:
        out["category"] = "需OCR(无文字层)"
    elif out.get("chapters", 0) < 3:
        out["category"] = "无章节结构"
    else:
        out["category"] = "可转"
    return out


_MATH_CH = set("=<>±∑∫∂√≤≥∈∀∃→⊂⊆∪∩×÷^_{}")
_ODL_TIMEOUT = int(os.getenv("ODL_TIMEOUT_SEC", "900"))


def _page_count(path: str) -> int:
    try:
        return fitz.open(path).page_count
    except Exception:
        return 0


def _pi_quality_issue(md: str, npg: int) -> str | None:
    """pdf_inspector 结果质量门禁; 返回问题原因(→ 换 ODL), None = 合格。

    依据 2026-10-11 18 本数字书对照测试:
      - short: 结果 <500 字(只吐 TOC / 整本空, 如代数几何百科)
      - replacement_chars: U+FFFD 乱码 >0.1% 且 >20 个(如 Python ML 8835 个)
      - fake_headings: 短文档(≤60 页, 论文)公式被当成标题 >30%
        长书不用此条: 长书上 ODL 切章反而更差。
    """
    if len(md) < 500:
        return "short"
    bad = md.count("\ufffd")
    if bad > 20 and bad > len(md) * 0.001:
        return "replacement_chars"
    if 0 < npg <= 60:
        heads = re.findall(r"(?m)^#{1,6} (.*)$", md)
        fake = sum(1 for h in heads if sum(c in _MATH_CH for c in h) >= 2 or len(h) > 120)
        if len(heads) >= 10 and fake / len(heads) > 0.3:
            return "fake_headings"
    return None


_RUN_HEAD = re.compile(r"^#{1,6}\s+(.*)$")


def _drop_running_heads(md: str, npg: int) -> str:
    """ODL 会把运行页眉判成标题(如 '#### 36 2. BUILDING BLOCKS'): 去掉页码后重复出现的标题行删除。"""

    def norm(h: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"^\d{1,4}\s+|\s+\d{1,4}$", "", h.strip())).strip()

    lines = md.split("\n")
    cnt = Counter(norm(m.group(1)) for ln in lines if (m := _RUN_HEAD.match(ln.strip())))
    thresh = max(3, int(npg * 0.05))
    rep = {k for k, c in cnt.items() if k and c > thresh}
    out = []
    for ln in lines:
        m = _RUN_HEAD.match(ln.strip())
        if m and norm(m.group(1)) in rep:
            continue
        out.append(ln)
    return "\n".join(out)


def _odl_markdown(path: str, npg: int) -> str | None:
    """opendataloader-pdf fast 模式(Java, 无 OCR/hybrid)。不可用/超时/失败 → None。"""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    exe = shutil.which("opendataloader-pdf")
    if not exe or not shutil.which("java"):
        return None
    with tempfile.TemporaryDirectory(prefix="odl_") as td:
        try:
            subprocess.run(
                [exe, path, "-o", td, "-f", "markdown", "--image-output", "off"],
                check=True,
                timeout=_ODL_TIMEOUT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None
        mds = list(Path(td).rglob("*.md"))
        if not mds:
            return None
        md = mds[0].read_text(encoding="utf-8", errors="replace")
    md = _drop_running_heads(md, npg)
    return md if len(md) >= 500 else None


def convert_to_md(path: str) -> str:
    """PDF/EPUB → MD。

    PDF 引擎顺序(2026-10-11):
      1. pdf-inspector(Rust, 主力; 切章/表格最好)
      2. 质量门禁不过 → opendataloader-pdf fast(Java, 治空输出/乱码/论文公式假标题)
      3. oprim parse_pdf(pymupdf4llm; ODL_HYBRID=1 时 opendataloader hybrid)
      4. markitdown 兜底
    扫描件 OCR 不在此处(走 Unlimited-OCR 链路), 本函数不做 OCR。
    """
    if str(path).lower().endswith(".pdf"):
        npg = _page_count(path)
        pi_md = None
        try:
            import pdf_inspector

            pi_md = pdf_inspector.process_pdf(path).markdown or ""
        except Exception:
            pi_md = None
        issue = "error" if pi_md is None else _pi_quality_issue(pi_md, npg)
        if issue is None:
            return _clean_md(pi_md, path)
        odl_md = _odl_markdown(path, npg)
        if odl_md is not None:
            return _clean_md(odl_md, path)
        # ODL 不可用且 pi 只是质量欠佳(非空): 仍用 pi, 不退回更差的 markitdown
        if pi_md and len(pi_md) >= 500:
            return _clean_md(pi_md, path)
    # fallback: oprim parse_pdf → markitdown(同旧逻辑)
    text = None
    try:
        from oprim.parser.parse_pdf import parse_pdf

        if os.getenv("ODL_HYBRID") == "1":
            pc = parse_pdf(path, provider="opendataloader", hint={"hybrid": True})
        else:
            pc = parse_pdf(path, provider="pymupdf4llm")
        text = pc.markdown
    except Exception:
        pass
    if text is None:
        from markitdown import MarkItDown

        text = MarkItDown().convert(path).text_content
    return _clean_md(text, path)


def _clean_md(text: str, path: str) -> str:
    """清洗(页眉/页码/章节提升) — 与旧 convert 同款。"""
    try:
        npg = fitz.open(path).page_count
    except Exception:
        npg = 0
    lines = text.split("\n")
    cnt = Counter(ln.strip() for ln in lines if ln.strip())
    thresh = max(3, int(npg * 0.12))
    headers = {ln for ln, c in cnt.items() if c > thresh and len(ln) < 80}
    out = []
    for ln in lines:
        s = ln.strip()
        if not s or s in headers or re.fullmatch(r"\d{1,4}", s):
            continue
        if _MD_HEADER.match(s):
            out.append(f"\n# {s}\n")
        else:
            out.append(s)
    return "\n".join(out)


OFFICE_EXT = (
    ".docx",
    ".pptx",
    ".xlsx",
    ".odt",
    ".odp",
    ".ods",
    ".rtf",
    ".csv",
    ".doc",
    ".ppt",
    ".xls",
)


def convert_office_to_md(path: str) -> str:
    """Office 文档(DOCX/PPTX/XLSX/ODT/RTF/CSV…) → Markdown — anydoc(firecrawl, Rust, 毫秒级)。"""
    import anydoc

    return anydoc.to_markdown(path)


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
        img = f"{tmpdir}/p{i + 1:03d}.jpg"
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
