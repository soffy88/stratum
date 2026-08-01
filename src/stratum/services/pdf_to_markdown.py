"""PDF → Markdown for inbox ingest.

MVP: prefer Docling (tables + code), fall back to pymupdf4llm.
Converts before omodul process_inbox_substrate (same pattern as DOCX→MD).
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def pdf_to_markdown(path: Path) -> tuple[Path, str]:
    """Convert PDF to a sibling .md file. Returns (md_path, parser_name).

    On total failure returns (original_path, "passthrough") so caller can still try omodul PDF path.
    """
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return path, "skip"

    md_path = path.with_suffix(".md")
    # Already converted
    if md_path.exists() and md_path.stat().st_size > 0:
        return md_path, "cached"

    errors: list[str] = []

    # 1) Docling (preferred)
    try:
        text = _via_docling(path)
        if text and len(text.strip()) > 40:
            md_path.write_text(text, encoding="utf-8")
            log.info("pdf_to_md parser=docling path=%s chars=%d", path.name, len(text))
            return md_path, "docling"
        errors.append("docling_empty")
    except Exception as e:
        errors.append(f"docling:{type(e).__name__}:{e}")
        log.warning("pdf_to_md docling failed: %s", e)

    # 2) pymupdf4llm
    try:
        text = _via_pymupdf4llm(path)
        if text and len(text.strip()) > 40:
            md_path.write_text(text, encoding="utf-8")
            log.info("pdf_to_md parser=pymupdf4llm path=%s chars=%d", path.name, len(text))
            return md_path, "pymupdf4llm"
        errors.append("pymupdf_empty")
    except Exception as e:
        errors.append(f"pymupdf:{type(e).__name__}:{e}")
        log.warning("pdf_to_md pymupdf4llm failed: %s", e)

    # 3) oprim.parse_pdf if available
    try:
        from oprim.parser.parse_pdf import parse_pdf

        pc = parse_pdf(path, provider="auto")
        text = getattr(pc, "markdown", None) or getattr(pc, "plaintext", "") or ""
        if text and len(text.strip()) > 40:
            md_path.write_text(text, encoding="utf-8")
            log.info("pdf_to_md parser=oprim path=%s chars=%d", path.name, len(text))
            return md_path, "oprim:" + (getattr(pc, "parser_name", "") or "auto")
        errors.append("oprim_empty")
    except Exception as e:
        errors.append(f"oprim:{type(e).__name__}:{e}")

    log.error("pdf_to_md all parsers failed path=%s errors=%s", path, errors)
    return path, "passthrough:" + ";".join(errors[:3])


def _via_docling(path: Path) -> str:
    from docling.document_converter import DocumentConverter

    conv = DocumentConverter()
    result = conv.convert(str(path))
    # export_to_markdown is the standard path in recent docling
    doc = result.document
    if hasattr(doc, "export_to_markdown"):
        return doc.export_to_markdown() or ""
    if hasattr(result, "document") and hasattr(result.document, "export_to_text"):
        return result.document.export_to_text() or ""
    return str(doc)


def _via_pymupdf4llm(path: Path) -> str:
    import pymupdf4llm

    return pymupdf4llm.to_markdown(str(path)) or ""
