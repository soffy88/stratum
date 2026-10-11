"""stratum-docs PDF 引擎顺序: pdf-inspector 主力 → ODL 质量兜底 → 旧 fallback。"""

from __future__ import annotations

import sys
import types

try:
    import fitz  # noqa: F401
except ImportError:  # CI 环境可能没装 pymupdf: converter 只在模块级 import, 测试里全部打桩
    sys.modules["fitz"] = types.SimpleNamespace(open=lambda p: None)

from services.docs_service import converter as C  # noqa: E402

GOOD = "# Chapter 1 Intro\n\n" + "Plain readable text about sets and functions. " * 40


def _fake_pi(monkeypatch, md):
    mod = types.SimpleNamespace(process_pdf=lambda p: types.SimpleNamespace(markdown=md))
    monkeypatch.setitem(sys.modules, "pdf_inspector", mod)


def _stub(monkeypatch, npg=200, odl=None):
    monkeypatch.setattr(C, "_page_count", lambda p: npg)
    monkeypatch.setattr(C, "_clean_md", lambda t, p: t)
    calls = []

    def fake_odl(path, n):
        calls.append(path)
        return odl

    monkeypatch.setattr(C, "_odl_markdown", fake_odl)
    return calls


def test_quality_ok_long_book():
    assert C._pi_quality_issue(GOOD, 300) is None


def test_quality_short_output():
    assert C._pi_quality_issue("# TOC\n1 2 3", 300) == "short"


def test_quality_replacement_chars():
    assert C._pi_quality_issue(GOOD + "\ufffd" * 50, 300) == "replacement_chars"


def test_quality_few_replacement_chars_tolerated():
    assert C._pi_quality_issue(GOOD * 20 + "\ufffd" * 5, 300) is None


def test_fake_math_headings_only_for_short_docs():
    md = GOOD + "".join(f"\n## x_{i} = \\sum a_i + b^{i}\n" for i in range(12))
    assert C._pi_quality_issue(md, 20) == "fake_headings"
    assert C._pi_quality_issue(md, 300) is None


def test_drop_running_heads():
    md = "\n".join(
        [f"#### {n} 2. BUILDING BLOCKS\ntext {n}" for n in range(30, 40)] + ["## 2.1 Real Heading"]
    )
    out = C._drop_running_heads(md, 100)
    assert "BUILDING BLOCKS" not in out
    assert "## 2.1 Real Heading" in out


def test_pi_good_skips_odl(tmp_path, monkeypatch):
    _fake_pi(monkeypatch, GOOD)
    calls = _stub(monkeypatch)
    assert C.convert_to_md(str(tmp_path / "a.pdf")) == GOOD
    assert calls == []


def test_pi_empty_uses_odl(tmp_path, monkeypatch):
    _fake_pi(monkeypatch, "")
    _stub(monkeypatch, odl="ODL OUTPUT " * 100)
    assert C.convert_to_md(str(tmp_path / "a.pdf")).startswith("ODL OUTPUT")


def test_pi_weak_and_odl_missing_keeps_pi(tmp_path, monkeypatch):
    md = GOOD + "\ufffd" * 50
    _fake_pi(monkeypatch, md)
    _stub(monkeypatch, odl=None)
    assert C.convert_to_md(str(tmp_path / "a.pdf")) == md


def test_odl_missing_binary_returns_none(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert C._odl_markdown("/nonexistent.pdf", 10) is None
