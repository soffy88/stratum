"""Tests for the opendataloader-pdf (ODL) adapter and its integration into
the PDF→Markdown chain and scan-OCR service.

All subprocess / network / binary lookups are mocked — no ODL binary, Java
runtime or docling-fast server is required to run these tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# ── odl_adapter: binary resolution ────────────────────────────────────────────


def test_find_bin_missing_override_returns_path_hit(tmp_path: Path):
    """When the env override points to a missing path, ODL is found on PATH."""
    from stratum.services import odl_adapter

    with patch.object(odl_adapter, "shutil") as sh:
        sh.which.return_value = "/usr/bin/opendataloader-pdf"
        with patch("stratum.services.odl_adapter.config") as cfg:
            cfg.ODL_BIN = "opendataloader-pdf"  # default → fall through to which()
            # Mask the fallback venv candidate so the PATH hit is the outcome.
            with patch.object(odl_adapter, "os") as fake_os:
                fake_os.path.expanduser.return_value = str(tmp_path / "no-such-home")
                assert odl_adapter.find_bin() == "/usr/bin/opendataloader-pdf"


def test_find_bin_missing_override_not_found_anywhere(tmp_path: Path):
    """No env path, no PATH entry, no venv candidate → None."""
    from stratum.services import odl_adapter

    with patch.object(odl_adapter, "shutil") as sh:
        sh.which.return_value = None
        with patch("stratum.services.odl_adapter.config") as cfg:
            cfg.ODL_BIN = "opendataloader-pdf"
            with patch.object(odl_adapter, "os") as fake_os:
                fake_os.path.expanduser.return_value = str(tmp_path / "no-such-home")
                assert odl_adapter.find_bin() is None


def test_find_bin_prefers_existing_env_override(tmp_path: Path):
    from stratum.services import odl_adapter

    fake = tmp_path / "odl-bin"
    fake.write_text("#!/bin/sh\nexit 0\n")
    with patch("stratum.services.odl_adapter.config") as cfg:
        cfg.ODL_BIN = str(fake)
        assert odl_adapter.find_bin() == str(fake)


# ── odl_adapter: text-layer probe ────────────────────────────────────────────


def test_has_text_layer_false_for_image_only_pdf(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake scan")

    class _FakePage:
        def get_text(self, *a, **k):
            return "   "

    class _FakeDoc:
        def __iter__(self):
            return iter([_FakePage()])

        def close(self):
            pass

    class _StubFitz:
        @staticmethod
        def open(path):
            return _FakeDoc()

    import sys

    real = sys.modules.get("fitz")
    sys.modules["fitz"] = _StubFitz()
    try:
        assert odl_adapter.has_text_layer(pdf) is False
    finally:
        if real is not None:
            sys.modules["fitz"] = real
        else:
            sys.modules.pop("fitz", None)


def test_has_text_layer_true_when_probe_fails(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a pdf")
    import sys

    class _StubFitz:
        @staticmethod
        def open(path):
            raise ValueError("no fitz")

    real = sys.modules.get("fitz")
    sys.modules["fitz"] = _StubFitz()
    try:
        assert odl_adapter.has_text_layer(pdf) is True
    finally:
        if real is not None:
            sys.modules["fitz"] = real


# ── odl_adapter: convert ─────────────────────────────────────────────────────


def test_convert_raises_when_binary_missing(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with patch.object(odl_adapter, "find_bin", return_value=None):
        with pytest.raises(odl_adapter.OdlUnavailable):
            odl_adapter.convert(pdf)


def test_convert_invokes_cli_and_reads_markdown(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "# 第一章\n\n这是一个测试段落，足够长以通过最小字符数检查。" * 5
    (tmp_path / "book.md").write_text(body, encoding="utf-8")

    proc = odl_adapter.subprocess.CompletedProcess(
        args=["odl", str(pdf)], returncode=0, stdout="", stderr=""
    )
    with patch.object(odl_adapter, "find_bin", return_value="/usr/bin/odl"):
        with patch.object(odl_adapter, "has_text_layer", return_value=True):
            with patch.object(odl_adapter.subprocess, "run", return_value=proc) as run:
                text = odl_adapter.convert(pdf, use_hybrid=False)
    assert text == body
    argv = run.call_args[0][0]
    assert argv[0] == "/usr/bin/odl"
    assert str(pdf) in argv
    assert "--hybrid" not in argv


def test_convert_uses_hybrid_flags_for_scans(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "OCR 文本结果" * 10
    (tmp_path / "scan.md").write_text(body, encoding="utf-8")
    proc = odl_adapter.subprocess.CompletedProcess(
        args=["odl", str(pdf)], returncode=0, stdout="", stderr=""
    )
    with patch.object(odl_adapter, "find_bin", return_value="/usr/bin/odl"):
        with patch.object(odl_adapter, "has_text_layer", return_value=False):
            with patch.object(odl_adapter, "ocr_available", return_value=True):
                with patch.object(odl_adapter.config, "ODL_HYBRID_URL", "http://127.0.0.1:5002"):
                    with patch.object(odl_adapter.subprocess, "run", return_value=proc) as run:
                        odl_adapter.convert(pdf, use_hybrid=True)
    argv = run.call_args[0][0]
    assert "--hybrid" in argv
    assert "docling-fast" in argv


def test_convert_hybrid_downgrades_for_digital_pdfs(tmp_path: Path):
    from stratum.services import odl_adapter

    pdf = tmp_path / "digital.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "数字 PDF 文本，足够长。" * 5
    (tmp_path / "digital.md").write_text(body, encoding="utf-8")
    proc = odl_adapter.subprocess.CompletedProcess(
        args=["odl", str(pdf)], returncode=0, stdout="", stderr=""
    )
    with patch.object(odl_adapter, "find_bin", return_value="/usr/bin/odl"):
        with patch.object(odl_adapter, "has_text_layer", return_value=True):
            with patch.object(odl_adapter.subprocess, "run", return_value=proc) as run:
                odl_adapter.convert(pdf, use_hybrid=True)  # scanned==False → hybrid off
    argv = run.call_args[0][0]
    assert "--hybrid" not in argv


# ── pdf_to_markdown integration ──────────────────────────────────────────────


def test_pdf_to_markdown_prefers_odl_when_enabled(tmp_path: Path):
    from stratum.services import odl_adapter, pdf_to_markdown as m

    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "# ODL 输出\n\n内容足够长以通过校验。" * 5

    with patch.object(odl_adapter, "is_enabled", return_value=True):
        with patch.object(odl_adapter, "is_hybrid", return_value=False):
            with patch.object(odl_adapter, "has_text_layer", return_value=True):
                with patch.object(odl_adapter, "convert", return_value=body) as cv:
                    out, parser = m.pdf_to_markdown(pdf)
    assert out.suffix == ".md"
    assert out.read_text(encoding="utf-8") == body
    assert parser == "odl"
    cv.assert_called_once_with(pdf, use_hybrid=False)


def test_pdf_to_markdown_odl_failure_falls_back_to_docling(tmp_path: Path):
    from stratum.services import odl_adapter, pdf_to_markdown as m

    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "docling 兜底输出，足够长。" * 5

    with patch.object(odl_adapter, "is_enabled", return_value=True):
        with patch.object(
            odl_adapter, "convert", side_effect=odl_adapter.OdlUnavailable("bin missing")
        ):
            with patch.object(m, "_via_docling", return_value=body):
                out, parser = m.pdf_to_markdown(pdf)
    assert out.read_text(encoding="utf-8") == body
    assert parser == "docling"


def test_pdf_to_markdown_ignores_odl_when_disabled(tmp_path: Path):
    from stratum.services import odl_adapter, pdf_to_markdown as m

    pdf = tmp_path / "ok.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    body = "pdftotext 文本兜底，足够长。" * 5

    with patch.object(odl_adapter, "is_enabled", return_value=False):
        with patch.object(odl_adapter, "convert") as cv:
            with patch.object(m, "_via_docling", side_effect=ImportError("no docling")):
                with patch.object(m, "_via_pymupdf4llm", side_effect=ImportError("no pymupdf4llm")):
                    with patch.object(m, "_via_pdftotext", return_value=body):
                        out, parser = m.pdf_to_markdown(pdf)
    cv.assert_not_called()
    assert parser == "pdftotext"


# ── scan_ocr_service integration ─────────────────────────────────────────────


def test_scan_ocr_odl_hybrid_available_true():
    from stratum.services import scan_ocr_service as s
    from stratum.services import odl_adapter

    with patch.object(odl_adapter, "is_enabled", return_value=True):
        with patch.object(odl_adapter, "is_hybrid", return_value=True):
            with patch.object(odl_adapter, "ocr_available", return_value=True):
                assert s._odl_hybrid_available() is True


def test_scan_ocr_odl_hybrid_available_false_when_disabled():
    from stratum.services import scan_ocr_service as s
    from stratum.services import odl_adapter

    with patch.object(odl_adapter, "is_enabled", return_value=False):
        assert s._odl_hybrid_available() is False
