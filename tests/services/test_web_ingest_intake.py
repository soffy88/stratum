"""ingest-url must land articles where the paper flywheel (aii/scripts/paper_discover.py) scans."""

from __future__ import annotations

import ast
import os
import stat
from pathlib import Path

import pytest

from stratum.services import web_ingest

REPO = Path(__file__).resolve().parents[2]


def _paper_dirs_from_discover() -> list[str]:
    """Extract the path literals of PAPER_DIRS from paper_discover.py without importing it."""
    src = (REPO / "aii" / "scripts" / "paper_discover.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PAPER_DIRS" for t in node.targets
        ):
            return [
                c.value
                for c in ast.walk(node)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
            ]
    raise AssertionError("PAPER_DIRS not found in paper_discover.py")


def test_candidates_match_paper_flywheel_dirs():
    lits = _paper_dirs_from_discover()
    # paper_discover: ROOT / "gdrive_staging" / "MD" / "论文"  and  /home/soffy/books/MD/论文
    assert "gdrive_staging" in lits and "论文" in lits
    assert "/home/soffy/books/MD/论文" in lits
    cands = [str(c) for c in web_ingest._PAPER_INTAKE_CANDIDATES]
    assert cands[0] == str(REPO / "aii" / "gdrive_staging" / "MD" / "论文")
    assert "/home/soffy/books/MD/论文" in cands
    # the legacy dir is NOT scanned by the paper flywheel and must never be the default
    assert str(web_ingest._LEGACY_INTAKE) not in cands
    assert web_ingest._DEFAULT_INTAKE != "/home/soffy/shared/stratum-to-aii"


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("STRATUM_AII_INTAKE_DIR", str(tmp_path / "x"))
    assert web_ingest.intake_dir() == tmp_path / "x"


def test_first_writable_candidate(monkeypatch, tmp_path):
    monkeypatch.delenv("STRATUM_AII_INTAKE_DIR", raising=False)
    missing = tmp_path / "missing"
    ro = tmp_path / "ro"
    ro.mkdir()
    ok = tmp_path / "ok"
    ok.mkdir()
    ro.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(ro, os.W_OK):  # running as root: chmod can't make it read-only
            pytest.skip("cannot simulate read-only dir as root")
        monkeypatch.setattr(web_ingest, "_PAPER_INTAKE_CANDIDATES", (missing, ro, ok))
        assert web_ingest.intake_dir() == ok
    finally:
        ro.chmod(stat.S_IRWXU)


def test_legacy_fallback_when_no_candidate(monkeypatch, tmp_path):
    monkeypatch.delenv("STRATUM_AII_INTAKE_DIR", raising=False)
    monkeypatch.setattr(web_ingest, "_PAPER_INTAKE_CANDIDATES", (tmp_path / "nope",))
    assert web_ingest.intake_dir() == web_ingest._LEGACY_INTAKE


def test_ingest_url_writes_into_paper_intake(monkeypatch, tmp_path):
    """End to end (fetch stubbed): file lands in the resolved paper intake with paper frontmatter."""
    monkeypatch.delenv("STRATUM_AII_INTAKE_DIR", raising=False)
    intake = tmp_path / "gdrive_staging" / "MD" / "论文"
    intake.mkdir(parents=True)
    monkeypatch.setattr(web_ingest, "_PAPER_INTAKE_CANDIDATES", (intake,))

    class _Res:
        success = True
        strategy = "stub"
        title = "测试文章"
        author = "a"
        published = ""
        markdown = "正文。" * 400
        error = None

    monkeypatch.setattr(web_ingest, "is_fetchable_url", lambda u: True, raising=False)
    monkeypatch.setattr(web_ingest, "_fetch", lambda url, client, timeout: (_Res(), "wechat"))
    res = web_ingest.ingest_url("https://mp.weixin.qq.com/s/abc")
    assert res.success, res.error
    out = Path(res.path)
    assert out.parent == intake
    head = out.read_text(encoding="utf-8")[:400]
    assert "doc_type: paper" in head and "doc_kind: article" in head
