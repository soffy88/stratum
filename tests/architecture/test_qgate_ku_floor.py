"""AII quality-gate absolute KU floor (aii/scripts/ku_floor.py)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "aii" / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("ku_floor", SCRIPTS / "ku_floor.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ku_floor"] = mod
    spec.loader.exec_module(mod)
    return mod


kf = _load()


def test_haozhuanqian_case_is_thin():
    # 好好赚钱: 4 KUs in 1 of 11 chapters "passed" with KU密度 4/10=40%
    r = kf.thin_reason(4, 1, 11)
    assert r and r.startswith("KU密度不足: 实抽4")


def test_zero_chapters_and_zero_ku():
    assert "0章有KU" in kf.thin_reason(4, 0, 11)
    assert kf.thin_reason(0, 0, 11).startswith("KU密度不足: 实抽0仅0%")


def test_coverage_floor():
    assert kf.thin_reason(40, 2, 11)  # 18% of chapters
    assert kf.thin_reason(40, 4, 11) is None  # 36%
    assert kf.thin_reason(40, 2, None) is None  # unknown book size -> no coverage check


def test_misc_floor_is_lower(monkeypatch):
    monkeypatch.delenv("QGATE_MISC_MIN_KU", raising=False)
    assert kf.thin_reason(4, 2, 4, is_misc=True) is None
    assert kf.thin_reason(4, 2, 4) is not None
    monkeypatch.setenv("QGATE_MIN_KU", "3")
    assert kf.thin_reason(4, 2, 4) is None


def test_reasons_match_retry_patterns():
    # flywheel_retry_quarantined.py classifies these strings as retryable
    src = (SCRIPTS / "flywheel_retry_quarantined.py").read_text(encoding="utf-8")
    assert "KU密度不足" in src
    for r in (kf.thin_reason(4, 1, 11), kf.thin_reason(4, 0, 11), kf.thin_reason(40, 2, 11)):
        assert re.search(r"KU密度不足: 实抽\d+", r)


def test_gate_discovery_and_batch_use_floor():
    gate = (SCRIPTS / "econ_quality_gate.py").read_text(encoding="utf-8")
    disc = (SCRIPTS / "econ_discover_all.py").read_text(encoding="utf-8")
    batch = (SCRIPTS / "econ_batch_run.sh").read_text(encoding="utf-8")
    assert "thin_reason(" in gate and "n_book_chs" in gate
    assert "thin_reason(" in disc
    assert "thin_reason(" in batch
