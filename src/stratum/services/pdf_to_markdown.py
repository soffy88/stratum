"""PDF → Markdown for inbox ingest.

Parser chain (configurable via STRATUM_ODL_ENABLED):
  1) ODL (opendataloader-pdf) when enabled — fast, accurate text extraction;
     scanned PDFs route to the ODL hybrid backend (docling-fast) for OCR when
     STRATUM_ODL_HYBRID is on and the backend is reachable.
  2) Docling (tables + code), then pymupdf4llm/oprim, then text-only
     ``pdftotext`` fallback.
Converts before omodul process_inbox_substrate (same pattern as DOCX→MD).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
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

    # 0) ODL (opendataloader-pdf) — fast JVM parser, optional first choice.
    # On ODL failure (missing binary, OCR backend down, ...) we fall through to
    # the existing chain below; ODL never blocks ingestion.
    try:
        from stratum.services import odl_adapter

        if odl_adapter.is_enabled():
            hybrid = odl_adapter.is_hybrid() and not odl_adapter.has_text_layer(path)
            text = odl_adapter.convert(path, use_hybrid=hybrid)
            md_path.write_text(text, encoding="utf-8")
            parser = "odl-hybrid" if hybrid else "odl"
            log.info("pdf_to_md parser=%s path=%s chars=%d", parser, path.name, len(text))
            return md_path, parser
    except Exception as e:
        errors.append(f"odl:{type(e).__name__}:{e}")
        log.warning("pdf_to_md ODL unavailable, falling back to chain: %s", e)

    # 1) Docling (preferred when ODL off/unavailable)
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

    # 4) Poppler's pdftotext is a deliberately narrow, dependency-light fallback.
    # It preserves text when the richer parsers are not installed, but does not
    # claim layout/table fidelity; the benchmark still evaluates those dimensions
    # separately when reviewed annotations are present.
    try:
        text = _via_pdftotext(path)
        if text and len(text.strip()) > 40:
            md_path.write_text(text, encoding="utf-8")
            log.info("pdf_to_md parser=pdftotext path=%s chars=%d", path.name, len(text))
            return md_path, "pdftotext"
        errors.append("pdftotext_empty")
    except Exception as e:
        errors.append(f"pdftotext:{type(e).__name__}:{e}")
        log.warning("pdf_to_md pdftotext failed: %s", e)

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


def _via_pdftotext(path: Path) -> str:
    """Extract text through the system Poppler binary, without invoking a shell."""
    executable = shutil.which("pdftotext")
    if executable is None:
        raise RuntimeError("pdftotext executable not found")

    completed = subprocess.run(
        [executable, "-layout", str(path), "-"],
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().replace("\n", " ")[:240]
        raise RuntimeError(f"pdftotext exited with {completed.returncode}: {detail}")
    return completed.stdout or ""
