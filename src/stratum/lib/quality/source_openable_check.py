"""source_openable_check — 真正打开源文件,确认可读.

PDF  : fitz.open() + page_count > 0
EPUB : zipfile 解包 + 找 OPF spine
其他 : 文件存在且非空即通过
"""
from __future__ import annotations

import zipfile
from pathlib import Path


def check_source_openable(source_path: str | None, mime: str | None) -> tuple[bool, str | None]:
    """Return (ok, reason_if_not). reason 约定: file_missing / pdf_no_pages /
    pdf_open_failed / epub_no_opf / epub_no_spine / epub_open_failed / file_empty.
    """
    if not source_path:
        return False, "file_missing"
    path = Path(source_path)
    if not path.exists():
        return False, "file_missing"

    mime_lower = (mime or "").lower()

    if "pdf" in mime_lower:
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(path))
            count = doc.page_count
            doc.close()
            if count <= 0:
                return False, "pdf_no_pages"
            return True, None
        except Exception:
            return False, "pdf_open_failed"

    if "epub" in mime_lower:
        try:
            with zipfile.ZipFile(str(path)) as z:
                names = z.namelist()
                opf_files = [n for n in names if n.lower().endswith(".opf")]
                if not opf_files:
                    return False, "epub_no_opf"
                opf_content = z.read(opf_files[0]).decode("utf-8", errors="ignore")
                if "<spine" not in opf_content:
                    return False, "epub_no_spine"
            return True, None
        except zipfile.BadZipFile:
            return False, "epub_open_failed"
        except Exception:
            return False, "epub_open_failed"

    # txt / md / html / video 等 — 文件存在且非空即通过
    if path.stat().st_size == 0:
        return False, "file_empty"
    return True, None
