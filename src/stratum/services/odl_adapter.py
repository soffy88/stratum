"""opendataloader-pdf (ODL) adapter for Stratum PDF parsing.

ODL is a fast JVM-based PDF parser (Apache-2.0, no OCR in local mode). When
enabled it sits ahead of Docling in the pdf_to_markdown chain; scanned PDFs
optionally route to the ODL hybrid backend (docling-fast) for OCR.

Env vars (see stratum.config):
  STRATUM_ODL_ENABLED      master switch, default false
  STRATUM_ODL_BIN          CLI name/path, default "opendataloader-pdf"
  STRATUM_ODL_HYBRID       route scans through ODL hybrid OCR, default false
  STRATUM_ODL_HYBRID_URL  docling-fast server URL, default http://127.0.0.1:5002
  STRATUM_ODL_TIMEOUT_S    per-file timeout, default 600
  STRATUM_ODL_MIN_CHARS   minimum markdown chars to accept, default 40
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

import stratum.config as config

log = logging.getLogger(__name__)


class OdlUnavailable(Exception):
    """ODL binary not found or invocation failed (caller may fall back)."""


def is_enabled() -> bool:
    return bool(config.ODL_ENABLED)


def is_hybrid() -> bool:
    return bool(config.ODL_HYBRID)


def find_bin() -> str | None:
    """Locate the opendataloader-pdf CLI: env override → PATH → project venv."""
    env_bin = config.ODL_BIN.strip()
    if env_bin and env_bin != "opendataloader-pdf":
        p = Path(env_bin)
        return str(p) if p.exists() else None
    found = shutil.which("opendataloader-pdf")
    if found:
        return found
    # Fallback: sibling project venv used by the evaluation harness
    candidate = Path(os.path.expanduser("~/projects/stratum-odl/.venv-odl/bin/opendataloader-pdf"))
    return str(candidate) if candidate.exists() else None


def has_text_layer(pdf: Path) -> bool:
    """Cheap check: does the PDF carry a text layer? (False → scanned)."""
    try:
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open(str(pdf))
        try:
            sample = [page.get_text("text").strip() for page in doc]
        finally:
            doc.close()
        nonempty = [s for s in sample if s]
        if not nonempty:
            return False
        # Scanned PDFs often have a thin OCR layer; treat mostly-empty text as scanned
        total = sum(len(s) for s in nonempty)
        per_page = total / len(sample)
        return per_page >= 20
    except Exception:
        log.warning("odl_adapter: text-layer probe failed for %s", pdf.name, exc_info=True)
        return True  # assume digital so we don't force OCR on unknown files


def ocr_available() -> bool:
    """Whether the ODL hybrid OCR backend is actually reachable."""
    if not is_hybrid():
        return False
    url = config.ODL_HYBRID_URL or "http://127.0.0.1:5002"
    try:
        import httpx

        with httpx.Client(timeout=3.0) as client:
            # docling-fast exposes /health
            r = client.get(f"{url}/health")
            return r.status_code < 500
    except Exception:
        return False


def convert(
    pdf: Path,
    *,
    use_hybrid: bool | None = None,
    timeout_s: int | None = None,
) -> str:
    """Run ODL CLI on pdf, return markdown text.

    use_hybrid=None → auto-decide (hybrid only for scanned files when ocr_available()).
    Raises OdlUnavailable on any failure (binary missing, non-zero exit, empty output).
    """
    pdf = Path(pdf)
    binary = find_bin()
    if binary is None:
        raise OdlUnavailable("opendataloader-pdf binary not found (set STRATUM_ODL_BIN)")

    hybrid = ocr_available() if use_hybrid is None else bool(use_hybrid)
    scanned = not has_text_layer(pdf)
    if hybrid and not scanned:
        hybrid = False  # hybrid is only useful for scans

    argv = [
        binary,
        str(pdf),
        "--format",
        "markdown",
        "-o",
        str(pdf.parent),
        "--content-safety-off",
        "all",
    ]
    if hybrid:
        argv += [
            "--hybrid",
            "docling-fast",
            "--hybrid-url",
            config.ODL_HYBRID_URL or "http://127.0.0.1:5002",
        ]

    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout_s or config.ODL_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-300:]
        raise OdlUnavailable(f"odl exit {proc.returncode}: {tail}")
    # ODL writes <stem>.md (or <stem>.json etc.) into the -o directory.
    out_md = pdf.parent / f"{pdf.stem}.md"
    if not out_md.exists():
        # Also accept a stray .odl.md produced by earlier invocations
        alt = pdf.parent / f"{pdf.stem}.odl.md"
        if alt.exists():
            out_md = alt
        else:
            raise OdlUnavailable(f"odl produced no markdown for {pdf.name}")
    text = out_md.read_text(encoding="utf-8").strip()
    if len(text) < (config.ODL_MIN_CHARS or 40):
        raise OdlUnavailable(f"odl output too short ({len(text)} chars)")
    return text
